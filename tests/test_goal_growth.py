"""Real restricted Workers, fake models: the whole linked growth lifecycle."""
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
from host import goals, goal_growth, development
from host.background import BackgroundLane
from host.settings_operations import command as operation
from modules.task_resource import growth
from modules.autonomous_development.service import Development
from sdk.protocol import CoreError, canonical, decode
from test_development import Provider, candidate
from test_preferences_dialogue import fixture
from test_core import task
from apps.workbench.server import Handler


def draft_value():
    return {'schema':'jarvis.capability-draft.v1','supported':True,'summary':'转换文字为大写','description':'run(text)->str. Uppercase all Unicode letters, preserve whitespace; empty stays empty.',
            'public_cases':[{'input':'hi','expected':'HI'}],
            'evaluation_cases':[{'input':'héllo\n','expected':'HÉLLO\n'},{'input':'','expected':''}],'questions':[]}


class GoalGrowth(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jarvis-growth-');self.root=Path(self.temp.name);self.core=Core.initialize(self.root)
        self.core.preferences.install(fixture(),{});shutil.copytree(ROOT/'user-data/worker-runtime',self.root/'worker-runtime')
        self.request={'request_id':'growth-original','goal':'把这段文字转换为大写并保存','input_text':'Jarvis 中文','provider':'auto','model':'','reasoning':'default'}
        self.ident=goals.command(self.root,{'action':'create','request':self.request})['id']
        state=goals.execute(self.root,self.ident);self.assertEqual(state['status'],'NEEDS_INPUT')
        self.prepared=goal_growth.command(self.root,{'action':'prepare','id':self.ident,'revision':state['revision']})

    def tearDown(self):self.core.close();self.temp.cleanup()
    def detail(self):return goals.command(self.root,{'action':'detail','id':self.ident})
    def code(self,expected,fn,*args):
        with self.assertRaises(CoreError) as exc:fn(*args)
        self.assertEqual(exc.exception.code,expected)
    def draft(self,values=None,retry=False):
        p=Provider(values if values is not None else [draft_value()])
        with patch('host.goal_growth.NativeModel',return_value=p):r=goal_growth.draft(self.root,self.ident,retry)
        return r,p
    def begin_body(self):
        route={'provider':'openai','model':'test-model','reasoning':'low'}
        return {'action':'begin','id':self.ident,'revision':self.detail()['growth']['revision'],'routes':{'plan':[route],'code':[route]},
                'limits':{'max_model_calls':4,'max_attempts':2,'max_seconds':1800},'acceptance_reviewed':True}
    def begin(self):return goal_growth.command(self.root,self.begin_body())['development_id']
    def generate(self,dev,code=None):
        p=Provider([{'schema':'jarvis.development-plan.v1','capability':goal_growth.capability(self.ident),'summary':'Uppercase','steps':['Implement','Test']},code or candidate()])
        with patch('host.core.NativeModel',return_value=p):r=self.core.develop(dev,True)
        return r,p
    def publish(self,dev):
        r=self.core.development.get(dev);development.command(self.root,{'action':'approve','id':dev,'package_id':r['release_id']})
        return self.core.develop(dev,True)
    def returned_plan(self):
        return {'schema':'jarvis.goal-plan.v1','summary':'使用新能力','input_text':self.request['input_text'],'questions':[],
                'steps':[{'title':'转换大写','capability':goal_growth.capability(self.ident),'source':'input','expected':'大写文本'}]}

    def test_complete_loop_rejoins_original_goal_without_repeating_development(self):
        drafted,_=self.draft();self.assertEqual(drafted['status'],'REVIEW');self.assertEqual(self.core.db.all('SELECT * FROM development_runs'),[])
        body=self.begin_body();dev=self.begin();self.assertEqual(goal_growth.command(self.root,body)['development_id'],dev)
        r,coder=self.generate(dev);self.assertEqual(r['error'],'review_required');self.assertNotIn('HÉLLO',canonical(coder.prompts))
        self.assertIsNone(self.core.packages.slot(goal_growth.capability(self.ident)))
        self.code('review_required',goal_growth.rejoin,self.root,self.ident)
        development.command(self.root,{'action':'approve','id':dev,'package_id':r['release_id']})
        returned=Provider([self.returned_plan()]);lane=BackgroundLane();runner=development.DevelopmentRunner(self.root,lane)
        try:
            with patch('host.goals.NativeModel',return_value=returned):
                runner._run({'id':dev,'network_enabled':True,'retry_unknown':False})
        finally:lane.close()
        d=self.detail();self.assertEqual(d['plan']['id'],self.ident);self.assertEqual(d['plan']['request'],self.request)
        self.assertEqual(d['plan']['planning_round'],1);self.assertEqual(d['plan']['status'],'REVIEW');self.assertIsNone(d['task'])
        self.assertEqual(d['growth']['status'],'REJOINED');self.assertEqual(len(returned.prompts),1)
        old=growth.get(self.core.db,self.ident);self.assertEqual(old['prior_proposal']['steps'],[])
        self.assertEqual(self.core.db.one('SELECT revoked FROM grants WHERE id=?',(self.ident+'-build',))['revoked'],1)
        approved=goals.command(self.root,{'action':'approve','id':self.ident,'revision':d['plan']['revision']})
        self.assertEqual(self.core.run_task(approved['task_id'])['status'],'SUCCEEDED')
        self.assertEqual(self.detail()['actions'][0]['result']['text'],'JARVIS 中文')
        before=len(self.core.db.all('SELECT * FROM model_calls'))
        goal_growth.after_development(self.root,dev)
        self.assertEqual(len(self.core.db.all('SELECT * FROM model_calls')),before)
        self.assertEqual(len(self.core.db.all('SELECT * FROM development_runs')),1)

    def test_spec_edit_review_and_admission_are_bounded(self):
        self.draft();before=len(self.core.db.all('SELECT * FROM grants'));cmd=self.begin_body()
        self.code('review_required',goal_growth.command,self.root,{**cmd,'acceptance_reviewed':False})
        bad=draft_value();bad['evaluation_cases']=bad['public_cases']
        self.code('growth_incomplete',goal_growth.command,self.root,{'action':'edit','id':self.ident,'revision':cmd['revision'],'draft':bad})
        bad=draft_value();bad['grant_id']='local-default'
        with self.assertRaises(CoreError):growth.validate(bad)
        self.assertEqual(len(self.core.db.all('SELECT * FROM grants')),before)
        good=draft_value();good['summary']='Reviewed locally'
        goal_growth.command(self.root,{'action':'edit','id':self.ident,'revision':cmd['revision'],'draft':good})
        self.code('conflict',goal_growth.command,self.root,cmd)
        self.assertEqual(self.core.db.all('SELECT * FROM development_runs'),[])

    def test_unsupported_goal_cannot_silently_create_a_tool(self):
        unsupported={**draft_value(),'supported':False,'questions':['必须接入真实邮箱，纯文本工具无法发送邮件']}
        r,_=self.draft([unsupported]);self.assertEqual(r['status'],'NEEDS_INPUT')
        self.code('conflict',self.begin)
        self.assertEqual(self.core.db.all('SELECT * FROM packages'),[])

    def test_atomic_admission_failure_leaves_no_grant_child_or_link(self):
        self.draft();before=len(self.core.db.all('SELECT * FROM grants'))
        with patch.object(Development,'submit',side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):self.begin()
        self.assertEqual(len(self.core.db.all('SELECT * FROM grants')),before)
        self.assertIsNone(self.detail()['growth']['development_id']);self.assertEqual(self.detail()['growth']['status'],'REVIEW')
        self.assertEqual(self.core.db.all('SELECT * FROM development_runs'),[])

    def test_parent_edit_is_blocked_during_growth(self):
        p=self.detail()['plan']
        self.code('growth_active',goals.command,self.root,{'action':'edit','id':self.ident,'revision':p['revision'],'proposal':p['proposal']})

    def test_cancel_during_draft_does_not_overwrite_cancel_or_block_other_task(self):
        provider=Provider([])
        def stop(prompt,checkpoint):
            goals.command(self.root,{'action':'cancel','id':self.ident});checkpoint()
        provider.generate=stop
        with patch('host.goal_growth.NativeModel',return_value=provider):r=goal_growth.draft(self.root,self.ident)
        self.assertEqual(r['status'],'CANCELLED');self.assertEqual(self.detail()['plan']['status'],'CANCELLED')
        other=self.core.tasks.submit(task('unrelated-after-cancel'));self.assertEqual(self.core.run_task(other)['status'],'SUCCEEDED')

    def test_parent_cancel_prevents_approved_candidate_publication_even_from_modules_page(self):
        self.draft();dev=self.begin();r,_=self.generate(dev)
        development.command(self.root,{'action':'approve','id':dev,'package_id':r['release_id']})
        goals.command(self.root,{'action':'cancel','id':self.ident})
        self.assertTrue(self.core.development.get(dev)['cancel'])
        self.code('cancelled',operation,self.root,{'action':'release','operation':'activate','id':r['release_id'],'revision':0})
        self.assertIsNone(self.core.packages.slot(goal_growth.capability(self.ident)))
        self.code('cancelled',goal_growth.rejoin,self.root,self.ident)

    def test_bounded_failed_candidate_repairs_without_changing_heldout_cases(self):
        self.draft();dev=self.begin();spec=self.core.development.get(dev)['spec']
        p=Provider([{'schema':'jarvis.development-plan.v1','capability':goal_growth.capability(self.ident),'summary':'test','steps':['code']},candidate('def run(text):\n    return text.lower()\n'),candidate()])
        with patch('host.core.NativeModel',return_value=p):r=self.core.develop(dev,True)
        self.assertEqual(r['phase'],'verified');self.assertEqual(r['attempt'],1);self.assertEqual(len(p.prompts),3)
        self.assertEqual(self.core.development.get(dev)['spec']['evaluation_cases'],spec['evaluation_cases'])
        self.assertNotIn('HÉLLO',canonical(p.prompts));self.assertEqual(r['error'],'review_required')

    def test_unknown_draft_requires_ack_and_preserves_two_call_budget(self):
        r,_=self.draft([{'status':'UNKNOWN','code':'timeout'}]);self.assertEqual(r['error'],'model_unknown')
        r,p=self.draft([]);self.assertEqual(r['error'],'model_unknown');self.assertEqual(p.prompts,[])
        r,_=self.draft(retry=True);self.assertEqual(r['status'],'REVIEW')
        self.assertEqual(self.core.db.one('SELECT spent FROM grants WHERE id=?',(self.ident+'-draft-plan',))['spent'],2)

    def test_restart_recovers_draft_without_reissuing_model(self):
        self.draft([{'status':'UNKNOWN','code':'timeout'}])
        with self.core.db.transaction() as tx:
            tx.execute("UPDATE goal_growth SET status='DRAFTING' WHERE goal_id=?",(self.ident,))
            tx.execute("UPDATE model_calls SET status='DISPATCHING' WHERE run_id=?",(self.ident+'-draft',))
        lane=BackgroundLane()
        try:goal_growth.GrowthRunner(self.root,lane)
        finally:lane.close()
        self.assertEqual(self.detail()['growth']['status'],'WAITING');self.assertEqual(self.detail()['growth']['error'],'model_unknown')
        self.assertEqual(len(self.core.db.all('SELECT * FROM model_calls')),1)

    def test_rejoin_failure_preserves_published_result_for_explicit_retry(self):
        self.draft();dev=self.begin();r,_=self.generate(dev);self.assertEqual(self.publish(dev)['status'],'SUCCEEDED')
        slot=self.core.packages.slot(goal_growth.capability(self.ident))
        operation(self.root,{'action':'release','operation':'disable','id':slot['capability'],'revision':slot['revision']})
        self.code('module_disabled',goal_growth.rejoin,self.root,self.ident)
        self.assertEqual(self.detail()['growth']['status'],'DEVELOPING');self.assertEqual(self.detail()['plan']['planning_round'],0)
        operation(self.root,{'action':'release','operation':'activate','id':r['release_id'],'revision':slot['revision']+1})
        plan=goal_growth.rejoin(self.root,self.ident);self.assertEqual(plan['planning_round'],1)
        rev=plan['revision'];self.assertEqual(goal_growth.rejoin(self.root,self.ident)['revision'],rev)

    def test_sample_receipt_recovery_does_not_replay_sample(self):
        self.draft();dev=self.begin();r,_=self.generate(dev)
        development.command(self.root,{'action':'approve','id':dev,'package_id':r['release_id']})
        original=self.core.tasks.confirm
        def crash(t,a,result):
            if 'text' in result:raise OSError('after receipt')
            original(t,a,result)
        with patch.object(self.core.tasks,'confirm',side_effect=crash):r=self.core.develop(dev,True)
        self.assertEqual(r['status'],'WAITING')
        self.assertEqual(len(goal_growth.command(self.root,{'action':'reconcile','id':self.ident})['reconciled']),1)
        with patch.object(self.core.worker,'run',side_effect=AssertionError('Do not replay sample')):
            self.assertEqual(self.core.develop(dev,True)['status'],'SUCCEEDED')

    def test_schema_v5_upgrade_keeps_goal_and_existing_identity(self):
        self.core.close();db=sqlite3.connect(self.root/'state/core.sqlite3')
        db.execute('DROP TABLE assistant_operations');db.execute('DROP TABLE chat_goals');db.execute('DROP TABLE goal_context');db.execute('ALTER TABLE goal_plans DROP COLUMN generation');db.execute('DROP TABLE goal_growth');db.execute('ALTER TABLE goal_plans DROP COLUMN planning_round');db.execute('PRAGMA user_version=5');db.commit();db.close()
        self.core=Core(self.root);self.assertEqual(self.core.db.one('PRAGMA user_version')['user_version'],7)
        self.assertEqual(self.detail()['plan']['request'],self.request);self.assertIsNone(self.detail()['growth'])
        self.assertEqual(self.core.identity.describe()['owner_id'],'owner.local')

    def test_http_nonce_and_shared_runner(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='test-nonce';lane=BackgroundLane();server.growth_runner=goal_growth.GrowthRunner(self.root,lane)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
        def call(token):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port);headers={'Content-Type':'application/json','Origin':origin}
            if token:headers['X-Jarvis-Token']='test-nonce'
            conn.request('POST','/api/goal-growth/run',body=canonical({'id':self.ident,'mode':'draft','retry_unknown':False}),headers=headers)
            res=conn.getresponse();value=decode(res.read());conn.close();return res.status,value
        try:
            self.assertEqual(call(False)[0],403)
            with patch('host.goal_growth.NativeModel',return_value=Provider([draft_value()])):
                self.assertEqual(call(True)[0],202);lane.close()
            self.assertEqual(self.detail()['growth']['status'],'REVIEW')
        finally:server.shutdown();server.server_close();thread.join(2);lane.close()


if __name__=='__main__':unittest.main()
