import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host.core import Core
from host import tools
from host.settings_operations import TaskRunner, command as operation
from apps.workbench.server import Handler
from control import receipts
from modules.model_gateway.routed import RoutedModels
from sdk.protocol import CoreError, canonical, decode
from test_core import task
from test_development import specification, candidate


class ToolUse(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-tool-use-')
        self.root = Path(self.temp.name); self.core = Core.initialize(self.root)
        shutil.copytree(ROOT/'user-data/worker-runtime', self.root/'worker-runtime')
        self.package = self.publish()

    def tearDown(self):
        self.core.close(); self.temp.cleanup()

    def publish(self, suffix=''):
        spec = specification('published-tool'+suffix)
        for c in spec['public_cases']+spec['evaluation_cases']: c['expected'] += suffix
        ident = self.core.packages.stage(candidate('def run(text):\n    return text.upper() + '+repr(suffix)+'\n'), spec)
        self.assertTrue(self.core.packages.verify(ident)['passed'])
        slot = self.core.packages.slot(spec['capability'])
        self.core.packages.activate(ident, slot['revision'] if slot else 0)
        return ident

    def request(self, **change):
        slot = self.core.packages.slot('plugin.upper.v1')
        return dict(action='submit', request_id='use-tool-0001', capability=slot['capability'],
                    package_id=slot['active'], revision=slot['revision'], text='Jarvis 中文', **change)

    def detail(self, ident): return tools.command(self.root, {'action':'detail','id':ident})

    def code(self, expected, fn, *args):
        with self.assertRaises(CoreError) as exc: fn(*args)
        self.assertEqual(exc.exception.code, expected)

    def test_reuse_without_model_calls_delivers_once_and_only_selected_task(self):
        other = self.core.tasks.submit(task('unrelated'))
        request = self.request(); ident = tools.command(self.root, request)['id']
        grant = self.detail(ident)['grant']['body']
        self.assertEqual(grant['capabilities'], ['plugin.upper.v1','artifact.write.v1'])
        self.assertEqual(grant['max_cost_units'], 2)
        with patch.object(RoutedModels, 'request', side_effect=AssertionError('No model allowed')):
            result = self.core.run_task(ident)
            self.assertEqual(result['status'], 'SUCCEEDED', result)
            self.core.run_task(ident)
        detail = self.detail(ident)
        self.assertEqual(detail['actions'][0]['result']['text'], 'JARVIS 中文')
        self.assertEqual(detail['grant']['spent'], 2)
        self.assertEqual([x['attempts'] for x in detail['actions']], [1,1])
        self.assertEqual(self.core.tasks.get(other)['status'], 'READY')
        self.assertEqual(tools.command(self.root, request)['id'], ident)
        self.assertEqual(len(tools.catalog(self.root)['recent']), 1)
        delivery=detail['actions'][1]['result']; self.assertTrue(delivery)
        self.assertEqual(self.core.db.all('SELECT * FROM model_calls'), [])

    def test_catalog_has_no_candidates_and_checks_scope_and_integrity(self):
        self.core.packages.stage(candidate('def run(text):\n    return text.lower()\n'), specification('candidate-only'))
        items = tools.catalog(self.root)['items']; self.assertEqual(len(items),1); self.assertTrue(items[0]['available'])
        with self.core.db.transaction() as tx:
            spec=specification();spec['scope_id']='project-secret'
            tx.execute('UPDATE packages SET spec=? WHERE id=?',(canonical(spec),self.package))
        self.assertEqual(tools.catalog(self.root)['items'], [])
        self.code('package_changed', tools.command, self.root, self.request())

    def test_input_version_stop_and_disabled_checks_do_not_grant(self):
        count=len(self.core.db.all('SELECT * FROM grants'))
        for changes in [{'text':[]},{'text':'a'*50001},{'text':'字'*40000},{'revision':True},{'action':[]},{'grant_id':'local-default'}]:
            self.code('tool_invalid',tools.command,self.root,{**self.request(),**changes})
        self.code('conflict',tools.command,self.root,{**self.request(),'revision':99})
        self.core.gate.stop();self.code('stopped',tools.command,self.root,self.request())
        self.core.gate.resume(self.core.gate.token())
        operation(self.root,{'action':'release','operation':'disable','id':'plugin.upper.v1','revision':1})
        self.code('module_disabled',tools.command,self.root,self.request())
        self.assertEqual(len(self.core.db.all('SELECT * FROM grants')),count)

    def test_idempotence_survives_new_release_and_different_inputs_conflict(self):
        request=self.request();ident=tools.command(self.root,request)['id']
        self.publish('!')
        self.assertEqual(tools.command(self.root,request),{'id':ident,'existing':True})
        self.code('conflict',tools.command,self.root,{**request,'text':'changed'})
        self.core.run_task(ident)
        self.assertEqual(self.detail(ident)['actions'][0]['result']['text'],'JARVIS 中文')
        self.assertEqual(self.detail(ident)['task']['bindings']['plugin.upper.v1'],self.package)

    def test_disable_blocks_pending_task_then_checked_restore_resumes(self):
        ident=tools.command(self.root,self.request())['id']
        operation(self.root,{'action':'release','operation':'disable','id':'plugin.upper.v1','revision':1})
        result=self.core.run_task(ident);self.assertEqual(result['status'],'WAITING');self.assertEqual(result['spent'],0)
        operation(self.root,{'action':'release','operation':'activate','id':self.package,'revision':2})
        self.assertEqual(self.core.run_task(ident)['status'],'SUCCEEDED')

    def test_cancelled_grant_stays_revoked_and_cannot_restart(self):
        ident=tools.command(self.root,self.request())['id']
        tools.command(self.root,{'action':'cancel','id':ident})
        runner=TaskRunner(self.root)
        try: self.code('invalid_state',runner.start_tool,{'id':ident})
        finally: runner.close()
        d=self.detail(ident);self.assertEqual(d['task']['status'],'CANCELLED');self.assertEqual(d['grant']['revoked'],1)
        self.code('invalid_state',self.core.run_task,ident)

    def test_unknown_receipt_reconciles_without_running_worker_again(self):
        ident=tools.command(self.root,self.request())['id']
        real_confirm=self.core.tasks.confirm
        def crash_after_receipt(task_id,action_id,result):
            if 'text' in result: raise OSError('simulated host failure after durable effect')
            real_confirm(task_id,action_id,result)
        with patch.object(self.core.tasks,'confirm',side_effect=crash_after_receipt): self.core.run_task(ident)
        self.assertEqual(self.detail(ident)['task']['status'],'WAITING')
        runner=TaskRunner(self.root)
        try: self.code('unknown_effect',runner.start_tool,{'id':ident})
        finally:runner.close()
        self.assertEqual(len(tools.command(self.root,{'action':'reconcile','id':ident})['reconciled']),1)
        with patch.object(self.core.worker,'run',side_effect=AssertionError('Do not replay known output')):
            self.assertEqual(self.core.run_task(ident)['status'],'SUCCEEDED')
        self.assertEqual(self.detail(ident)['actions'][0]['attempts'],1)

    def test_failed_worker_cannot_block_unrelated_task_or_regain_privilege(self):
        ident=tools.command(self.root,self.request())['id'];other=self.core.tasks.submit(task('still-works'))
        def cancellation(files,texts,checkpoint):
            tools.command(self.root,{'action':'cancel','id':ident});checkpoint()
            raise AssertionError('Revoked worker continued')
        with patch.object(self.core.worker,'run',side_effect=cancellation):self.core.run_task(ident)
        self.assertEqual(self.detail(ident)['task']['status'],'CANCELLED')
        self.assertEqual(self.core.run_task(other)['status'],'SUCCEEDED')
        self.assertTrue(self.core.packages.slot('plugin.upper.v1')['enabled'])

    def test_grant_expiry_and_known_failure_do_not_auto_retry(self):
        ident=tools.command(self.root,self.request())['id']
        with patch('control.policy.grants.time.time',return_value=time.time()+601):
            result=self.core.run_task(ident)
        self.assertEqual(result['status'],'FAILED')  # task deadline reached first
        self.assertEqual(result['spent'],0)
        self.code('invalid_state',self.core.run_task,ident)

    def test_http_csrf_and_background_lane(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='test-nonce';server.task_runner=TaskRunner(self.root)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        def call(path,body,token=True):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            headers={'Content-Type':'application/json','Origin':origin}
            if token:headers['X-Jarvis-Token']='test-nonce'
            conn.request('POST',path,body=canonical(body).encode(),headers=headers)
            r=conn.getresponse();value=decode(r.read());conn.close();return r.status,value
        try:
            self.assertEqual(call('/api/tools',self.request(),False)[0],403)
            status,created=call('/api/tools',self.request());self.assertEqual(status,200)
            self.assertEqual(call('/api/tools/run',{'id':created['id']})[0],202)
            server.task_runner.close()
            self.assertEqual(self.detail(created['id'])['task']['status'],'SUCCEEDED')
            self.assertEqual(call('/api/tools',{'action':'detail','id':created['id']})[0],200)
            other=self.core.tasks.submit(task('outside-tool-endpoint'))
            self.code('denied',tools.owned_task,self.core,other)
        finally:
            server.shutdown();server.server_close();thread.join(2);server.task_runner.close()


if __name__=='__main__':unittest.main()
