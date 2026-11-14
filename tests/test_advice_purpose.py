"""New selector semantics opt in only behind a compatible installed controller."""
import copy,unittest
from unittest.mock import patch
import test_goal_advice as f
from host import goal_context
from host.planning_advice import PlanningAdvice
from modules.task_resource.advice_scope import inspect,selectors
from sdk.protocol import canonical

class PurposeAdvice(unittest.TestCase):
    setUp=f.GoalAdvice.setUp
    tearDown=f.GoalAdvice.tearDown
    publish=f.GoalAdvice.publish
    req=f.GoalAdvice.req
    detail=f.GoalAdvice.detail
    plan=f.GoalAdvice.plan
    code=f.GoalAdvice.code
    seed=f.GoalAdvice.seed
    source=f.GoalAdvice.source
    create=f.GoalAdvice.create
    edit_source=f.GoalAdvice.edit_source
    goal='整理当前资料，原样摘录每条原文，保留来源ID和顺序，不概括，保存报告'
    data={'schema':'jarvis.notes-input.v1','sources':[{'id':'source-note-A','text':'暂估 81 元，尚未确认。'}]}

    def current(self,ident='purpose-01',goal=None,data=None):
        with patch.object(PlanningAdvice,'writer_version',return_value=3):
            return self.create(request_id='purpose-request-'+ident,goal=goal or self.goal,input_text=canonical(self.data if data is None else data))

    def method(self):
        return self.seed(requires={'channel':'task','input_schema':'jarvis.notes-input.v1','task_purpose':'notes-excerpt-v1'})

    def test_scoped_method_selected_and_generic_card_omitted_without_erasing_facts(self):
        self.seed();generic=self.current('generic');self.assertIsNone(self.detail(generic)['planning_advice'])
        self.method();specific=self.current('specific');view=self.detail(specific)['planning_advice']
        self.assertEqual(view['version'],3);self.assertTrue(view['current']);self.assertEqual(len(view['offered']),1)
        self.assertTrue(goal_context.get(self.core,specific)['view']['facts'])

    def test_contradictory_unknown_clause_and_other_domain_do_not_receive_notes_method(self):
        self.method()
        for i,goal in enumerate([self.goal+'，改写为已确认',self.goal.replace('不概括','请概括'),self.goal+'，只保留第一条','Summarize these notes.']):
            with self.subTest(goal=goal):self.assertIsNone(self.detail(self.current('unknown-'+str(i),goal))['planning_advice'])
        self.assertIsNone(self.detail(self.current('practice',data={'schema':'jarvis.practice-input.v1','pairs':[[2,3]]}))['planning_advice'])

    def test_malformed_schema_spoofing_and_duplicate_sources_do_not_match(self):
        self.method()
        for i,data in enumerate([{'schema':'jarvis.notes-input.v1'},dict(self.data,extra=True),dict(self.data,sources=self.data['sources']*2),{'schema':['jarvis.notes-input.v1']}]):
            with self.subTest(data=data):self.assertIsNone(self.detail(self.current('bad-'+str(i),data=data))['planning_advice'])

    def test_practice_grammar_validates_numbers_and_does_not_claim_mastery(self):
        goal='生成当前乘法练习和正确答案，保留题目顺序，保存练习表，不得声称已经掌握'
        data={'schema':'jarvis.practice-input.v1','pairs':[[18,13],[-7,9]]}
        self.assertEqual(inspect(goal,canonical(data))['task_purpose'],'practice-product-v1')
        self.assertNotIn('task_purpose',inspect(goal+'，给学生评定掌握程度',canonical(data)))
        for value in [True,1.5,10**6+1,'18']:
            self.assertEqual(inspect(goal,canonical({'schema':data['schema'],'pairs':[[value,13]]})),{})

    def test_legacy_selector_and_message_remain_frozen_for_existing_v2(self):
        self.seed();ident=self.create();self.plan(ident);before=goal_context.get(self.core,ident)
        self.assertEqual(before['view']['conditional_advice']['version'],2)
        self.assertTrue(self.detail(ident)['planning_advice']['current'])
        self.assertEqual(goal_context.get(self.core,ident),before)
        row={'request':{'goal':self.goal,'input_text':canonical(self.data)}}
        self.assertNotIn('task_purpose',selectors(row,2));self.assertIn('task_purpose',selectors(row,3))

    def test_new_semantics_recheck_source_and_current_goal_before_dispatch(self):
        evidence,_,_=self.method();ident=self.current();self.edit_source(evidence['id'],paused=True)
        result,p=self.plan(ident);self.assertEqual(result['error'],'goal_context_changed');self.assertEqual(p.prompts,[])

    def test_writer_requires_protocol4_and_preserves_unmanaged_v2(self):
        self.assertEqual(PlanningAdvice.writer_version(self.root),2)
        marker=self.root/'deployment/controller-protocol.json';marker.parent.mkdir(exist_ok=True);marker.write_text('{"schema":1,"minimum":3}')
        for protocol,version in [(2,1),(3,2),(4,3)]:
            with patch('control.controller_pin.read',return_value={'controller_protocol':protocol}):
                self.assertEqual(PlanningAdvice.writer_version(self.root),version)

    def test_v3_model_message_cached_resume_preserves_call_and_grant(self):
        from test_goal_plans import proposal
        self.method();ident=self.current();result,p=self.plan(ident,[proposal(canonical(self.data))])
        self.assertEqual(result['status'],'REVIEW');self.assertIn('notes-excerpt-v1',p.prompts[0])
        calls=self.core.db.all('SELECT * FROM model_calls');grants=self.core.db.all('SELECT * FROM grants')
        with self.core.db.transaction() as tx:tx.execute("UPDATE goal_plans SET status='WAITING' WHERE id=?",(ident,))
        result,p=self.plan(ident);self.assertEqual(result['status'],'REVIEW');self.assertEqual(p.prompts,[])
        self.assertEqual(calls,self.core.db.all('SELECT * FROM model_calls'));self.assertEqual(grants,self.core.db.all('SELECT * FROM grants'))

    def test_current_and_historical_v3_require_reader3(self):
        import json
        from control.application_compatibility import require_compatible
        from sdk.protocol import CoreError
        self.method();ident=self.current();package=self.root/'reader';(package/'config').mkdir(parents=True)
        (package/'config/conditional-advice-compatibility.json').write_text('{"schema":1,"conditional_advice_schema":1}')
        marker=package/'config/goal-advice-compatibility.json'
        for historical in (False,True):
            if historical:
                context=goal_context.get(self.core,ident)
                with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=?,history=? WHERE goal_id=?',('{}',canonical([context['view']]),ident))
            for reader in (1,2,3):
                marker.write_text(json.dumps({'schema':1,'goal_advice_schema':reader}))
                if reader<3:
                    with self.assertRaises(CoreError):require_compatible(self.root,package)
                else:self.assertEqual(require_compatible(self.root,package)['required']['goal_advice_schema'],3)

if __name__=='__main__':unittest.main()
