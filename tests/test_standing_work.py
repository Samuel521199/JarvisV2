"""Standing work uses real goal admission/ledger; model/desktop effects excluded."""
import copy,time,uuid,unittest
from datetime import datetime,timezone
from unittest.mock import patch
import test_goal_plans as base
from host import goals,standing_work
from modules.task_resource.plans import Plans
from modules.task_resource.standing import Standing,quiet,policy
from modules.task_resource.scheduling import Scheduling
from sdk.protocol import CoreError,decode


def config(now=None,**changes):
    return {'start_at':datetime.fromtimestamp(now or time.time(),timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'interval_seconds':0,'max_runs':3,'max_action_units':20,'max_attempts':3,'quiet_start':0,'quiet_end':0,
        'utc_offset_minutes':480,'notification_interval_seconds':60,'cloud_model_budget_usd':0,**changes}


def checks(expected='JARVIS 中文'):
    return {'coverage':'complete','criteria':[{'id':'literal','step_id':'step-1','check':'text_equals','expected':expected}],
        'requirements':[{'id':'output','text':'精确文本结果','kind':'literal','criterion_ids':['literal']}]}


class StandingWork(unittest.TestCase):
    setUp=base.GoalPlans.setUp
    tearDown=base.GoalPlans.tearDown
    publish=base.GoalPlans.publish
    req=base.GoalPlans.req
    create=base.GoalPlans.create
    plan=base.GoalPlans.plan
    detail=base.GoalPlans.detail
    code=base.GoalPlans.code

    def make(self,expected='JARVIS 中文',**changes):
        goal=self.create(request_id=uuid.uuid4().hex);self.plan(goal)
        request={'action':'create','request_id':uuid.uuid4().hex,'title':'验收持续办事','plans':[{'goal_id':goal,'acceptance':checks(expected)}],'policy':config(**changes)}
        row=standing_work.command(self.root,request);return row,request

    def act(self,row,action,**extra):
        return standing_work.command(self.root,{'action':action,'request_id':uuid.uuid4().hex,'id':row['id'],'revision':row['revision'],**extra})

    def state(self,ident):return next(r for r in standing_work.read(self.root)['items'] if r['id']==ident)

    def step(self):standing_work.advance(self.root)

    def run_task(self,row):
        r=self.state(row['id'])['runs'][0];tid=next(a['task_id'] for a in r['attempts'].values() if a['task_id']);self.core.run_task(tid);return tid

    def test_review_execution_acceptance_feedback_and_withdrawal(self):
        row,request=self.make();self.step();self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        self.assertEqual(standing_work.command(self.root,request),row)
        row=self.act(row,'approve');self.step();tid=self.run_task(row);self.step();r=self.state(row['id'])
        self.assertEqual(r['status'],'DONE');self.assertEqual(r['runs'][0]['status'],'VERIFIED')
        self.assertEqual(len(self.core.db.all('SELECT * FROM tasks')),1);self.assertEqual(len(self.core.db.all('SELECT * FROM model_calls')),1)
        row=self.act(row,'feedback',run_id=r['runs'][0]['id'],kind='accept',note='这项文字处理方法可用')
        r=self.state(row['id']);self.assertFalse(r['runs'][0]['learning_candidate']['automatic_use'])
        row=self.act(row,'feedback',run_id=r['runs'][0]['id'],kind='withdraw',note='撤回这次经验，需重新检查')
        self.assertEqual(self.state(row['id'])['status'],'PAUSED')

    def test_wrong_result_is_not_complete_and_other_mandate_continues(self):
        bad,_=self.make(expected='wrong');good,_=self.make()
        bad=self.act(bad,'approve');good=self.act(good,'approve');self.step();self.run_task(bad);self.run_task(good);self.step()
        self.assertEqual(self.state(bad['id'])['status'],'NEEDS_INPUT');self.assertEqual(self.state(good['id'])['status'],'DONE')
        self.code('standing_feedback',lambda:self.act(bad,'feedback',run_id=self.state(bad['id'])['runs'][0]['id'],kind='accept',note='不允许把错误验收成正确'))

    def test_restart_idempotence_no_repeat_confirmed_actions(self):
        row,_=self.make();row=self.act(row,'approve');self.step();tid=self.run_task(row)
        with patch('host.standing_work.goals.command',side_effect=AssertionError('must not admit a second task')):self.step()
        self.step();self.assertEqual(len(self.core.db.all('SELECT * FROM tasks')),1);self.assertEqual(self.core.tasks.get(tid)['status'],'SUCCEEDED')

    def test_quiet_foreground_and_budget_prevent_admission(self):
        row,_=self.make(max_action_units=1);row=self.act(row,'approve')
        standing_work.advance(self.root,foreground=True);self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        self.step();self.assertEqual(self.state(row['id'])['error'],'standing_budget')
        p=config(quiet_start=22*60,quiet_end=8*60)
        self.assertTrue(quiet(p,datetime(2026,11,10,16,tzinfo=timezone.utc).timestamp()))
        self.assertFalse(quiet(p,datetime(2026,11,10,6,tzinfo=timezone.utc).timestamp()))
        self.code('standing_invalid',policy,{**p,'cloud_model_budget_usd':1})

    def test_pause_cancel_stale_commands_and_grant_boundary(self):
        row,_=self.make();row=self.act(row,'approve');self.step();tid=self.state(row['id'])['runs'][0]['attempts']['0-0']['task_id']
        paused=self.act(row,'pause');self.code('conflict',self.act,row,'resume')
        self.code('module_disabled',self.core._goal_memory_check,tid)
        resumed=self.act(paused,'resume');cancelled=self.act(resumed,'cancel');self.step()
        self.assertEqual(cancelled['status'],'CANCELLED');self.assertTrue(self.core.tasks.get(tid)['cancel'])

    def test_unknown_effect_never_retried_or_readmitted(self):
        row,_=self.make();row=self.act(row,'approve');self.step();r=self.state(row['id'])['runs'][0];tid=r['attempts']['0-0']['task_id']
        body=self.core.tasks.get(tid)['body'];self.core.tasks.prepare(tid,body['steps'][0],body['steps'][0]['arguments'])
        self.core.db.connection.execute("UPDATE actions SET status='UNKNOWN' WHERE task_id=?",(tid,));self.core.tasks.state(tid,'WAITING','unknown_effect');self.step();self.step()
        self.assertEqual(self.state(row['id'])['status'],'NEEDS_INPUT');self.assertEqual(len(self.core.db.all('SELECT * FROM tasks')),1)

    def test_failed_attempts_bounded_and_successful_previous_goal_not_repeated(self):
        row,_=self.make();row=self.act(row,'approve')
        clock=time.time()
        for i in range(3):
            standing_work.advance(self.root,now=clock+i*30)
            run=self.state(row['id'])['runs'][0];tid=run['attempts']['0-'+str(i)]['task_id'];self.core.tasks.state(tid,'FAILED','synthetic_known_failure')
            standing_work.advance(self.root,now=clock+i*30)
        r=self.state(row['id']);self.assertEqual(r['status'],'NEEDS_INPUT');self.assertEqual(len(r['runs'][0]['attempts']),3)

    def test_sleep_coalesces_intervals_and_source_change_blocks_next_dispatch(self):
        row,_=self.make(interval_seconds=60);row=self.act(row,'approve');standing_work.advance(self.root,now=time.time()+3600)
        self.run_task(row);standing_work.advance(self.root,now=time.time()+3601);r=self.state(row['id']);self.assertEqual(r['runs_started'],1);self.assertGreater(r['next_at'],time.time()+3600)
        source=r['plans'][0]['id'];self.core.db.connection.execute("UPDATE goal_plans SET cancel=1 WHERE id=?",(source,));self.step();self.assertEqual(self.state(row['id'])['status'],'NEEDS_INPUT')

    def test_multiple_ordered_goals_and_original_snapshot_guard(self):
        row,request=self.make();other=self.create(request_id=uuid.uuid4().hex);self.plan(other)
        request['request_id']=uuid.uuid4().hex;request['plans'].append({'goal_id':other,'acceptance':checks()})
        row=standing_work.command(self.root,request);row=self.act(row,'approve');self.step();self.run_task(row);self.step();self.step()
        run=self.state(row['id'])['runs'][0];self.assertEqual(run['cursor'],1)
        tid=run['attempts']['1-0']['task_id'];self.core.db.connection.execute("UPDATE goal_plans SET cancel=1 WHERE id=?",(other,))
        self.code('plan_source_changed',self.core._goal_memory_check,tid)
        self.assertEqual(len(run['goals']),2)

    def test_notification_deferral_and_feedback_requires_new_review(self):
        from modules.continuity.attention import needs_receipt
        row,_=self.make();row=self.act(row,'approve');self.step();self.run_task(row);self.step()
        item=next(i for i in standing_work.projection(self.root)[0] if i['id']==row['id']);self.assertFalse(needs_receipt(item))
        self.step();item=next(i for i in standing_work.projection(self.root)[0] if i['id']==row['id']);self.assertTrue(needs_receipt(item))
        r=self.state(row['id']);row=self.act(row,'feedback',run_id=r['runs'][0]['id'],kind='reject',note='需要修改预期')
        self.code('standing_review_required',lambda:self.act(row,'resume'))

    def test_paused_occurrence_can_be_abandoned_without_deleting_receipts(self):
        row,_=self.make();row=self.act(row,'approve');self.step();row=self.act(row,'pause')
        row=self.act(row,'abandon_run');state=self.state(row['id']);self.assertIsNone(state['current_run']);self.assertEqual(state['runs'][0]['status'],'CANCELLED')
        self.assertEqual(len(self.core.db.all('SELECT * FROM tasks')),1)

    def test_model_schedule_quote_scoping_and_compatibility(self):
        from host import assistant
        from control.application_compatibility import require_compatible
        from sdk.protocol import canonical,PROJECT
        from pathlib import Path
        proposal={'schema':'jarvis.assistant-turn.v1','reply':'待核对','action':{'kind':'goal','goal':'文字处理','input_text':'a','target':'',
            'standing':{'quote':'每天帮我处理文字','interval_seconds':86400,'time_text':'每天'}}}
        self.assertEqual(assistant.parse(canonical(proposal),[])[1]['standing']['interval_seconds'],86400)
        proposal['action']['kind']='chat';self.code('assistant_invalid',assistant.parse,canonical(proposal),[])
        row,_=self.make();self.assertTrue(require_compatible(self.root,PROJECT)['compatible'])
        package=self.root/'old-package';(package/'config').mkdir(parents=True)
        (package/'config/runtime-compatibility.json').write_text((PROJECT/'config/runtime-compatibility.json').read_text(),encoding='utf-8')
        self.code('application_data_compatibility',require_compatible,self.root,package)

    def test_http_guards_same_projection_and_draft_has_no_effect(self):
        from http.server import ThreadingHTTPServer
        from apps.workbench.server import Handler
        from control.local_access import LocalAccess,cookie_name
        import threading,http.client,json
        row,request=self.make();server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='synthetic-page';server.access=LocalAccess(self.root,key='synthetic-key-'+('a'*32))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port);cookie=cookie_name(server.server_port)+'='+server.access.unlock('synthetic-key-'+('a'*32))
        def call(path,body=None,**changes):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port);headers={'Cookie':cookie,'Origin':origin,'X-Jarvis-Token':server.nonce,'Content-Type':'application/json',**changes}
            conn.request('POST' if body is not None else 'GET',path,body=json.dumps(body) if body else None,headers=headers);r=conn.getresponse();raw=r.read();conn.close();return r.status,json.loads(raw)
        try:
            for headers in ({'Cookie':''},{'Origin':'https://hostile.invalid'},{'X-Jarvis-Token':''}):self.assertIn(call('/api/standing-work',request,**headers)[0],(401,403))
            self.assertEqual(call('/api/standing-work')[1]['items'][0]['id'],row['id']);self.assertEqual(call('/api/work-status')[0],200)
            self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        finally:
            server.shutdown();server.server_close();thread.join()
            if hasattr(server,'family'):server.family.close()

    def test_bad_controls_do_not_create_schema_or_execution(self):
        self.code('standing_invalid',standing_work.command,self.root,{'action':[]})
        self.assertIsNone(self.core.db.one("SELECT 1 FROM meta WHERE key='standing_schema'"))
        row,request=self.make();request['request_id']=uuid.uuid4().hex;request['plans'][0]['acceptance']['criteria'][0]['check']='shell'
        self.code('standing_invalid',standing_work.command,self.root,request)
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])

    def test_initial_approval_and_cancelled_feedback_cannot_revive_work(self):
        row,_=self.make();paused=self.act(row,'pause');self.code('standing_state',lambda:self.act(paused,'resume'))
        row=self.act(paused,'approve');self.step();self.run_task(row);self.step();row=self.act(row,'cancel')
        run=self.state(row['id'])['runs'][0]
        row=self.act(row,'feedback',run_id=run['id'],kind='reject',note='结果留作失败教训')
        self.assertEqual(row['status'],'CANCELLED');self.code('standing_state',lambda:self.act(row,'resume'))

    def test_mixed_wait_and_failed_retries_share_one_attempt_limit(self):
        row,_=self.make();row=self.act(row,'approve');self.step();r=self.state(row['id'])['runs'][0];tid=r['attempts']['0-0']['task_id'];now=time.time()
        self.core.tasks.state(tid,'WAITING','module_disabled');standing_work.advance(self.root,now=now)
        self.core.tasks.state(tid,'FAILED','known_failure');standing_work.advance(self.root,now=now+6)
        standing_work.advance(self.root,now=now+20);r=self.state(row['id'])['runs'][0];last=r['attempts']['0-1']['task_id']
        self.core.tasks.state(last,'FAILED','known_failure');standing_work.advance(self.root,now=now+21)
        self.assertEqual(self.state(row['id'])['status'],'NEEDS_INPUT');self.assertEqual(self.state(row['id'])['runs'][0]['retries_used'],2)

    def test_feedback_projection_failure_still_durably_pauses_shared_method_users(self):
        row,request=self.make();request['request_id']=uuid.uuid4().hex;other=standing_work.command(self.root,request)
        row=self.act(row,'approve');other=self.act(other,'approve');self.step();self.run_task(row);self.step();run=self.state(row['id'])['runs'][0]
        with patch('host.completion.command',side_effect=RuntimeError('synthetic projection failure')):
            with self.assertRaises(RuntimeError):self.act(row,'feedback',run_id=run['id'],kind='withdraw',note='撤回共同方法')
        self.assertEqual(self.state(row['id'])['status'],'PAUSED');self.assertEqual(self.state(other['id'])['status'],'PAUSED')
        self.assertIn('withdrawal_requested',self.state(row['id'])['runs'][0])

    def linked_mandate(self):
        from test_assistant_goals import AssistantGoals
        from host import assistant
        chat=AssistantGoals.chat(self);goal=assistant.goal_from_turn(self.root,'chat-turn-1')['id'];self.plan(goal)
        row=standing_work.command(self.root,{'action':'create','request_id':uuid.uuid4().hex,'title':'每天文字安排',
            'plans':[{'goal_id':goal,'acceptance':checks()}],'policy':config()})
        return chat,self.act(row,'approve')

    def test_conversation_control_uses_current_shared_state_and_one_receipt(self):
        from host import assistant
        from modules.dialogue.store import Dialogues
        from sdk.protocol import canonical
        chat,row=self.linked_mandate();items=assistant.context(self.root,chat,'openai')
        self.assertEqual(next(i for i in items if i.get('resource')=='standing')['status'],'ACTIVE')
        prompt,_=assistant.instructions(self.root,chat,'openai');self.assertIn(row['id'],prompt)
        action={'kind':'cancel','goal':'','input_text':'','target':row['id'],'standing_operation':'pause'}
        reply,action=assistant.parse(canonical({'schema':'jarvis.assistant-turn.v1','reply':'待核对','action':action}),items)
        s=Dialogues(self.root)
        try:
            s.begin({'chat_id':chat,'request_id':'pause-turn','text':'先停一下每天的安排','provider':'openai','model':'test-model','reasoning':'default','assistant_mode':True},[])
            s.finish('pause-turn',{'status':'SUCCEEDED','text':reply,'provider':'openai','model':'test-model','assistant_action':action})
        finally:s.close()
        receipt=assistant.accept(self.root,{'turn_id':'pause-turn'});again=assistant.accept(self.root,{'turn_id':'pause-turn'})
        self.assertEqual(receipt,again);self.assertEqual(self.state(row['id'])['status'],'PAUSED')

    def test_other_chat_cannot_control_an_unrelated_standing_mandate(self):
        from host import assistant
        from sdk.protocol import canonical
        from modules.dialogue.store import Dialogues
        chat,row=self.linked_mandate();s=Dialogues(self.root)
        try:other=s.create()
        finally:s.close()
        action={'kind':'cancel','goal':'','input_text':'','target':row['id'],'standing_operation':'cancel'}
        self.code('assistant_invalid',assistant.parse,canonical({'schema':'jarvis.assistant-turn.v1','reply':'不能跨会话操作','action':action}),assistant.context(self.root,other,'openai'))
        self.assertEqual(self.state(row['id'])['status'],'ACTIVE')

    def test_standing_result_is_published_into_original_session_and_resync_is_idempotent(self):
        from host.session_workspace import command
        chat,row=self.linked_mandate();self.step();self.run_task(row);self.step()
        first=command(self.root,{'action':'sync','id':chat});second=command(self.root,{'action':'sync','id':chat})
        self.assertEqual(first['files'],second['files'])
        artifacts=[f for f in first['files'] if f['path'].startswith('artifacts/')]
        self.assertEqual(len(artifacts),1)
        from pathlib import Path
        self.assertEqual(decode((Path(first['path'])/artifacts[0]['path']).read_text(encoding='utf-8'))['text'],'JARVIS 中文')

if __name__=='__main__':unittest.main()
