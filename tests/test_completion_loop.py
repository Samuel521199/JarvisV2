"""End-to-end local acceptance, late correction, reusable methods and durable recovery."""
import time
import unittest
from unittest.mock import patch

import test_core as base
from test_core import task
from test_concurrency import memory_ok,until
from host.core import Core
from host.completion import refresh, pump
from host.settings_operations import command
from host.task_scheduler import TaskRunner
from host.waiting import advance
from modules.task_resource.completion import Completion
from modules.task_resource.scheduling import Scheduling
from modules.task_resource.waiting import Waiting
from sdk.protocol import CoreError,decode


class CompletionLoop(unittest.TestCase):
    setUp=base.CoreCase.setUp
    tearDown=base.CoreCase.tearDown

    def complete(self,key='closed-loop'):
        ident=self.core.tasks.submit(task(key,artifact=True));self.core.run_task(ident);return ident

    def reuse(self,ident,key='reuse-01',text='new input with four words'):
        return command(self.root,{'action':'experience_reuse','id':ident,'request_id':key,'text':text})['task_id']

    def feedback(self,ident,kind,key='feedback-01',note=''):
        current=refresh(self.core,ident)
        return command(self.root,{'action':'completion_feedback','id':ident,'fingerprint':current['fingerprint'],
                                 'kind':kind,'request_id':key,'note':note})

    def test_end_to_end_conditions_feedback_reuse_and_real_new_output(self):
        ident=self.complete();first=refresh(self.core,ident)
        self.assertEqual(first['state'],'SATISFIED');self.assertEqual(first['condition_score'],100)
        self.assertEqual(first['score_scope'],'declared_conditions_only');self.assertTrue(first['method_available'])
        self.assertEqual(self.feedback(ident,'accept')['state'],'ACCEPTED')
        child=self.reuse(ident,text='one two three')
        self.assertEqual(Scheduling(self.core.db).pending()[0]['task_id'],child)
        self.core.run_task(child)
        result=decode(self.core.tasks.actions(child)[0]['result'])
        self.assertEqual(result['words'],3);self.assertEqual(refresh(self.core,child)['state'],'SATISFIED')
        self.assertNotEqual(ident,child)
        self.assertEqual(self.core.db.one('SELECT source_task FROM experience_uses WHERE task_id=?',(child,))['source_task'],ident)
        self.assertEqual(self.core.db.all('SELECT * FROM model_calls'),[])

    def test_complete_label_alone_does_not_prove_requirements_covered(self):
        ident=self.core.tasks.submit(task(artifact=True));criteria=Completion(self.core.db).criteria(ident)
        command(self.root,{'action':'acceptance_set','id':ident,'revision':criteria['revision'],
                          'rules':{**criteria['rules'],'coverage':'complete'}})
        self.core.run_task(ident)
        self.assertEqual(refresh(self.core,ident)['state'],'SATISFIED')
        self.assertFalse(refresh(self.core,ident)['requirement_coverage']['complete'])
        self.assertEqual(self.core.db.all('SELECT * FROM completion_feedback'),[])

    def test_acceptance_is_frozen_before_first_action_and_bad_rules_rejected(self):
        ident=self.core.tasks.submit(task(artifact=True));old=Completion(self.core.db).criteria(ident)
        for rules in ({'coverage':'complete','criteria':[]},{**old['rules'],'extra':'bad'},
                      {'coverage':'complete','criteria':[{'id':'bad','step_id':'missing','check':'text_equals','expected':'x'}]}):
            with self.assertRaises(CoreError):Completion(self.core.db).configure(ident,1,rules)
        self.core.run_task(ident)
        with self.assertRaises(CoreError) as error:Completion(self.core.db).configure(ident,1,old['rules'])
        self.assertEqual(error.exception.code,'acceptance_frozen')

    def test_late_rejection_blocks_queued_adoption_after_restart(self):
        source=self.complete();child=self.reuse(source)
        before=self.core.tasks.actions(source);self.feedback(source,'reject',note='发现遗漏，先停止复用')
        self.core.close();self.core=Core(self.root)
        result=self.core.run_task(child)
        self.assertEqual(result['status'],'WAITING');self.assertEqual(result['error'],'experience_changed')
        self.assertEqual(self.core.tasks.actions(child),[]);self.assertEqual(self.core.tasks.actions(source),before)
        self.assertEqual(refresh(self.core,source)['state'],'NEEDS_CORRECTION')
        with self.assertRaises(CoreError):self.reuse(source,'another')

    def test_late_rejection_invalidates_completed_adoption_without_replaying(self):
        source=self.complete();child=self.reuse(source);self.core.run_task(child);before=self.core.tasks.actions(child)
        self.feedback(source,'reject',note='真实使用发现不适用')
        current=refresh(self.core,child)
        self.assertEqual(current['state'],'INVALIDATED')
        self.assertEqual(self.core.tasks.get(child)['status'],'SUCCEEDED')
        self.assertEqual(self.core.tasks.actions(child),before)

    def test_adoption_feedback_quarantines_the_method_that_was_actually_used(self):
        source=self.complete();child=self.reuse(source);self.core.run_task(child)
        self.feedback(child,'reject',note='新输入下出现问题')
        self.assertFalse(refresh(self.core,source)['method_available'])
        with self.assertRaises(CoreError):self.reuse(source,'later')

    def test_goal_memory_is_excluded_immediately_after_feedback(self):
        from modules.context_knowledge.memory import Memory
        from test_memory_development_ui import fact
        from sdk.protocol import canonical
        source=self.complete();goal='goal-memory-source'
        self.core.db.connection.execute('''INSERT INTO goal_plans(id,request_id,digest,request,catalog,routes,status,task_id,created,deadline)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',(goal,goal,'fixture','{}','[]','[]','ACCEPTED',source,time.time(),time.time()+60))
        memory=Memory(self.core.db);memory.save(fact(key='结果方法'),0,source='goal:'+goal)
        refs=memory.references('personal','openai');self.assertTrue(refs)
        self.feedback(source,'reject',note='方法需要修改')
        self.assertFalse(memory.references_valid('personal','openai',True,refs))

    def test_changed_source_file_blocks_adoption_without_waiting_for_poll(self):
        source=self.complete();child=self.reuse(source)
        receipt=decode(self.core.tasks.actions(source)[-1]['result']);(self.root/receipt['relative_path']).write_text('changed')
        self.assertEqual(self.core.run_task(child)['error'],'experience_changed')
        self.assertEqual(self.core.tasks.actions(child),[])

    def test_method_never_reuses_original_answer_or_stores_input_text(self):
        source=self.complete();self.reuse(source,text='fresh private input')
        rows=self.core.db.all('SELECT * FROM experience_methods')+self.core.db.all('SELECT * FROM experience_sources')
        self.assertNotIn('hello world',str(rows));self.assertNotIn('fresh private input',str(rows))
        self.assertEqual(len(self.core.db.all('SELECT * FROM experience_methods')),1)
        other=self.complete('same-method');self.assertEqual(len(self.core.db.all('SELECT * FROM experience_methods')),1)
        self.assertEqual(len(self.core.db.all('SELECT * FROM experience_sources')),2)

    def test_method_binding_change_or_expiry_requires_fresh_evidence(self):
        source=self.complete();self.core.change_module('text-analyzer','activate',1,'text.scan.v1')
        with self.assertRaises(CoreError):self.reuse(source)
        self.core.change_module('text-analyzer','rollback',2)
        self.core.db.connection.execute('UPDATE experience_methods SET expires=0')
        with self.assertRaises(CoreError):self.reuse(source)

    def test_expired_method_requires_post_expiry_evidence_and_can_be_requalified(self):
        source=self.complete();child=self.reuse(source)
        self.core.db.connection.execute('UPDATE experience_methods SET expires=?',(time.time(),))
        current=refresh(self.core,source);method=current['method']
        self.assertFalse(current['method_available']);self.assertTrue(method['review_required'])
        review={'action':'experience_review','id':source,'revision':method['revision']}
        with self.assertRaises(CoreError):command(self.root,review)
        for i in range(2):
            body=task('after-expiry-'+str(i),artifact=True);body['steps'][0]['arguments']['text']='fresh after expiry '+str(i)
            ident=self.core.tasks.submit(body);self.core.run_task(ident)
            if i==0:
                with self.assertRaises(CoreError):command(self.root,review)
        current=command(self.root,review)
        self.assertTrue(current['method_available']);self.assertFalse(current['method']['review_required'])
        self.assertGreater(current['method']['revision'],method['revision'])
        self.assertEqual(self.core.run_task(child)['error'],'experience_changed')
        new=self.reuse(source,'renewed');self.assertEqual(self.core.run_task(new)['status'],'SUCCEEDED')

    def test_reuse_and_feedback_request_keys_do_not_duplicate_effects(self):
        source=self.complete();child=self.reuse(source);self.core.run_task(child)
        before=self.core.tasks.actions(child)
        self.assertEqual(self.reuse(source),child)
        with self.assertRaises(CoreError):self.reuse(source,text='different')
        first=self.feedback(source,'reject',note='需要修正');self.assertEqual(self.feedback(source,'reject',note='需要修正'),first)
        self.assertEqual(len(self.core.db.all('SELECT * FROM completion_feedback')),1)
        self.assertEqual(self.core.tasks.actions(child),before)

    def test_accepting_feedback_cannot_bless_missing_file(self):
        source=self.complete();receipt=decode(self.core.tasks.actions(source)[-1]['result']);(self.root/receipt['relative_path']).unlink()
        with self.assertRaises(CoreError):self.feedback(source,'accept')
        self.assertEqual(refresh(self.core,source)['state'],'NEEDS_CORRECTION')

    def test_late_acceptance_does_not_unquarantine_old_adoptions(self):
        source=self.complete();child=self.reuse(source);self.feedback(source,'reject',note='需要复核')
        self.feedback(source,'accept','resolved')
        self.assertFalse(refresh(self.core,source)['method_available'])
        self.assertEqual(self.core.run_task(child)['error'],'experience_changed')

    def test_fresh_counterexample_review_allows_growth_but_old_adoptions_stay_fenced(self):
        source=self.complete();child=self.reuse(source);self.feedback(source,'reject',note='需要复核')
        self.feedback(source,'accept','resolved')
        method=refresh(self.core,source)['method']
        with self.assertRaises(CoreError):command(self.root,{'action':'experience_review','id':source,'revision':method['revision']})
        for i in range(2):
            body=task('fresh-'+str(i),artifact=True);body['steps'][0]['arguments']['text']='fresh independent '+str(i)
            ident=self.core.tasks.submit(body);self.core.run_task(ident)
        reviewed=command(self.root,{'action':'experience_review','id':source,'revision':method['revision']})
        self.assertTrue(reviewed['method_available'])
        self.assertEqual(self.core.run_task(child)['error'],'experience_changed')
        new=self.reuse(source,'after-review');self.assertEqual(self.core.run_task(new)['status'],'SUCCEEDED')

    def test_optional_completion_schema_failure_does_not_break_unrelated_execution(self):
        with patch('modules.task_resource.completion.ensure',side_effect=CoreError('completion_schema','fixture')):
            ident=self.complete()
        self.assertEqual(self.core.tasks.get(ident)['status'],'SUCCEEDED')

    def test_disabled_observer_never_closes_or_teaches(self):
        command(self.root,{'action':'outcome_configure','enabled':False});ident=self.complete()
        self.assertEqual(refresh(self.core,ident)['state'],'UNAVAILABLE')
        self.assertEqual(self.core.db.all('SELECT * FROM experience_sources'),[])
        command(self.root,{'action':'outcome_configure','enabled':True})
        self.core.db.connection.execute('UPDATE task_completion SET checked=0')
        pump(self.core)
        self.assertEqual(refresh(self.core,ident)['state'],'SATISFIED')

    def test_optional_outage_preserves_method_revision_but_blocks_dependent_effect(self):
        source=self.complete();child=self.reuse(source);method=refresh(self.core,source)['method']
        command(self.root,{'action':'outcome_configure','enabled':False})
        self.assertEqual(self.core.run_task(child)['error'],'experience_changed')
        self.assertEqual(refresh(self.core,source)['method']['revision'],method['revision'])
        command(self.root,{'action':'outcome_configure','enabled':True})
        self.assertEqual(self.core.run_task(child)['status'],'SUCCEEDED')

    def test_missing_adoption_record_fails_closed_only_for_that_task(self):
        source=self.complete();child=self.reuse(source)
        self.core.db.connection.execute('DELETE FROM experience_uses WHERE task_id=?',(child,))
        self.assertEqual(self.core.run_task(child)['error'],'experience_changed')
        self.assertEqual(self.core.tasks.get(self.complete('unrelated'))['status'],'SUCCEEDED')

    def test_cancelled_task_never_becomes_a_successful_method(self):
        ident=self.core.tasks.submit(task(artifact=True));self.core.tasks.cancel(ident)
        self.assertEqual(refresh(self.core,ident)['state'],'CANCELLED')
        self.assertEqual(self.core.db.all('SELECT * FROM experience_sources'),[])

    def waiting_task(self):
        ident=self.core.tasks.submit(task('module-wait',artifact=True));store=Scheduling(self.core.db);store.enqueue([ident])
        store.mark(ident,started=True);self.core.change_module('text-analyzer','stop',1)
        self.core.run_task(ident);store.mark(ident,finished=True,reason='module_disabled');return ident,store

    def test_module_recovery_before_wait_registration_is_not_lost(self):
        ident,store=self.waiting_task();self.core.change_module('text-analyzer','start',2)
        advance(self.core,store)
        self.assertEqual(store.pending()[0]['task_id'],ident)
        self.assertEqual(self.core.db.one('SELECT state FROM task_waits')['state'],'QUEUED')
        advance(self.core,store);self.assertEqual(len(store.pending()),1)
        self.core.run_task(ident);self.assertEqual(refresh(self.core,ident)['state'],'SATISFIED')

    def test_module_wait_survives_restart_and_uses_real_scheduler(self):
        ident,store=self.waiting_task();advance(self.core,store)
        self.core.close();self.core=Core(self.root);self.core.change_module('text-analyzer','start',2)
        runner=TaskRunner(self.root,resource_sample=memory_ok)
        try:until(lambda:self.core.tasks.get(ident)['status']=='SUCCEEDED')
        finally:runner.close()
        self.assertEqual(len(self.core.tasks.actions(ident)),2)
        self.assertEqual(refresh(self.core,ident)['state'],'SATISFIED')

    def test_cancel_deadline_and_revocation_win_over_recovery(self):
        ident,store=self.waiting_task();advance(self.core,store);self.core.tasks.cancel(ident)
        self.core.change_module('text-analyzer','start',2);advance(self.core,store)
        self.assertEqual(self.core.db.one('SELECT state FROM task_waits')['state'],'CANCELLED')
        self.assertEqual(store.pending(),[])

    def test_revocation_blocks_automatic_resume(self):
        ident,store=self.waiting_task();advance(self.core,store);self.core.grants.revoke('local-default')
        self.core.change_module('text-analyzer','start',2);advance(self.core,store)
        self.assertEqual(self.core.db.one('SELECT state,reason FROM task_waits'),{'state':'BLOCKED','reason':'denied'})
        self.assertEqual(store.pending(),[])

    def test_expired_wait_exits_without_dispatch(self):
        ident,store=self.waiting_task();advance(self.core,store)
        self.core.db.connection.execute('UPDATE tasks SET deadline=0 WHERE id=?',(ident,))
        advance(self.core,store)
        self.assertEqual(self.core.db.one('SELECT state FROM task_waits')['state'],'EXPIRED')
        self.assertEqual(store.pending(),[])

    def test_unknown_action_never_resumes_even_if_wait_reason_is_mislabelled(self):
        ident,store=self.waiting_task();self.core.change_module('text-analyzer','start',2)
        self.core.tasks.state(ident,'RUNNING');step=task()['steps'][0]
        action=self.core.tasks.prepare(ident,step,step['arguments']);self.core.tasks.dispatch(ident,action['id'])
        self.core.tasks.uncertain(ident,action['id']);self.core.tasks.state(ident,'WAITING','module_disabled')
        advance(self.core,store)
        self.assertEqual(self.core.db.one('SELECT state,reason FROM task_waits'),{'state':'BLOCKED','reason':'unknown_effect'})
        self.assertEqual(store.pending(),[])

    def test_repeated_module_flapping_exhausts_the_persistent_wake_budget(self):
        ident,store=self.waiting_task()
        for _ in range(3):
            rev=self.core.db.one("SELECT revision FROM modules WHERE id='text-analyzer'")['revision']
            self.core.change_module('text-analyzer','start',rev);advance(self.core,store)
            rev=self.core.db.one("SELECT revision FROM modules WHERE id='text-analyzer'")['revision']
            self.core.change_module('text-analyzer','stop',rev);store.mark(ident,started=True)
            self.core.run_task(ident);store.mark(ident,finished=True,reason='module_disabled')
        advance(self.core,store)
        self.assertEqual(self.core.db.one('SELECT state,reason,wake_count FROM task_waits'),{'state':'BLOCKED','reason':'wake_budget','wake_count':3})
        self.assertEqual(store.pending(),[])


if __name__=='__main__':unittest.main()
