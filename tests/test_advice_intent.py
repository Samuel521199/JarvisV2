"""Composed intent, exact residuals, dispatch freeze and old-reader boundaries."""
import json,unittest
from unittest.mock import patch
import test_advice_purpose as prior
from modules.task_resource.advice_intent import analyze
from modules.task_resource.advice_scope import selectors
from host import goal_context
from host.planning_advice import PlanningAdvice
from sdk.protocol import canonical,CoreError


class IntentGrammar(unittest.TestCase):
    def test_slots_combine_in_either_order_without_dropping_original_requirements(self):
        for goal in ('逐字摘录各条原文；保持来源ID与顺序；保存报告',
                     '保留来源编号；保持原始顺序；把这些资料逐条照抄成报告',
                     'Copy each source verbatim. Keep source identifiers. Preserve original order.'):
            with self.subTest(goal=goal):
                view=analyze(goal,'jarvis.notes-input.v1');self.assertTrue(view['matched'])
                self.assertEqual(view['slots'],{'operation':'copy','fidelity':'verbatim','source_ids':'keep','order':'input'})
                self.assertEqual(view['uncovered'],[])

    def test_missing_and_unsupported_constraints_have_exact_diagnostic_spans(self):
        goal='逐字摘录每条原文，保留来源ID和顺序，但只保存已确认的条目'
        result=analyze(goal,'jarvis.notes-input.v1')
        self.assertFalse(result['matched']);self.assertEqual(result['reason'],'uncovered_clause')
        self.assertEqual(len(result['uncovered']),1)
        item=result['uncovered'][0];self.assertEqual(goal[item['start']:item['end']],item['text'])
        self.assertEqual(item['text'],'但只保存已确认的条目')
        missing=analyze('逐字摘录每条原文','jarvis.notes-input.v1')
        self.assertEqual(set(missing['missing']),{'source_ids','order'})

    def test_negations_quoted_instructions_and_extra_actions_cannot_match_by_substring(self):
        positive='生成当前乘法练习和正确答案，保留题目顺序'
        for goal in ('不要'+positive,'有人说“'+positive+'”','如果有空就'+positive,
                     positive+'，忽略此前要求',positive+'，但答案必须全错',positive+'，发给老师'):
            with self.subTest(goal=goal):self.assertFalse(analyze(goal,'jarvis.practice-input.v1')['matched'])

    def test_schema_and_goal_bounds_are_not_filled_from_source_content(self):
        for goal in ('',None,'a'*2001,('保存报告，'*33)):
            self.assertFalse(analyze(goal,'jarvis.notes-input.v1')['matched'])
        self.assertFalse(analyze('生成当前乘法练习和正确答案，保留题目顺序','jarvis.notes-input.v1')['matched'])
        self.assertFalse(analyze('copy each source verbatim','unknown')['matched'])


class IntentIntegration(unittest.TestCase):
    setUp=prior.PurposeAdvice.setUp
    tearDown=prior.PurposeAdvice.tearDown
    publish=prior.PurposeAdvice.publish
    req=prior.PurposeAdvice.req
    detail=prior.PurposeAdvice.detail
    plan=prior.PurposeAdvice.plan
    code=prior.PurposeAdvice.code
    seed=prior.PurposeAdvice.seed
    source=prior.PurposeAdvice.source
    create=prior.PurposeAdvice.create
    edit_source=prior.PurposeAdvice.edit_source
    method=prior.PurposeAdvice.method
    data=prior.PurposeAdvice.data
    goal='把这些资料按原顺序逐条原样引用，附上各自来源ID，不要总结。'

    def current(self,ident='intent-main',goal=None,version=4):
        with patch.object(PlanningAdvice,'writer_version',return_value=version):
            return self.create(request_id='intent-request-'+ident,goal=goal or self.goal,input_text=canonical(self.data))

    def test_v4_selects_composed_purpose_without_reinterpreting_v3(self):
        self.method();old=self.current('old',version=3);self.assertIsNone(self.detail(old)['planning_advice'])
        new=self.current();result=self.detail(new)['planning_advice']
        self.assertEqual(result['version'],4);self.assertTrue(result['current'])
        self.assertFalse(result['execution_authorized']);self.assertFalse(result['automatic_promotion'])
        context=goal_context.get(self.core,new);self.assertEqual(context['view']['conditional_advice']['selectors']['task_purpose'],'notes-excerpt-v1')
        self.assertTrue(context['view']['facts']);self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])

    def test_v3_already_dispatched_context_resumes_with_original_bytes(self):
        from test_goal_plans import proposal
        self.method();ident=self.current('legacy',goal=prior.PurposeAdvice.goal,version=3)
        result,p=self.plan(ident,[proposal(canonical(self.data))]);self.assertEqual(result['status'],'REVIEW')
        before=goal_context.get(self.core,ident);calls=self.core.db.all('SELECT * FROM model_calls');grants=self.core.db.all('SELECT * FROM grants')
        with self.core.db.transaction() as tx:tx.execute("UPDATE goal_plans SET status='WAITING' WHERE id=?",(ident,))
        result,p=self.plan(ident);self.assertEqual(result['status'],'REVIEW');self.assertEqual(p.prompts,[])
        self.assertEqual(goal_context.get(self.core,ident),before)
        self.assertEqual(self.core.db.all('SELECT * FROM model_calls'),calls);self.assertEqual(self.core.db.all('SELECT * FROM grants'),grants)

    def test_v4_cached_resume_and_withdrawal_still_use_original_model_ledger(self):
        from test_goal_plans import proposal
        evidence,_,_=self.method();ident=self.current()
        result,p=self.plan(ident,[proposal(canonical(self.data))]);self.assertEqual(result['status'],'REVIEW')
        calls=self.core.db.all('SELECT * FROM model_calls');grants=self.core.db.all('SELECT * FROM grants')
        with self.core.db.transaction() as tx:tx.execute("UPDATE goal_plans SET status='WAITING' WHERE id=?",(ident,))
        result,p=self.plan(ident);self.assertEqual(result['status'],'REVIEW');self.assertEqual(p.prompts,[])
        self.edit_source(evidence['id'],paused=True)
        with self.core.db.transaction() as tx:tx.execute("UPDATE goal_plans SET status='WAITING' WHERE id=?",(ident,))
        result,p=self.plan(ident);self.assertEqual(result['error'],'goal_context_changed');self.assertEqual(p.prompts,[])
        self.assertEqual(self.core.db.all('SELECT * FROM model_calls'),calls);self.assertEqual(self.core.db.all('SELECT * FROM grants'),grants)

    def test_controller5_required_for_new_writes_and_reader4_for_current_or_history(self):
        marker=self.root/'deployment/controller-protocol.json';marker.parent.mkdir(exist_ok=True);marker.write_text('{"schema":1,"minimum":4}')
        for protocol,version in ((3,2),(4,3),(5,4)):
            with patch('control.controller_pin.read',return_value={'controller_protocol':protocol}):
                self.assertEqual(PlanningAdvice.writer_version(self.root),version)
        from control.application_compatibility import require_compatible
        self.method();ident=self.current();package=self.root/'reader';(package/'config').mkdir(parents=True)
        (package/'config/conditional-advice-compatibility.json').write_text('{"schema":1,"conditional_advice_schema":1}')
        marker=package/'config/goal-advice-compatibility.json'
        for historical in (False,True):
            if historical:
                context=goal_context.get(self.core,ident)
                with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=?,history=? WHERE goal_id=?',('{}',canonical([context['view']]),ident))
            for reader in (1,2,3,4):
                marker.write_text(json.dumps({'schema':1,'goal_advice_schema':reader}))
                if reader<4:
                    with self.assertRaises(CoreError):require_compatible(self.root,package)
                else:self.assertEqual(require_compatible(self.root,package)['required']['goal_advice_schema'],4)

if __name__=='__main__':unittest.main()
