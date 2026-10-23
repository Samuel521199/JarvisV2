"""Goal proposals never become authority without explicit, atomic admission."""
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from host.core import Core
from host import goals
from host.background import BackgroundLane
from host.settings_operations import TaskRunner, command as operation
from apps.workbench.server import Handler
from control.network import NetworkGate
from modules.model_gateway.routed import RoutedModels
from modules.task_resource.ledger import Ledger
from sdk.protocol import CoreError, canonical, decode
from test_development import specification, candidate, Provider
from test_preferences_dialogue import fixture
from test_core import task


def proposal(text='Jarvis 中文',chain=False):
    step={'title':'转换大写','capability':'plugin.upper.v1','source':'input','expected':'保留空白，字母变为大写'}
    return {'schema':'jarvis.goal-plan.v1','summary':'使用已发布的文字工具','input_text':text,
            'steps':[step]+([{**step,'source':'previous'}] if chain else []),'questions':[]}


class GoalPlans(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jarvis-goal-');self.root=Path(self.temp.name)
        self.core=Core.initialize(self.root)
        self.core.preferences.install(fixture(),{})
        shutil.copytree(ROOT/'user-data/worker-runtime',self.root/'worker-runtime')
        self.package=self.publish()

    def tearDown(self):self.core.close();self.temp.cleanup()

    def publish(self,suffix=''):
        spec=specification('goal-tool'+suffix)
        for case in spec['public_cases']+spec['evaluation_cases']:case['expected']+=suffix
        ident=self.core.packages.stage(candidate('def run(text):\n    return text.upper() + '+repr(suffix)+'\n'),spec)
        self.assertTrue(self.core.packages.verify(ident)['passed'])
        slot=self.core.packages.slot(spec['capability']);self.core.packages.activate(ident,slot['revision'] if slot else 0)
        return ident

    def req(self,**changes):
        return {'request_id':'goal-request-01','goal':'将文本转为大写并保存','input_text':'Jarvis 中文',
                'provider':'auto','model':'','reasoning':'default',**changes}

    def create(self,**changes):return goals.command(self.root,{'action':'create','request':self.req(**changes)})['id']
    def detail(self,ident):return goals.command(self.root,{'action':'detail','id':ident})
    def approve(self,ident):return goals.command(self.root,{'action':'approve','id':ident,'revision':self.detail(ident)['plan']['revision']})['task_id']
    def code(self,expected,fn,*args):
        with self.assertRaises(CoreError) as exc:fn(*args)
        self.assertEqual(exc.exception.code,expected)

    def plan(self,ident,values=None,retry=False):
        provider=Provider(values if values is not None else [proposal()])
        with patch('host.goals.NativeModel',return_value=provider):result=goals.execute(self.root,ident,retry)
        return result,provider

    def test_review_grants_model_only_then_atomic_admission_and_pipeline_delivery(self):
        ident=self.create();self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        planned,provider=self.plan(ident,[proposal(chain=True)])
        self.assertEqual(planned['status'],'REVIEW');self.assertEqual(len(provider.prompts),1)
        self.assertIn('自动保存最终结果到 Jarvis 本机任务产物目录',provider.prompts[0])
        grants=self.core.db.all('SELECT * FROM grants WHERE id LIKE ?',(ident+'%',))
        self.assertEqual(len(grants),1);self.assertEqual(decode(grants[0]['body'])['capabilities'],['model.generate.v1'])
        rev=planned['revision'];task_id=self.approve(ident)
        self.assertEqual(goals.command(self.root,{'action':'approve','id':ident,'revision':rev})['task_id'],task_id)
        self.assertEqual(self.core.tasks.get(task_id)['status'],'READY')
        self.assertEqual(self.core.run_task(task_id)['status'],'SUCCEEDED')
        d=self.detail(ident);self.assertEqual([a['result'].get('text') for a in d['actions'][:2]],['JARVIS 中文']*2)
        self.assertEqual(d['task']['spent'],3)
        self.assertEqual(self.core.db.one('SELECT revoked FROM grants WHERE id=?',(ident+'-plan',))['revoked'],1)
        with patch.object(self.core.worker,'run',side_effect=AssertionError('No replay')):self.core.run_task(task_id)
        self.assertEqual(len(self.core.db.all('SELECT * FROM model_calls')),1)

    def test_invalid_inputs_do_not_create_grants_or_goals_and_idempotence(self):
        before=len(self.core.db.all('SELECT * FROM grants'))
        for change in [{'input_text':[]},{'goal':' '},{'request_id':'bad'},{'extra':'forbidden'},{'input_text':'x'*12001}]:
            self.code('plan_invalid',goals.command,self.root,{'action':'create','request':self.req(**change)})
        self.assertEqual(len(self.core.db.all('SELECT * FROM grants')),before)
        ident=self.create();self.assertEqual(self.create(),ident)
        self.code('conflict',goals.command,self.root,{'action':'create','request':self.req(goal='changed')})
        self.assertEqual(len(goals.listing(self.root)),1)

    def test_hallucinated_tool_and_changed_input_cannot_execute(self):
        p=proposal();p['steps'][0]['capability']='mail.send.v1'
        ident=self.create();state,_=self.plan(ident,[p]);self.assertEqual(state['error'],'plan_capability')
        self.code('conflict',goals.command,self.root,{'action':'approve','id':ident,'revision':state['revision']})
        second=self.create(request_id='changed-input-02');state,_=self.plan(second,[proposal('changed')])
        self.assertEqual(state['error'],'plan_input_changed');self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])

    def test_questions_block_execution_edit_cas_cannot_add_authority(self):
        ident=self.create();p=proposal();p['questions']=['还要发送邮件，当前没有此能力']
        state,_=self.plan(ident,[p]);self.assertEqual(state['status'],'NEEDS_INPUT')
        self.code('conflict',goals.command,self.root,{'action':'approve','id':ident,'revision':state['revision']})
        edit={'action':'edit','id':ident,'revision':state['revision'],'proposal':proposal()}
        d=goals.command(self.root,edit);self.assertEqual(d['plan']['status'],'REVIEW')
        self.code('conflict',goals.command,self.root,edit)
        p=proposal();p['steps'][0]['source']='previous'
        self.code('plan_capability',goals.command,self.root,{**edit,'revision':d['plan']['revision'],'proposal':p})
        p=proposal();p['grant_id']='local-default'
        with self.assertRaises(CoreError):goals.command(self.root,{**edit,'proposal':p})

    def test_admission_rolls_back_grant_task_link_and_revision_on_failure(self):
        ident=self.create();state,_=self.plan(ident)
        with patch.object(Ledger,'submit',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):self.approve(ident)
        self.assertIsNone(self.core.db.one('SELECT id FROM grants WHERE id=?',(ident+'-execute',)))
        self.assertEqual(self.detail(ident)['plan']['revision'],state['revision'])
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        self.assertEqual(self.core.db.one('SELECT revoked FROM grants WHERE id=?',(ident+'-plan',))['revoked'],0)
        self.approve(ident)

    def test_release_change_requires_new_catalog_review(self):
        ident=self.create();self.plan(ident);self.publish('!')
        self.code('plan_version_changed',self.approve,ident)
        self.assertIsNone(self.detail(ident)['task'])

    def test_cancel_during_model_retains_cancellation_and_other_tasks_run(self):
        ident=self.create()
        provider=Provider([])
        def cancel(prompt,checkpoint):
            goals.command(self.root,{'action':'cancel','id':ident});checkpoint()
            raise AssertionError('continued after cancellation')
        provider.generate=cancel
        with patch('host.goals.NativeModel',return_value=provider):state=goals.execute(self.root,ident)
        self.assertEqual(state['status'],'CANCELLED');self.assertEqual(state['cancel'],1)
        self.code('conflict',self.approve,ident)
        other=self.core.tasks.submit(task('unrelated'));self.assertEqual(self.core.run_task(other)['status'],'SUCCEEDED')

    def test_cancel_during_worker_revokes_execution_and_keeps_module_available(self):
        ident=self.create();self.plan(ident);task_id=self.approve(ident)
        def cancel(files,texts,checkpoint):
            goals.command(self.root,{'action':'cancel','id':ident});checkpoint()
            raise AssertionError('continued after cancellation')
        with patch.object(self.core.worker,'run',side_effect=cancel):self.core.run_task(task_id)
        self.assertEqual(self.detail(ident)['task']['status'],'CANCELLED')
        self.assertEqual(self.core.db.one('SELECT revoked FROM grants WHERE id=?',(ident+'-execute',))['revoked'],1)
        self.assertTrue(self.core.packages.slot('plugin.upper.v1')['enabled'])
        runner=TaskRunner(self.root)
        try:self.code('invalid_state',runner.start_goal,{'id':task_id})
        finally:runner.close()

    def test_unknown_model_requires_acknowledgement_with_same_budget(self):
        ident=self.create();state,_=self.plan(ident,[{'status':'UNKNOWN','code':'timeout'}]);self.assertEqual(state['error'],'model_unknown')
        state,p=self.plan(ident,[]);self.assertEqual(state['error'],'model_unknown');self.assertEqual(p.prompts,[])
        state,_=self.plan(ident,retry=True);self.assertEqual(state['status'],'REVIEW')
        self.assertEqual(len(self.core.db.all('SELECT * FROM model_calls WHERE run_id=?',(ident,))),2)
        self.assertEqual(self.core.db.one('SELECT spent FROM grants WHERE id=?',(ident+'-plan',))['spent'],2)

    def test_known_rejection_uses_backup_and_does_not_exceed_two_calls(self):
        ident=self.create();state,p=self.plan(ident,[{'status':'REJECTED','code':'unavailable'},proposal()])
        self.assertEqual(state['status'],'REVIEW');self.assertEqual(len(p.prompts),2)
        self.assertEqual(len(self.core.db.all('SELECT * FROM model_calls')),2)

    def test_offline_and_empty_catalog_do_not_call_model(self):
        ident=self.create();NetworkGate(self.root).update({'revision':0,'blocked':True})
        state,p=self.plan(ident,[]);self.assertEqual(state['error'],'network_disabled');self.assertEqual(p.prompts,[])
        operation(self.root,{'action':'release','operation':'disable','id':'plugin.upper.v1','revision':1})
        other=self.create(request_id='empty-catalog-01')
        state,p=self.plan(other,[]);self.assertEqual(state['status'],'NEEDS_INPUT');self.assertEqual(p.prompts,[])

    def test_unknown_worker_receipt_reconciles_and_resumes_without_replaying_step(self):
        ident=self.create();self.plan(ident,[proposal(chain=True)]);task_id=self.approve(ident)
        original=self.core.tasks.confirm
        def fail_once(t,a,result):
            if self.core.db.one('SELECT step_id FROM actions WHERE id=?',(a,))['step_id']=='step-1':raise OSError('host died after receipt')
            original(t,a,result)
        with patch.object(self.core.tasks,'confirm',side_effect=fail_once):self.core.run_task(task_id)
        runner=TaskRunner(self.root)
        try:self.code('unknown_effect',runner.start_goal,{'id':task_id})
        finally:runner.close()
        self.assertEqual(len(goals.command(self.root,{'action':'reconcile','id':ident})['reconciled']),1)
        with patch.object(self.core.worker,'run',wraps=self.core.worker.run) as worker:
            self.assertEqual(self.core.run_task(task_id)['status'],'SUCCEEDED')
            # A CANARY may run its fixed probes; the original business input must not be replayed.
            inputs=[c.args[1] for c in worker.call_args_list]
            self.assertNotIn(['Jarvis 中文'],inputs);self.assertEqual(inputs.count(['JARVIS 中文']),1)
        self.assertEqual([a['attempts'] for a in self.detail(ident)['actions']],[1,1,1])

    def test_planning_and_coding_share_one_slot_without_blocking_local_task(self):
        lane=BackgroundLane();released=threading.Event();started=threading.Event()
        def block():started.set();released.wait(5);return {'status':'REVIEW'}
        try:
            lane.submit('goal','test',block);self.assertTrue(started.wait(2))
            self.code('development_busy',lane.submit,'development','other',lambda:{})
            other=self.core.tasks.submit(task('local-while-planning'));self.assertEqual(self.core.run_task(other)['status'],'SUCCEEDED')
        finally:released.set();lane.close()
        self.assertEqual(lane.state()['kind'],'goal')

    def test_schema_v4_upgrade_preserves_identity_and_releases(self):
        self.core.close();db=sqlite3.connect(self.root/'state/core.sqlite3')
        db.execute('DROP TABLE assistant_operations');db.execute('DROP TABLE chat_goals');db.execute('DROP TABLE goal_context');db.execute('ALTER TABLE goal_plans DROP COLUMN generation');db.execute('DROP TABLE goal_growth');db.execute('DROP TABLE goal_plans');db.execute('PRAGMA user_version=4');db.commit();db.close()
        self.core=Core(self.root)
        self.assertEqual(self.core.db.one('PRAGMA user_version')['user_version'],7)
        self.assertEqual(self.core.identity.describe()['owner_id'],'owner.local')
        self.assertEqual(self.core.packages.slot('plugin.upper.v1')['active'],self.package)
        self.assertEqual(goals.listing(self.root),[])

    def test_restart_recovers_only_goal_calls_and_leaves_other_work_intact(self):
        ident=self.create();self.plan(ident,[{'status':'UNKNOWN','code':'timeout'}])
        with self.core.db.transaction() as tx:
            tx.execute("UPDATE model_calls SET status='DISPATCHING' WHERE run_id=?",(ident,))
            tx.execute("UPDATE goal_plans SET status='PLANNING' WHERE id=?",(ident,))
            tx.execute("INSERT INTO model_calls(id,run_id,phase,provider,status,input_digest,reservation,created) VALUES('other-call','other-run','plan','test','DISPATCHING','digest',1,0)")
        lane=BackgroundLane()
        try:goals.GoalRunner(self.root,lane)
        finally:lane.close()
        self.assertEqual(self.detail(ident)['plan']['status'],'WAITING')
        self.assertEqual(self.detail(ident)['plan']['error'],'model_unknown')
        self.assertEqual(self.core.db.one("SELECT status FROM model_calls WHERE id='other-call'")['status'],'DISPATCHING')
        RoutedModels(self.core.db,{},[]).recover(ident)
        self.assertEqual(self.core.db.one("SELECT status FROM model_calls WHERE id='other-call'")['status'],'DISPATCHING')

    def test_http_origin_nonce_scoped_task_and_runner(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='test-nonce'
        lane=BackgroundLane();server.goal_runner=goals.GoalRunner(self.root,lane);server.task_runner=TaskRunner(self.root)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        def call(path,body,token=True):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            headers={'Content-Type':'application/json','Origin':origin}
            if token:headers['X-Jarvis-Token']='test-nonce'
            conn.request('POST',path,body=canonical(body).encode(),headers=headers)
            r=conn.getresponse();v=decode(r.read());conn.close();return r.status,v
        try:
            cmd={'action':'create','request':self.req()};self.assertEqual(call('/api/goals',cmd,False)[0],403)
            status,v=call('/api/goals',cmd);self.assertEqual(status,200);ident=v['id']
            with patch('host.goals.NativeModel',return_value=Provider([proposal()])):
                self.assertEqual(call('/api/goals/plan',{'id':ident,'retry_unknown':False})[0],202);lane.close()
            rev=self.detail(ident)['plan']['revision']
            status,v=call('/api/goals',{'action':'approve','id':ident,'revision':rev});self.assertEqual(status,200)
            self.assertEqual(call('/api/goals/run',{'id':v['task_id']})[0],202);server.task_runner.close()
            self.assertEqual(self.detail(ident)['task']['status'],'SUCCEEDED')
            other=self.core.tasks.submit(task('not-a-goal'));self.code('denied',goals.owned_task,self.core,other)
        finally:server.shutdown();server.server_close();thread.join(2);server.task_runner.close();lane.close()


if __name__=='__main__':unittest.main()
