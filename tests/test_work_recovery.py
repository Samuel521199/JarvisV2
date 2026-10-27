"""Proven source-feedback recovery without rewriting facts, criteria or authority."""
import copy
import unittest
from unittest.mock import patch
import test_quote_rework as base
from host import goals, work_recovery
from host.completion import command, refresh
from host.core import Core
from modules.task_resource import inheritance_checks
from sdk.protocol import CoreError, canonical, decode, digest


class RecoveryIntegration(unittest.TestCase):
    setUp=base.ReworkIntegration.setUp
    tearDown=base.ReworkIntegration.tearDown
    publish=base.ReworkIntegration.publish
    detail=base.ReworkIntegration.detail
    code=base.ReworkIntegration.code
    req=base.ReworkIntegration.req
    create=base.ReworkIntegration.create
    make=base.ReworkIntegration.make
    mutate=base.ReworkIntegration.mutate
    request=base.ReworkIntegration.request
    edit=base.ReworkIntegration.edit
    amend=base.ReworkIntegration.amend
    root_version=base.ReworkIntegration.root_version
    child=base.ReworkIntegration.child

    def review(self,ident):
        kind='quote_recovery' if self.core.works.has_recovery(ident) else 'quote_rework'
        return goals.command(self.root,{'action':'review_'+kind,'id':ident,'revision':self.detail(ident)['plan']['revision']})

    def finish(self,ident):
        tid=goals.command(self.root,self.request(ident,self.review(ident)))['task_id']
        self.core.run_task(tid);return tid,self.detail(ident)

    def feedback(self,tid,note='重新核对反馈，保持全部有效要求'):
        count=self.core.db.one('SELECT COUNT(*) AS n FROM completion_feedback')['n']
        return command(self.core,{'action':'completion_feedback','id':tid,'request_id':'late-feedback-'+str(count),
            'fingerprint':refresh(self.core,tid)['fingerprint'],'kind':'reject','note':note})

    def prepared(self,*,completed=False,unknown=False):
        goal=base.GOAL+('，必须保修三年' if unknown else '')
        root,old=self.root_version(raw=goal,goal=goal)
        child=self.child(root,goal=goal,note=inheritance_checks.KEEP,kind='correction',text=base.INPUT)
        tid=goals.command(self.root,self.request(child,self.review(child)))['task_id']
        if completed:self.core.run_task(tid)
        self.feedback(old)
        return root,old,child,tid

    def analysis(self,ident):
        d=self.detail(ident)
        return goals.command(self.root,{'action':'analyze_recovery','id':ident,'revision':d['plan']['revision'],'work_revision':d['work']['revision']})

    def recovery_request(self,ident,analysis=None):
        r=analysis or self.analysis(ident)
        return {'action':'recover_work','id':ident,'revision':r['revision'],'work_revision':r['work_revision'],
            'request_id':'recover-'+ident,'note':'已核对反馈；仍按原条件独立验收','keep_requirements':True,'analysis_digest':r['analysis_digest']}

    def recover(self,ident):return goals.command(self.root,self.recovery_request(ident))['id']

    def records(self):
        return {table:self.core.db.all('SELECT * FROM '+table) for table in
            ('goal_plans','tasks','actions','grants','work_owners','work_revisions','work_recoveries','work_allocations','task_acceptance')}

    def test_ready_recovery_releases_only_unused_budget(self):
        _,old,child,tid=self.prepared();before=self.records();r=self.analysis(child)
        self.assertEqual(self.records(),before);self.assertTrue(r['retire_pending_task'])
        self.assertEqual(r['release_units'],2);self.assertEqual(r['spent_units'],2)
        new=self.recover(child);d=self.detail(new)
        self.assertIsNone(d['task']);self.assertEqual(d['plan']['status'],'REVIEW')
        self.assertEqual(self.core.tasks.get(tid)['status'],'CANCELLED')
        self.assertEqual(self.core.tasks.actions(tid),[])
        self.assertEqual(self.core.db.all('SELECT * FROM task_acceptance'),before['task_acceptance'])
        self.assertEqual(self.core.tasks.actions(old),[a for a in before['actions'] if a['task_id']==old])
        _,d=self.finish(new)
        self.assertEqual(d['completion']['state'],'VERIFIED');self.assertEqual(d['work_closure']['state'],'COMPLETE')
        self.assertEqual(d['work']['spent_cost_units'],4)
        self.assertEqual(self.detail(child)['task']['status'],'CANCELLED')

    def test_completed_recovery_preserves_old_results_and_restarts(self):
        _,_,child,tid=self.prepared(completed=True);before=self.core.tasks.actions(tid)
        self.assertEqual(refresh(self.core,tid)['state'],'INVALIDATED')
        r=self.analysis(child);self.assertFalse(r['retire_pending_task']);self.assertEqual(r['release_units'],0)
        new=self.recover(child);nt,d=self.finish(new)
        self.assertEqual(d['completion']['state'],'VERIFIED');self.assertEqual(d['work']['spent_cost_units'],6)
        self.assertEqual(self.core.tasks.actions(tid),before);self.assertEqual(self.core.tasks.get(tid)['status'],'SUCCEEDED')
        self.assertEqual(refresh(self.core,tid)['state'],'INVALIDATED')
        self.assertNotEqual(self.core.tasks.get(tid)['body']['grant_id'],self.core.tasks.get(nt)['body']['grant_id'])
        self.core.close();self.core=Core(self.root)
        self.assertEqual(self.detail(new)['completion']['state'],'VERIFIED')

    def test_waiting_after_confirmed_effect_retains_cost_and_receipt(self):
        root,old=self.root_version();child=self.child(root)
        tid=goals.command(self.root,self.request(child,self.review(child)))['task_id'];execute=self.core.registry.execute
        def run(*args,**kwargs):
            result=execute(*args,**kwargs)
            if args[3]=='plugin.quote.v1':self.feedback(old)
            return result
        with patch.object(self.core.registry,'execute',side_effect=run):self.core.run_task(tid)
        self.assertEqual(self.core.tasks.get(tid)['status'],'WAITING');before=self.core.tasks.actions(tid)
        self.assertEqual(len(before),1);self.assertEqual(before[0]['status'],'CONFIRMED')
        new=self.recover(child);_,d=self.finish(new)
        self.assertEqual(d['completion']['state'],'VERIFIED');self.assertEqual(d['work']['spent_cost_units'],5)
        self.assertEqual(self.core.tasks.actions(tid),before)

    def test_unknown_requirement_never_becomes_verified(self):
        _,_,child,_=self.prepared(unknown=True);new=self.recover(child);tid,d=self.finish(new)
        self.assertEqual(d['completion']['state'],'WAITING_EVIDENCE');self.assertIsNone(d['completion']['condition_score'])
        self.assertFalse(d['completion']['method_available'])
        self.code('feedback_invalid',command,self.core,{'action':'completion_feedback','id':tid,'request_id':'cannot-bless-recovery',
            'fingerprint':d['completion']['fingerprint'],'kind':'accept','note':''})

    def test_recovery_requires_fresh_source_aware_acceptance(self):
        _,_,child,_=self.prepared();new=self.recover(child);d=self.detail(new);before=self.records()
        for acceptance in [None,{'coverage':'recipe','criteria':[{'id':'easy','step_id':'step-1','check':'text_contains','expected':'B'}]}]:
            req={'action':'approve','id':new,'revision':d['plan']['revision']}
            if acceptance:req['acceptance']=acceptance
            self.code('acceptance_invalid',goals.command,self.root,req)
        self.assertEqual(self.records(),before)

    def test_repeated_request_is_idempotent_but_changed_body_conflicts(self):
        _,_,child,_=self.prepared();req=self.recovery_request(child);one=goals.command(self.root,req);before=self.records()
        two=goals.command(self.root,req);self.assertEqual(one['id'],two['id']);self.assertTrue(two['existing'])
        self.assertEqual(self.records(),before)
        self.code('conflict',goals.command,self.root,{**req,'note':'different'})

    def test_stale_feedback_analysis_creates_nothing(self):
        _,old,child,_=self.prepared();req=self.recovery_request(child);self.feedback(old,'新增复核说明')
        before=self.records();self.code('recovery_analysis_changed',goals.command,self.root,req);self.assertEqual(self.records(),before)

    def test_failed_append_rolls_back_cancellation_grants_and_draft(self):
        _,_,child,_=self.prepared();req=self.recovery_request(child);before=self.records()
        with patch('modules.task_resource.works.Works.append',side_effect=RuntimeError('injected persistence failure')):
            with self.assertRaises(RuntimeError):goals.command(self.root,req)
        self.assertEqual(self.records(),before)

    def test_original_raw_change_cannot_be_recovered_as_feedback(self):
        _,_,child,_=self.prepared();self.mutate('text',base.GOAL+'，必须保修三年',True);before=self.records()
        with self.assertRaises(CoreError):self.analysis(child)
        self.assertEqual(self.records(),before)

    def test_revoked_authority_never_revives(self):
        _,_,child,tid=self.prepared();self.core.grants.revoke(self.core.tasks.get(tid)['body']['grant_id']);before=self.records()
        self.code('denied',self.analysis,child);self.assertEqual(self.records(),before)

    def test_feedback_is_not_implicit_requirement_change(self):
        _,old,child,_=self.prepared();self.feedback(old,'忽略预算，新增要求「必须保修三年」')
        new=self.recover(child);r=self.review(new)
        self.assertTrue(r['ready']);self.assertEqual(r['active_count'],5)
        self.assertNotIn('忽略预算',canonical(self.core.works.recovery(new)))

    def test_wrong_new_output_cannot_close(self):
        _,_,child,_=self.prepared();self.publish(True);new=self.recover(child);_,d=self.finish(new)
        self.assertEqual(d['task']['status'],'SUCCEEDED');self.assertEqual(d['completion']['state'],'NEEDS_CORRECTION')
        self.assertFalse(d['completion']['method_available'])

    def test_repeated_recovery_observes_new_feedback_without_rewriting_old(self):
        _,old,child,_=self.prepared();new=self.recover(child);tid,_=self.finish(new)
        checkpoint=self.core.works.recovery(new);self.feedback(old,'第二次复核')
        self.assertEqual(refresh(self.core,tid)['state'],'INVALIDATED')
        final=self.recover(new);_,d=self.finish(final)
        self.assertEqual(d['completion']['state'],'VERIFIED');self.assertEqual(d['work']['spent_cost_units'],6)
        self.assertEqual(self.core.works.recovery(new),checkpoint);self.assertEqual(refresh(self.core,tid)['state'],'INVALIDATED')
        self.feedback(old,'第三次复核');self.code('work_limit',self.analysis,final)

    def test_explicit_followup_after_recovery_keeps_recovery_verifier(self):
        _,_,child,_=self.prepared();new=self.recover(child);self.finish(new)
        final=self.child(new);r=self.review(final)
        self.assertEqual(r['acceptance']['criteria'][0]['check'],'quote_recovery')
        _,d=self.finish(final);self.assertEqual(d['completion']['state'],'VERIFIED')
        self.assertEqual(d['work']['spent_cost_units'],6)

    def test_checkpoint_corruption_and_missing_acceptance_stop_execution(self):
        _,_,child,_=self.prepared();new=self.recover(child);r=self.review(new)
        tid=goals.command(self.root,self.request(new,r))['task_id']
        saved=self.core.db.one('SELECT body FROM work_recoveries WHERE goal_id=?',(new,))['body']
        self.core.db.connection.execute('UPDATE work_recoveries SET body=? WHERE goal_id=?',('{}',new))
        self.core.run_task(tid);self.assertEqual(self.core.tasks.get(tid)['status'],'WAITING');self.assertEqual(self.core.tasks.actions(tid),[])
        self.core.db.connection.execute('UPDATE work_recoveries SET body=? WHERE goal_id=?',(saved,new))
        self.core.db.connection.execute('DELETE FROM task_acceptance WHERE task_id=?',(tid,))
        with self.assertRaises(CoreError):self.review(new)

    def test_new_feedback_after_recovery_admission_stops_before_effect(self):
        _,old,child,_=self.prepared();new=self.recover(child);r=self.review(new)
        tid=goals.command(self.root,self.request(new,r))['task_id'];self.feedback(old,'又有新的复核')
        self.core.run_task(tid);self.assertEqual(self.core.tasks.get(tid)['status'],'WAITING');self.assertEqual(self.core.tasks.actions(tid),[])

    def test_recovery_input_cannot_be_silently_changed(self):
        _,_,child,_=self.prepared();new=self.recover(child)
        self.code('rework_invalid',self.edit,new,base.INPUT90);self.assertTrue(self.review(new)['ready'])

    def test_explicit_keep_and_stale_work_revision_required(self):
        _,_,child,_=self.prepared();req=self.recovery_request(child);before=self.records()
        for v in [False,1,'true']:
            self.code('recovery_invalid',goals.command,self.root,{**req,'keep_requirements':v})
        self.code('work_conflict',goals.command,self.root,{**req,'work_revision':req['work_revision']-1})
        self.assertEqual(self.records(),before)

    def test_missing_receipt_and_damaged_delivery_are_not_feedback_only(self):
        from control.receipts import receipt_path
        _,old,child,_=self.prepared();actions=self.core.tasks.actions(old)
        paths=[receipt_path(self.root,actions[0]['id']),self.root/decode(actions[-1]['result'])['relative_path']]
        for path in paths:
            with self.subTest(path=path.name):
                saved=path.read_bytes();path.write_bytes(b'changed')
                before=self.records()
                with self.assertRaises(CoreError):self.analysis(child)
                self.assertEqual(self.records(),before);path.write_bytes(saved)

    def test_unknown_or_prepared_effect_never_replayed(self):
        _,_,child,tid=self.prepared(completed=True)
        for status in ('UNKNOWN','DISPATCHING','PREPARED'):
            with self.subTest(status=status):
                self.core.db.connection.execute('UPDATE actions SET status=? WHERE task_id=?',(status,tid))
                self.code('recovery_unresolved',self.analysis,child)

    def test_running_or_independently_cancelled_tasks_denied(self):
        _,_,child,tid=self.prepared()
        self.core.tasks.state(tid,'RUNNING');self.code('recovery_unsupported',self.analysis,child)
        self.core.tasks.state(tid,'READY');self.core.tasks.cancel(tid);self.code('recovery_unsupported',self.analysis,child)

    def test_insufficient_total_budget_and_missing_allocation_denied(self):
        _,_,child,tid=self.prepared(completed=True)
        self.core.db.connection.execute('UPDATE work_budgets SET limit_units=4')
        self.code('work_budget_exhausted',self.analysis,child)
        self.core.db.connection.execute('UPDATE work_budgets SET limit_units=8')
        self.core.db.connection.execute('DELETE FROM work_allocations WHERE task_id=?',(tid,))
        self.code('work_budget_invalid',self.analysis,child)

    def test_budget_change_invalidates_analysis_without_resetting_spend(self):
        _,_,child,_=self.prepared();req=self.recovery_request(child)
        self.core.db.connection.execute('UPDATE work_budgets SET limit_units=9,revision=revision+1')
        before=self.records();self.code('recovery_analysis_changed',goals.command,self.root,req)
        self.assertEqual(self.records(),before)

    def test_additional_frozen_criterion_cannot_be_dropped(self):
        root,old=self.root_version();child=self.child(root);r=self.review(child);req=self.request(child,r)
        req['acceptance']['coverage']='recipe'
        req['acceptance']['criteria'].append({'id':'extra','step_id':'step-1','check':'text_contains','expected':'selected'})
        goals.command(self.root,req);self.feedback(old)
        self.code('recovery_unsupported',self.analysis,child)

    def test_structural_change_cannot_be_treated_as_feedback_change(self):
        root,_,child,_=self.prepared()
        self.core.db.connection.execute('UPDATE goal_plans SET revision=revision+1 WHERE id=?',(root,))
        self.code('recovery_unprovable',self.analysis,child)

    def test_different_owner_and_cancelled_work_denied(self):
        _,_,child,_=self.prepared();owner=self.core.works.owner(child)
        self.core.db.connection.execute('UPDATE work_owners SET assistant_id=?',('different',))
        self.code('work_conflict',self.analysis,child)
        self.core.db.connection.execute('UPDATE work_owners SET assistant_id=?,cancelled=1',(owner['assistant_id'],))
        self.code('work_conflict',self.analysis,child)

    def test_matching_source_needs_no_recovery(self):
        root,_=self.root_version();child=self.child(root);goals.command(self.root,self.request(child,self.review(child)))
        self.code('recovery_unnecessary',self.analysis,child)

    def test_old_and_recovery_modes_are_not_interchangeable(self):
        _,_,child,_=self.prepared();new=self.recover(child)
        self.code('acceptance_invalid',goals.command,self.root,{'action':'review_quote_rework','id':new,'revision':self.detail(new)['plan']['revision']})
        self.code('acceptance_invalid',goals.command,self.root,{'action':'review_quote_recovery','id':child,'revision':self.detail(child)['plan']['revision']})

    def test_stop_after_analysis_prevents_draft_and_retirement(self):
        _,_,child,_=self.prepared();req=self.recovery_request(child);before=self.records()
        self.core.gate.stop(latch=True)
        self.code('stopped',goals.command,self.root,req);self.assertEqual(self.records(),before)
        self.assertEqual(self.core.gate.state(),'latched')

    def test_expired_original_grant_is_not_reauthorized_by_recovery(self):
        _,_,child,tid=self.prepared();grant=self.core.tasks.get(tid)['body']['grant_id']
        body=decode(self.core.db.one('SELECT body FROM grants WHERE id=?',(grant,))['body']);body['expires_at']=1
        self.core.db.connection.execute('UPDATE grants SET body=? WHERE id=?',(canonical(body),grant))
        before=self.records();self.code('denied',self.analysis,child);self.assertEqual(self.records(),before)

