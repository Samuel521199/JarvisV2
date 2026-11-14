"""Real goal/task/completion ledger; candidate audit is not promoted knowledge."""
import unittest
from unittest.mock import patch
import test_goal_advice as fixture
from test_goal_plans import proposal
from host import goals,goal_context
from host.completion import refresh,pump,command
from modules.context_knowledge.task_lessons import EVENT,TaskLessons
from sdk.protocol import canonical,decode


class TaskLessonTests(unittest.TestCase):
    setUp=fixture.GoalAdvice.setUp
    tearDown=fixture.GoalAdvice.tearDown
    publish=fixture.GoalAdvice.publish
    req=fixture.GoalAdvice.req
    detail=fixture.GoalAdvice.detail
    plan=fixture.GoalAdvice.plan
    code=fixture.GoalAdvice.code
    source=fixture.GoalAdvice.source
    seed=fixture.GoalAdvice.seed
    create=fixture.GoalAdvice.create
    edit_source=fixture.GoalAdvice.edit_source
    rules=fixture.GoalAdvice.rules

    def finish(self,request='lesson-main',text='Jarvis 中文',enabled=True,expected=None,complete=True):
        ident=self.create(request_id=request,input_text=text,enabled=enabled)
        self.plan(ident,[proposal(text)])
        rules=self.rules(text.upper() if expected is None else expected)
        if not complete:rules={'coverage':'recipe','criteria':rules['criteria']}
        tid=goals.command(self.root,{'action':'approve','id':ident,'revision':self.detail(ident)['plan']['revision'],'acceptance':rules})['task_id']
        self.core.run_task(tid)
        return ident,tid

    def events(self,tid):return self.core.db.all('SELECT data FROM events WHERE task_id=? AND kind=? ORDER BY seq',(tid,EVENT))

    def test_existing_pump_collects_candidate_once_without_promoting_or_copying_content(self):
        text='Private original sentence 937-A'
        ident,tid=self.finish(text=text)
        with self.core.db.transaction() as tx:tx.execute('UPDATE task_completion SET checked=0 WHERE task_id=?',(tid,))
        before={table:self.core.db.all('SELECT * FROM '+table) for table in ('facts','knowledge_sources','memory_candidates','model_calls','grants','tasks')}
        pump(self.core);result=refresh(self.core,tid)['learning_candidate']
        self.assertEqual(result['state'],'CANDIDATE');self.assertEqual(result['condition_score'],100)
        self.assertFalse(result['automatic_promotion']);self.assertFalse(result['retrievable_as_memory']);self.assertFalse(result['execution_authorized'])
        self.assertIsNone(result['independent_successes']);self.assertIsNone(result['causal_contribution'])
        self.assertEqual(len(self.events(tid)),1)
        raw=self.events(tid)[0]['data'];self.assertNotIn(text,raw);self.assertNotIn(text.upper(),raw)
        self.assertNotIn(self.req()['goal'],raw)
        for table,rows in before.items():self.assertEqual(self.core.db.all('SELECT * FROM '+table),rows,table)
        for _ in range(3):refresh(self.core,tid)
        self.assertEqual(len(self.events(tid)),1)

    def test_identical_input_does_not_increase_distinct_inputs_or_independent_votes(self):
        _,a=self.finish('lesson-first','alpha');_,b=self.finish('lesson-repeat','alpha');_,c=self.finish('lesson-new','beta')
        result=refresh(self.core,c)['learning_candidate']
        self.assertEqual(result['history']['observations'],3);self.assertEqual(result['history']['distinct_inputs'],2)
        self.assertEqual(result['history']['states']['CANDIDATE'],3)
        self.assertFalse(result['history']['live_revalidated']);self.assertIsNone(result['independent_successes'])
        self.assertEqual(refresh(self.core,a)['learning_candidate']['family'],result['family'])

    def test_late_feedback_updates_candidate_and_exposes_counterevidence_to_same_procedure(self):
        _,a=self.finish('lesson-feedback-a');_,b=self.finish('lesson-feedback-b','new value')
        current=refresh(self.core,a)
        command(self.core,{'action':'completion_feedback','id':a,'request_id':'lesson-rejection','fingerprint':current['fingerprint'],
            'kind':'reject','note':'Secret feedback must not enter the method candidate.'})
        current=refresh(self.core,a)['learning_candidate'];self.assertEqual(current['state'],'COUNTEREVIDENCE')
        self.assertEqual(current['condition_score'],100)  # A condition score is not a quality vote.
        self.assertNotIn('Secret feedback',self.events(a)[-1]['data'])
        other=refresh(self.core,b)['learning_candidate'];self.assertEqual(other['next_step'],'resolve_counterevidence')
        self.assertEqual(other['history']['states']['COUNTEREVIDENCE'],1)
        self.assertFalse(other['automatic_promotion'])

    def test_withdrawal_and_memory_opt_out_cannot_reactivate_candidate(self):
        evidence,_,_=self.seed();ident,tid=self.finish()
        self.assertEqual(refresh(self.core,tid)['learning_candidate']['state'],'CANDIDATE')
        self.edit_source(evidence['id'],paused=True)
        result=refresh(self.core,tid)['learning_candidate'];self.assertEqual(result['state'],'WITHDRAWN')
        self.assertEqual(result['source_error'],'goal_context_changed')
        with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET enabled=0 WHERE goal_id=?',(ident,))
        result=refresh(self.core,tid)['learning_candidate'];self.assertEqual(result['state'],'WITHDRAWN')
        self.assertEqual(result['source_error'],'memory_disabled')
        _,other=self.finish('lesson-opted-out',enabled=False)
        self.assertIsNone(refresh(self.core,other)['learning_candidate']);self.assertEqual(self.events(other),[])

    def test_incomplete_checks_and_failed_checks_are_distinguished(self):
        _,partial=self.finish('lesson-partial',complete=False)
        value=refresh(self.core,partial)['learning_candidate'];self.assertEqual(value['state'],'INCOMPLETE')
        self.assertEqual(value['next_step'],'complete_acceptance')
        _,bad=self.finish('lesson-wrong',expected='INCORRECT')
        value=refresh(self.core,bad)['learning_candidate'];self.assertEqual(value['state'],'COUNTEREVIDENCE')
        self.assertEqual(value['condition_score'],0)

    def test_no_goal_memory_context_does_not_silently_create_learning_records(self):
        ident=goals.command(self.root,{'action':'create','request':self.req()})['id']
        self.plan(ident);tid=goals.command(self.root,{'action':'approve','id':ident,'revision':self.detail(ident)['plan']['revision'],'acceptance':self.rules()})['task_id']
        self.core.run_task(tid)
        self.assertIsNone(refresh(self.core,tid)['learning_candidate']);self.assertEqual(self.events(tid),[])

    def test_scope_and_bound_literals_are_not_silently_generalized(self):
        from modules.context_knowledge.task_lessons import describe
        from modules.task_resource.plans import Plans
        ident,tid=self.finish();task=self.core.tasks.get(tid);plan=Plans(self.core.db).get(ident);context=goal_context.get(self.core,ident)
        completion=refresh(self.core,tid);a=describe(task,plan,context,completion)
        b=describe(task,plan,{**context,'scope':'project:other'},completion)
        self.assertNotEqual(a['family'],b['family'])
        task['body']['steps'][0]['arguments']['text']='a bound constant'
        c=describe(task,plan,context,completion)
        self.assertNotEqual(a['family'],c['family']);self.assertNotIn('a bound constant',canonical(c))
        with self.core.db.transaction() as tx:self.core.db.event(tx,'other-scope',EVENT,{**a,'scope':'project:other'})
        self.assertEqual(TaskLessons(self.core.db).projection(a)['history']['observations'],1)

    def test_reconciliation_after_missed_observation_and_transaction_rollback(self):
        with patch('host.completion.learning_candidate',return_value=None):ident,tid=self.finish()
        self.assertEqual(self.events(tid),[])
        with self.assertRaises(RuntimeError):
            with self.core.db.transaction() as tx:
                refresh(self.core,tid,transaction=tx);raise RuntimeError('rollback fixture')
        self.assertEqual(self.events(tid),[])
        with self.core.db.transaction() as tx:tx.execute('UPDATE task_completion SET checked=0 WHERE task_id=?',(tid,))
        pump(self.core);self.assertEqual(len(self.events(tid)),1)

    def test_history_limit_is_explicit_and_never_claims_independent_support(self):
        _,tid=self.finish();value=decode(self.events(tid)[-1]['data'])
        with self.core.db.transaction() as tx:
            for i in range(201):self.core.db.event(tx,'bounded-history-'+str(i),EVENT,{**value,'family':'different'})
        result=TaskLessons(self.core.db).projection(value)
        self.assertTrue(result['history']['window_truncated'])
        self.assertEqual(result['next_step'],'review_history_window')
        self.assertEqual(result['history']['observations'],0)
        self.assertIsNone(result['independent_successes']);self.assertFalse(result['automatic_promotion'])

if __name__=='__main__':unittest.main()
