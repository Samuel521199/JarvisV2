"""Goal admission and declared requirement coverage: positive paths and counterexamples."""
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import test_core as base
from test_core import task
import test_goal_plans as goal_base
from test_concurrency import memory_ok, until
from host import goals, memory
from host.core import Core
from host.completion import refresh, command
from host.task_scheduler import TaskRunner
from modules.task_resource.completion import Completion
from modules.task_resource.scheduling import Scheduling
from sdk.protocol import CoreError, canonical, decode
proposal, ROOT = goal_base.proposal, goal_base.ROOT


class WorkflowHandoff(unittest.TestCase):
    setUp = goal_base.GoalPlans.setUp
    tearDown = goal_base.GoalPlans.tearDown
    publish = goal_base.GoalPlans.publish
    req = goal_base.GoalPlans.req
    create = goal_base.GoalPlans.create
    detail = goal_base.GoalPlans.detail
    code = goal_base.GoalPlans.code

    def prepared(self, **changes):
        ident = self.create(**changes)
        goals.command(self.root, {'action':'edit','id':ident,'revision':self.detail(ident)['plan']['revision'],
                                 'proposal':proposal()})
        return {'action':'approve_and_run','id':ident,'revision':self.detail(ident)['plan']['revision']}

    def full_queue(self):
        store = Scheduling(self.core.db)
        store.configure({**store.policy(), 'queue_limit':4})
        ids = [self.core.tasks.submit(task('capacity-'+str(i))) for i in range(4)]
        store.enqueue(ids)
        return store, ids

    def test_single_request_persists_and_runner_restarts_without_ui_start(self):
        request = self.prepared()
        first = goals.command(self.root, request)
        self.assertEqual(first['dispatch']['state'], 'QUEUED')
        self.core.close(); self.core = Core(self.root)
        runner = TaskRunner(self.root, resource_sample=memory_ok)
        try:
            until(lambda: self.core.tasks.get(first['task_id'])['status']=='SUCCEEDED')
        finally:
            runner.close()
        before = self.core.tasks.actions(first['task_id'])
        repeated = goals.command(self.root, request)
        self.assertTrue(repeated['existing'])
        self.assertEqual(repeated['task_id'], first['task_id'])
        self.assertEqual(self.core.tasks.actions(first['task_id']), before)
        self.assertEqual(self.core.db.one('SELECT COUNT(*) AS n FROM tasks')['n'], 1)
        self.assertEqual(len(self.core.db.all("SELECT * FROM events WHERE kind='scheduler.execution_requested'")), 1)

    def test_approve_only_remains_unqueued_and_cannot_silently_change_intent(self):
        request = self.prepared()
        first = goals.command(self.root, {**request, 'action':'approve'})
        self.assertEqual(Scheduling(self.core.db).pending(), [])
        self.code('conflict', goals.command, self.root, request)
        self.assertEqual(self.core.tasks.get(first['task_id'])['status'], 'READY')

    def test_full_queue_retains_intent_and_promotes_once_after_capacity_returns(self):
        store, ids = self.full_queue(); request = self.prepared()
        first = goals.command(self.root, request); ident = first['task_id']
        self.assertEqual(first['dispatch']['state'], 'WAITING_CAPACITY')
        self.assertEqual(len(store.pending()), 4)
        self.assertEqual(goals.command(self.root, request)['task_id'], ident)
        self.core.close(); self.core=Core(self.root); store=Scheduling(self.core.db)
        store.mark(ids[0], finished=True); store.admit_waiting(); store.admit_waiting()
        self.assertEqual(store.intent(ident)['state'], 'QUEUED')
        self.assertEqual(len(store.pending()), 4)
        self.assertEqual(len(self.core.db.all("SELECT * FROM events WHERE task_id=? AND kind='scheduler.queued'",(ident,))),1)

    def test_capacity_wait_cancellation_never_revives(self):
        store, ids=self.full_queue(); request=self.prepared(); ident=goals.command(self.root,request)['task_id']
        goals.command(self.root, {'action':'cancel','id':request['id']})
        store.mark(ids[0],finished=True); store.admit_waiting()
        self.assertEqual(store.intent(ident)['state'],'NOT_PENDING')
        self.assertEqual(self.core.tasks.actions(ident),[])
        self.code('conflict',goals.command,self.root,request)

    def test_revocation_after_atomic_admission_still_fences_execution(self):
        request=self.prepared(); ident=goals.command(self.root,request)['task_id']
        self.core.grants.revoke(self.core.tasks.get(ident)['body']['grant_id'])
        result=self.core.run_task(ident)
        self.assertNotEqual(result['status'],'SUCCEEDED')
        self.assertFalse(any(a['status']=='CONFIRMED' for a in self.core.tasks.actions(ident)))

    def test_expired_capacity_wait_remains_visible_but_is_not_promoted(self):
        store,ids=self.full_queue(); request=self.prepared(); ident=goals.command(self.root,request)['task_id']
        self.core.db.connection.execute('UPDATE tasks SET deadline=0 WHERE id=?',(ident,))
        store.mark(ids[0],finished=True);store.admit_waiting()
        self.assertEqual(store.intent(ident),{'state':'NOT_PENDING','reason':'deadline'})
        self.assertEqual(self.core.tasks.actions(ident),[])

    def test_contains_cannot_verify_a_literal_requirement_and_contradiction_fails(self):
        request=self.prepared()
        rules={'coverage':'complete','criteria':[{'id':'contains','step_id':'step-1','check':'text_contains','expected':'JARVIS'}],
               'requirements':[{'id':'whole','text':'完整原样输出','kind':'literal','criterion_ids':['contains']}]}
        ident=goals.command(self.root,{**request,'acceptance':rules})['task_id'];self.core.run_task(ident)
        result=refresh(self.core,ident)
        self.assertEqual(result['state'],'SATISFIED')
        self.assertEqual(result['requirement_coverage']['requirements'][0]['reason'],'unsupported_verifier')

    def test_intent_limit_rolls_back_task_grant_and_goal_admission(self):
        request=self.prepared()
        with patch('modules.task_resource.scheduling.INTENT_LIMIT',0):
            self.code('task_capacity',goals.command,self.root,request)
        self.assertEqual(self.detail(request['id'])['plan']['status'],'REVIEW')
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        self.assertIsNone(self.core.db.one('SELECT id FROM grants WHERE id=?',(request['id']+'-execute',)))

    def crash(self, mode):
        request=self.prepared(); (self.root/'handoff-crash-fixture.json').write_text(json.dumps({
            'fixture_root':str(self.root),'request':request}),encoding='utf-8')
        self.core.close()
        try:
            result=subprocess.run([sys.executable,'-m','tools.handoff_crash_worker',str(self.root),mode],cwd=ROOT,
                                  capture_output=True,text=True,timeout=20,
                                  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        finally:self.core=Core(self.root)
        self.assertEqual(result.returncode,91 if mode=='before' else 92,result.stderr)
        self.assertEqual(self.core.db.integrity(),'ok')
        return request

    def test_real_process_exit_before_commit_leaves_no_orphan(self):
        request=self.crash('before')
        self.assertEqual(self.detail(request['id'])['plan']['status'],'REVIEW')
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        self.assertEqual(self.core.db.all('SELECT * FROM task_dispatch'),[])
        self.assertIsNone(self.core.db.one('SELECT id FROM grants WHERE id=?',(request['id']+'-execute',)))

    def test_real_process_exit_after_commit_retry_keeps_one_task_and_intent(self):
        request=self.crash('after')
        result=goals.command(self.root,request)
        self.assertTrue(result['existing'])
        self.assertEqual(len(self.core.db.all('SELECT * FROM tasks')),1)
        self.assertEqual([r['task_id'] for r in Scheduling(self.core.db).pending()],[result['task_id']])

    def test_weak_goal_candidate_is_execution_observation_not_verified_business_fact(self):
        request=self.prepared(goal='完成需要核对含义的业务目标')
        request['acceptance']={'coverage':'complete','criteria':[{'id':'contains','step_id':'step-1',
            'check':'text_contains','expected':'JARVIS'}]}
        ident=goals.command(self.root,request)['task_id'];self.core.run_task(ident)
        result=refresh(self.core,ident)
        self.assertEqual(result['state'],'SATISFIED');self.assertFalse(result['requirement_coverage']['complete'])
        _,text,_=memory.goal_source(self.root,request['id'])
        self.assertIn('执行观察',text);self.assertIn('目标要求覆盖尚未证实',text)
        self.assertNotIn('已通过实际执行完成',text)
        command(self.core,{'action':'completion_feedback','id':ident,'request_id':'reject-gap','fingerprint':result['fingerprint'],
                          'kind':'reject','note':'遗漏了业务限制'})
        self.code('memory_source_changed',memory.goal_source,self.root,request['id'])

    def test_long_goal_candidate_keeps_evidence_limits_when_truncated(self):
        request=self.prepared(goal='详'*4000)
        ident=goals.command(self.root,request)['task_id'];self.core.run_task(ident)
        _,text,_=memory.goal_source(self.root,request['id'])
        self.assertEqual(len(text),4000)
        self.assertIn('目标要求覆盖尚未证实',text)
        self.assertIn('其他输入仍需核对',text)


class RequirementCoverage(unittest.TestCase):
    setUp=base.CoreCase.setUp
    tearDown=base.CoreCase.tearDown

    def configured(self, requirements, *, complete=True):
        ident=self.core.tasks.submit(task('coverage',artifact=True)); store=Completion(self.core.db)
        old=store.criteria(ident)
        rules={**old['rules'],'coverage':'complete' if complete else 'recipe','requirements':requirements}
        store.configure(ident,old['revision'],rules)
        self.core.run_task(ident)
        return ident,refresh(self.core,ident)

    @staticmethod
    def requirement(**changes):
        return {'id':'stats','text':'核对本次文本统计','kind':'statistics','criterion_ids':['statistics'],**changes}

    def test_supported_explicit_requirements_verify_with_bounded_scope(self):
        ident,result=self.configured([self.requirement()])
        self.assertEqual(result['state'],'VERIFIED')
        self.assertTrue(result['requirement_coverage']['complete'])
        self.assertFalse(result['requirement_coverage']['semantic_goal_verified'])
        self.assertEqual(result['condition_score'],100)

    def test_missing_mapping_keeps_goal_unknown_even_when_checks_pass(self):
        _,result=self.configured([self.requirement(),self.requirement(id='delivery',text='五天内交付',kind='semantic',criterion_ids=[])])
        self.assertEqual(result['state'],'SATISFIED')
        self.assertEqual(result['requirement_coverage']['requirements'][1]['reason'],'unmapped')
        self.assertFalse(result['requirement_coverage']['complete'])

    def test_wrong_verifier_does_not_prove_a_semantic_requirement(self):
        _,result=self.configured([self.requirement(kind='semantic',text='业务结论正确')])
        self.assertEqual(result['requirement_coverage']['requirements'][0]['reason'],'unsupported_verifier')
        self.assertEqual(result['state'],'SATISFIED')

    def test_partial_declaration_never_claims_full_coverage(self):
        _,result=self.configured([self.requirement()],complete=False)
        self.assertEqual(result['state'],'SATISFIED')
        self.assertFalse(result['requirement_coverage']['complete'])

    def test_required_evidence_cannot_be_changed_after_execution(self):
        ident,result=self.configured([self.requirement()])
        with self.assertRaises(CoreError) as error:
            Completion(self.core.db).configure(ident,result['acceptance']['revision'],{**result['acceptance']['rules'],
                'requirements':[self.requirement(kind='literal')]})
        self.assertEqual(error.exception.code,'acceptance_frozen')

    def test_unknown_references_duplicate_ids_and_malformed_requirements_rejected(self):
        ident=self.core.tasks.submit(task('invalid-coverage',artifact=True));store=Completion(self.core.db);old=store.criteria(ident)
        for requirements in [None,[],[self.requirement(criterion_ids=['missing'])],
                             [self.requirement(),self.requirement()],[self.requirement(kind='invented')]]:
            with self.subTest(requirements=requirements),self.assertRaises(CoreError):
                store.configure(ident,old['revision'],{**old['rules'],'requirements':requirements})
        self.assertEqual(store.criteria(ident),old)

    def test_legacy_schema_upgrade_retains_old_conclusion_before_reassessment(self):
        ident=self.core.tasks.submit(task('legacy-coverage',artifact=True)); self.core.run_task(ident)
        old={**refresh(self.core,ident),'version':'completion-1.0.0','state':'VERIFIED'}
        old.pop('assessment_history',None)
        self.core.db.connection.execute('UPDATE task_completion SET body=? WHERE task_id=?',(canonical(old),ident))
        self.core.db.connection.execute('DROP TABLE completion_history')
        self.core.db.connection.execute("UPDATE meta SET value='1' WHERE key='completion_schema'")
        Completion(self.core.db)
        self.assertEqual(decode(self.core.db.one('SELECT body FROM task_completion WHERE task_id=?',(ident,))['body']),old)
        new=refresh(self.core,ident)
        self.assertEqual(new['state'],'SATISFIED')
        self.assertTrue(any(h['assessment']['version']=='completion-1.0.0' for h in new['assessment_history']))
        count=len(self.core.db.all('SELECT * FROM completion_history'))
        refresh(self.core,ident);self.assertEqual(len(self.core.db.all('SELECT * FROM completion_history')),count)

    def test_feedback_cannot_convert_unsupported_coverage_into_proof(self):
        ident,result=self.configured([self.requirement(kind='semantic')])
        accepted=command(self.core,{'action':'completion_feedback','id':ident,'request_id':'owner-feedback',
                                  'fingerprint':result['fingerprint'],'kind':'accept','note':'认可收到的结果'})
        self.assertEqual(accepted['state'],'ACCEPTED')
        self.assertFalse(accepted['requirement_coverage']['complete'])


if __name__=='__main__':unittest.main()
