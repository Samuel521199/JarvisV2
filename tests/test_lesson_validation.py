"""Real restricted workers, host-owned oracles, durable budgets and no promotion."""
import json,time,unittest
from unittest.mock import patch
import test_task_lessons as fixture
from host import goals
from host.completion import refresh
from host.lesson_validation import run,advance,key_for
from modules.context_knowledge.lesson_trials import LessonTrials,START
from modules.task_resource.lesson_checks import challenges,score
from control.worker.runtime import RestrictedWorker
from sdk.protocol import CoreError,canonical

TOOLS={
 'notes':('整理资料，原样摘录每条原文，保留来源ID和顺序',
  {'schema':'jarvis.notes-input.v1','sources':[{'id':'original-a','text':'草稿：91元，未确认。'}]},
  "result={'schema':'jarvis.notes-result.v1','excerpts':v['sources']}"),
 'practice':('生成当前乘法练习和正确答案，保留题目顺序',
  {'schema':'jarvis.practice-input.v1','pairs':[[6,7]]},
  "result={'schema':'jarvis.practice-result.v1','exercises':[{'a':a,'b':b,'answer':a*b} for a,b in v['pairs']]}"),
 'quote':('比较报价，预算不超过200元，交期不超过7天，在合格报价中选择最低价，保留来源引用，保存报告',
  {'schema':'jarvis.quote-input.v1','currency':'CNY','max_price_minor':20000,'max_delivery_days':7,
   'offers':[{'id':'original-q','price_minor':19100,'delivery_days':6,'source':'synthetic:original-q'}]},
  "offers=[o for o in v['offers'] if o['price_minor']<=v['max_price_minor'] and o['delivery_days']<=v['max_delivery_days']]\n    chosen=min(offers,key=lambda o:o['price_minor']) if offers else None\n    result={'schema':'jarvis.quote-result.v1','eligible_ids':[o['id'] for o in offers],'selected_id':chosen['id'] if chosen else None,'selected_source':chosen['source'] if chosen else None}")
}


class LessonValidationTests(unittest.TestCase):
    setUp=fixture.TaskLessonTests.setUp
    tearDown=fixture.TaskLessonTests.tearDown
    publish=fixture.TaskLessonTests.publish
    req=fixture.TaskLessonTests.req
    detail=fixture.TaskLessonTests.detail
    plan=fixture.TaskLessonTests.plan
    code=fixture.TaskLessonTests.code
    source=fixture.TaskLessonTests.source
    seed=fixture.TaskLessonTests.seed
    create=fixture.TaskLessonTests.create
    edit_source=fixture.TaskLessonTests.edit_source
    rules=fixture.TaskLessonTests.rules

    def candidate(self,domain='practice',overfit=False,stages=1):
        goal,data,logic=TOOLS[domain];text=canonical(data)
        source="import json\ndef run(text):\n    v=json.loads(text)\n    "+logic+"\n    return json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))\n"
        # Test fixture computes the original output; validation uses separate
        # host oracles on newly generated inputs, never this fixture function.
        ns={};exec(source,ns);expected=ns['run'](text)
        if overfit:source='def run(text):\n    return '+repr(expected)+'\n'
        cap='plugin.lesson-'+domain+'.v1'
        spec={'schema':'jarvis.development.v1','request_id':'lesson-tool-'+domain,'principal_id':'owner.local','scope_id':'personal','grant_id':'development-test',
            'goal':'Synthetic '+domain,'capability':cap,'description':'Synthetic validation fixture','public_cases':[{'input':text,'expected':expected}],
            'evaluation_cases':[{'input':'\n'+text,'expected':expected}],'sample_input':text,'limits':{'max_attempts':1,'max_model_calls':1,'max_seconds':120}}
        package=self.core.packages.stage({'schema':'jarvis.code-candidate.v1','summary':'Local validation fixture','files':[{'path':'main.py','content':source}]},spec)
        self.assertTrue(self.core.packages.verify(package)['passed']);self.core.packages.activate(package,0)
        ident=self.create(request_id='lesson-goal-'+domain,goal=goal,input_text=text)
        steps=[{'title':'Calculate','capability':cap,'source':'input','expected':'Current structured result'}]
        if stages==2:
            identity='plugin.lesson-identity.v1';spec={**spec,'capability':identity,'request_id':'identity-tool','public_cases':[{'input':'x','expected':'x'}],'evaluation_cases':[{'input':'y','expected':'y'}]}
            p=self.core.packages.stage({'schema':'jarvis.code-candidate.v1','summary':'Identity','files':[{'path':'main.py','content':'def run(text):\n    return text\n'}]},spec)
            self.assertTrue(self.core.packages.verify(p)['passed']);self.core.packages.activate(p,0)
            # Refresh the frozen goal catalog before generating its plan.
            from host.goal_context import amend
            from modules.task_resource.plans import Plans
            amend(self.core,ident,Plans(self.core.db).get(ident)['revision'],goal,text)
            steps.append({'title':'Pass through','capability':identity,'source':'previous','expected':'Unchanged structured result'})
        result,_=self.plan(ident,[{'schema':'jarvis.goal-plan.v1','summary':'Synthetic procedure','input_text':text,'steps':steps,'questions':[]}])
        self.assertEqual(result['status'],'REVIEW')
        rules=self.rules(expected)
        rules['criteria']=[{'id':'output-'+str(i),'step_id':'step-'+str(i),'check':'text_equals','expected':expected} for i in range(1,stages+1)]
        rules['requirements'][0].update(text='Explicit current structured output from every stage',criterion_ids=[c['id'] for c in rules['criteria']])
        tid=goals.command(self.root,{'action':'approve','id':ident,'revision':self.detail(ident)['plan']['revision'],'acceptance':rules})['task_id']
        self.core.run_task(tid);completion=refresh(self.core,tid)
        self.assertEqual(completion['learning_candidate']['state'],'CANDIDATE',completion)
        return ident,tid

    def enable(self,limit=4):
        trials=LessonTrials(self.core.db);return trials.configure({**trials.policy(),'enabled':True,'max_trials_24h':limit})

    def test_three_domains_pass_new_host_owned_cases_without_business_effects(self):
        self.enable()
        for domain in TOOLS:
            with self.subTest(domain=domain):
                _,tid=self.candidate(domain);before={t:self.core.db.all('SELECT * FROM '+t) for t in ('tasks','actions','grants','model_calls','facts','release_slots')}
                result=run(self.root,tid);self.assertEqual(result['status'],'PASSED');self.assertEqual(len(result['cases']),4)
                self.assertEqual(result['cloud_calls'],0);self.assertFalse(result['business_artifacts_written'])
                for table,value in before.items():self.assertEqual(value,self.core.db.all('SELECT * FROM '+table),table)
                candidate=refresh(self.core,tid)['learning_candidate'];self.assertFalse(candidate['retrievable_as_memory'])
                self.assertEqual(candidate['validation']['trial']['result']['status'],'PASSED')

    def test_three_original_successes_do_not_hide_overfit_failures(self):
        self.enable()
        for domain in TOOLS:
            with self.subTest(domain=domain):
                _,tid=self.candidate(domain,overfit=True);self.assertEqual(refresh(self.core,tid)['condition_score'],100)
                result=run(self.root,tid);self.assertEqual(result['status'],'FAILED');self.assertTrue(any(not c['passed'] for c in result['cases']))
                self.assertFalse(result['automatic_promotion'])
                self.assertEqual(refresh(self.core,tid)['learning_candidate']['next_step'],'resolve_validation_failure')

    def test_disabled_policy_and_repeated_family_never_dispatch_extra_worker(self):
        _,tid=self.candidate()
        with patch.object(RestrictedWorker,'run') as worker:
            self.assertEqual(run(self.root,tid)['error'],'lesson_policy');worker.assert_not_called()
        self.enable();self.assertEqual(run(self.root,tid)['status'],'PASSED')
        with patch.object(RestrictedWorker,'run') as worker:
            self.assertEqual(run(self.root,tid)['status'],'existing');worker.assert_not_called()
        self.assertEqual(LessonTrials(self.core.db).used(),1)

    def test_budget_counts_unfinished_reservations_and_policy_toggle_does_not_reset(self):
        _,tid=self.candidate();policy=self.enable(limit=1);trials=LessonTrials(self.core.db)
        with self.core.db.transaction() as tx:trials.reserve(tid,'unknown-trial',{'family':'unknown','source_task':tid},policy['revision'],tx)
        trials.configure({**trials.policy(),'enabled':False});trials.configure({**trials.policy(),'enabled':True})
        with patch.object(RestrictedWorker,'run') as worker:
            self.assertEqual(run(self.root,tid)['error'],'lesson_budget');worker.assert_not_called()
        self.assertEqual(trials.prior('unknown-trial')['state'],'UNKNOWN_OR_RUNNING');self.assertEqual(trials.used(),1)

    def test_revoked_grant_and_stop_prevent_test_execution(self):
        _,tid=self.candidate();self.enable();self.core.gate.stop()
        with patch.object(RestrictedWorker,'run') as worker:
            self.assertEqual(run(self.root,tid)['error'],'stopped');worker.assert_not_called()
        self.core.gate.resume(self.core.gate.token())
        self.core.grants.revoke(self.core.tasks.get(tid)['body']['grant_id'])
        with patch.object(RestrictedWorker,'run') as worker:
            self.assertEqual(run(self.root,tid)['error'],'denied');worker.assert_not_called()
        self.assertEqual(LessonTrials(self.core.db).used(),0)

    def test_policy_revocation_after_reservation_stops_and_keeps_charge(self):
        _,tid=self.candidate();self.enable();trials=LessonTrials(self.core.db)
        def revoked(worker,files,inputs,checkpoint,seconds):
            trials.configure({**trials.policy(),'enabled':False});checkpoint()
        with patch.object(RestrictedWorker,'run',revoked):result=run(self.root,tid)
        self.assertEqual(result,{'status':'INTERRUPTED','error':'lesson_policy'});self.assertEqual(trials.used(),1)
        self.assertEqual(refresh(self.core,tid)['learning_candidate']['validation']['trial']['result']['status'],'INTERRUPTED')

    def test_missing_finish_never_automatically_replays_and_foreground_wins(self):
        _,tid=self.candidate();policy=self.enable();candidate=refresh(self.core,tid)['learning_candidate'];trials=LessonTrials(self.core.db)
        with self.core.db.transaction() as tx:trials.reserve(tid,key_for(candidate),{'family':candidate['family'],'source_task':tid},policy['revision'],tx)
        class Lane:
            def state(self):return {'status':'idle'}
            def submit(self,*a):raise AssertionError('must not start')
        self.assertIsNone(advance(self.root,Lane()));self.assertIsNone(advance(self.root,Lane(),interrupted=lambda:True))
        with patch.object(RestrictedWorker,'run') as worker:
            self.assertEqual(run(self.root,tid)['status'],'existing');worker.assert_not_called()

    def test_two_stage_pipeline_is_tested_in_order_with_two_bounded_batches(self):
        _,tid=self.candidate(stages=2);self.enable();result=run(self.root,tid)
        self.assertEqual(result['status'],'PASSED');self.assertEqual(len(result['workers']),2)

    def test_existing_background_lane_runs_once_and_foreground_defers(self):
        from host.background import BackgroundLane
        _,tid=self.candidate();self.enable();lane=BackgroundLane(self.root)
        try:
            self.assertIsNone(advance(self.root,lane,interrupted=lambda:True))
            self.assertIsNone(lane.future)
            self.assertEqual(advance(self.root,lane)['id'],tid)
            self.assertEqual(lane.future.result(timeout=45)['status'],'PASSED')
            self.assertIsNone(advance(self.root,lane))
            self.assertEqual(LessonTrials(self.core.db).used(),1)
        finally:lane.close()

    def test_malformed_optional_policy_does_not_break_task_assessment(self):
        from modules.context_knowledge.lesson_trials import POLICY_KEY
        _,tid=self.candidate()
        with self.core.db.transaction() as tx:tx.execute('INSERT INTO meta VALUES(?,?)',(POLICY_KEY,'{"enabled":true}'))
        result=refresh(self.core,tid)
        self.assertEqual(result['condition_score'],100)
        self.assertEqual(result['learning_candidate']['validation']['policy_error'],'invalid_policy')
        with patch.object(RestrictedWorker,'run') as worker:
            self.assertEqual(run(self.root,tid)['error'],'lesson_policy');worker.assert_not_called()

    def test_original_scheduler_idle_maintenance_dispatches_local_trial(self):
        from host.background import BackgroundLane
        from host.task_scheduler import TaskRunner
        from host.settings_operations import command
        from test_concurrency import memory_ok
        _,tid=self.candidate();lane=BackgroundLane(self.root);holder={}
        command(self.root,{'action':'lesson_validation_configure',**LessonTrials(self.core.db).policy(),'enabled':True})
        def interrupted():
            runner=holder.get('runner')
            if runner is None or runner.closed:return True
            state=runner.state();return bool(state['active'] or state['queued'])
        runner=TaskRunner(self.root,resource_sample=memory_ok,
            maintenance=lambda:advance(self.root,lane,interrupted=interrupted))
        holder['runner']=runner;runner.wake.set()
        try:
            deadline=time.monotonic()+20
            while lane.future is None and time.monotonic()<deadline:time.sleep(.05)
            self.assertIsNotNone(lane.future)
            self.assertEqual(lane.future.result(timeout=30)['status'],'PASSED')
            self.assertEqual(refresh(self.core,tid)['learning_candidate']['next_step'],'compare_real_tasks')
            self.assertEqual(LessonTrials(self.core.db).used(),1)
        finally:runner.close(drain=False);lane.close()

    def test_incomplete_worker_response_cannot_be_vacuously_passed(self):
        _,tid=self.candidate();self.enable()
        with patch.object(RestrictedWorker,'run',return_value=([],{})):
            result=run(self.root,tid)
        self.assertEqual(result,{'status':'INTERRUPTED','error':'lesson_output'})
        self.assertEqual(LessonTrials(self.core.db).used(),1)

    def test_oracle_rejects_bool_answers_extra_mastery_and_rewritten_sources(self):
        cases=challenges('practice-product-v1','0'*32);source=json.loads(cases[0]['input'])
        value={'schema':'jarvis.practice-result.v1','exercises':[{'a':a,'b':b,'answer':True} for a,b in source['pairs']]}
        self.assertFalse(score('practice-product-v1',cases[0]['input'],canonical(value))['passed'])
        value['exercises']=[{'a':a,'b':b,'answer':a*b} for a,b in source['pairs']]
        value['mastery']='已掌握'
        self.assertFalse(score('practice-product-v1',cases[0]['input'],canonical(value))['passed'])
        case=challenges('notes-excerpt-v1','1'*32)[0];source=json.loads(case['input']);source['sources'][0]['text']='已确认'
        self.assertFalse(score('notes-excerpt-v1',case['input'],canonical({'schema':'jarvis.notes-result.v1','excerpts':source['sources']}))['passed'])

if __name__=='__main__':unittest.main()
