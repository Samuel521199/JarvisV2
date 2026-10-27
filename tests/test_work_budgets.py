"""Shared action budget boundaries, real execution and failure/legacy counterexamples."""
import concurrent.futures
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_work_revisions as base
from host import goals
from host.core import Core
from modules.task_resource.work_budgets import WorkBudgets
from sdk.protocol import CoreError, decode


class WorkBudgetsTest(unittest.TestCase):
    for _name in ('setUp','tearDown','publish','req','create','detail','approve','code','original','request','rework'):
        locals()[_name]=getattr(base.WorkRevisions,_name)

    def prepared(self, limit=None):
        ident=self.create()
        goals.command(self.root,{'action':'edit','id':ident,'revision':1,'proposal':base.base.proposal(chain=True)})
        req={'action':'approve','id':ident,'revision':2}
        if limit is not None:req['budget_limit']=limit
        return ident,req

    def budget(self, ident):return self.detail(ident)['work']['budget']

    def change(self, ident, limit, **kwargs):
        current=self.budget(ident)
        return {'action':'set_work_budget','id':ident,'revision':current['revision'],'request_id':'budget-change-'+str(current['revision']),
                'limit_units':limit,'note':'明确调整整件工作的执行额度',**kwargs}

    def test_reservation_becomes_original_ledger_spend_and_draft_costs_nothing(self):
        ident,req=self.prepared();tid=goals.command(self.root,req)['task_id']
        self.assertEqual((self.budget(ident)['limit_units'],self.budget(ident)['reserved_units']),(12,3))
        self.core.run_task(tid);child=self.rework(ident)
        self.assertEqual((self.budget(child)['spent_units'],self.budget(child)['reserved_units']),(3,0))
        new=self.approve(child);self.assertEqual(self.budget(child)['reserved_units'],2)
        self.core.run_task(new)
        b=self.budget(child);self.assertEqual((b['spent_units'],b['reserved_units'],b['available_units']),(5,0,7))
        self.assertEqual(sum(t['spent'] for t in self.core.db.all('SELECT spent FROM tasks')),5)

    def test_insufficient_root_budget_rolls_back_new_grant_task_and_queue(self):
        ident,req=self.prepared(4);tid=goals.command(self.root,req)['task_id'];self.core.run_task(tid)
        child=self.rework(ident)
        self.code('work_budget_exhausted',goals.command,self.root,{'action':'approve_and_run','id':child,'revision':1})
        self.assertEqual(len(self.core.db.all('SELECT * FROM tasks')),1)
        self.assertIsNone(self.core.db.one('SELECT * FROM grants WHERE id=?',(child+'-execute',)))
        self.assertIsNone(self.detail(child)['task']);self.assertEqual(self.budget(child)['available_units'],1)

    def test_exact_total_is_shared_across_followup_versions(self):
        ident,req=self.prepared(5);self.core.run_task(goals.command(self.root,req)['task_id'])
        child=self.rework(ident);self.core.run_task(self.approve(child))
        next_goal=self.rework(child,start_step=1)
        self.code('work_budget_exhausted',self.approve,next_goal)
        self.assertEqual(self.budget(next_goal)['spent_units'],5)

    def test_budget_increase_does_not_change_grants_or_execute_draft(self):
        ident,_=self.original();child=self.rework(ident)
        grants=self.core.db.all('SELECT * FROM grants')
        goals.command(self.root,self.change(ident,3));self.code('work_budget_exhausted',self.approve,child)
        goals.command(self.root,self.change(child,5))
        self.assertEqual(self.core.db.all('SELECT * FROM grants'),grants)
        self.assertIsNone(self.detail(child)['task'])
        self.assertEqual(self.core.run_task(self.approve(child))['status'],'SUCCEEDED')

    def test_lowering_cannot_steal_reservation_and_cancel_releases_unused(self):
        ident,_=self.original();child=self.rework(ident);new=self.approve(child)
        self.code('work_budget_committed',goals.command,self.root,self.change(ident,4))
        goals.command(self.root,{'action':'cancel','id':child})
        self.assertEqual(self.budget(ident)['reserved_units'],0)
        goals.command(self.root,self.change(ident,3))
        self.code('invalid_state',self.core.run_task,new)

    def test_unknown_even_after_cancel_keeps_unconfirmed_reservation(self):
        ident,_=self.original();child=self.rework(ident);new=self.approve(child)
        with patch.object(self.core.registry,'execute',side_effect=RuntimeError('synthetic uncertain effect')):self.core.run_task(new)
        goals.command(self.root,{'action':'cancel','id':child})
        b=self.budget(ident)
        self.assertEqual((b['spent_units'],b['reserved_units'],b['unresolved_tasks']),(4,1,1))
        self.code('work_budget_committed',goals.command,self.root,self.change(ident,4))
        self.assertEqual(self.core.tasks.actions(new)[0]['status'],'UNKNOWN')

    def test_confirmed_receipt_releases_only_unused_reservation_without_replay(self):
        ident,_=self.original();child=self.rework(ident);new=self.approve(child)
        with patch.object(self.core.tasks,'confirm',side_effect=RuntimeError('synthetic lost confirmation')):
            self.core.run_task(new)
        goals.command(self.root,{'action':'cancel','id':child})
        self.assertEqual((self.budget(child)['spent_units'],self.budget(child)['reserved_units']),(4,1))
        with patch.object(self.core.worker,'run',side_effect=AssertionError('Reconciliation cannot replay tools')):
            reconciled=self.core.reconcile(new)
        self.assertEqual(len(reconciled['reconciled']),1)
        self.assertEqual(reconciled['task_state'],'CANCELLED')
        self.assertEqual((self.budget(child)['spent_units'],self.budget(child)['reserved_units']),(4,0))
        goals.command(self.root,self.change(ident,4))
        self.code('invalid_state',self.core.run_task,new)

    def test_pre_dispatch_failure_releases_reservation_without_faking_spend(self):
        ident,_=self.original();child=self.rework(ident);new=self.approve(child)
        with patch.object(self.core.registry,'validate_arguments',side_effect=CoreError('invalid_arguments','fixture invalid')):
            result=self.core.run_task(new)
        self.assertEqual(result['status'],'FAILED')
        self.assertEqual((self.budget(ident)['spent_units'],self.budget(ident)['reserved_units']),(3,0))

    def test_restart_and_approval_retries_do_not_double_reserve_or_charge(self):
        ident,req=self.prepared(5);tid=goals.command(self.root,req)['task_id']
        self.core.close();self.core=Core(self.root)
        self.assertEqual(goals.command(self.root,req)['task_id'],tid)
        self.assertEqual(self.budget(ident)['reserved_units'],3)
        self.core.run_task(tid);self.core.run_task(tid)
        self.assertEqual(self.budget(ident)['spent_units'],3)
        self.assertEqual(len(self.core.db.all("SELECT * FROM events WHERE kind='work.budget_reserved'")),1)

    def test_approval_retry_uses_original_selection_after_explicit_budget_update(self):
        ident,req=self.prepared(5);tid=goals.command(self.root,req)['task_id']
        goals.command(self.root,self.change(ident,6))
        self.assertEqual(goals.command(self.root,req)['task_id'],tid)
        self.code('work_budget_conflict',goals.command,self.root,{**req,'budget_limit':6})

    def test_budget_request_id_and_revision_survive_later_changes(self):
        ident,_=self.original();req=self.change(ident,5);first=goals.command(self.root,req)
        goals.command(self.root,self.change(ident,6))
        self.assertTrue(goals.command(self.root,req)['existing'])
        self.assertEqual(self.budget(ident)['limit_units'],6)
        self.code('work_budget_conflict',goals.command,self.root,{**req,'limit_units':7})
        self.code('work_budget_conflict',goals.command,self.root,{**req,'request_id':'stale-new-id'})
        self.assertEqual(first['revision'],2)

    def test_concurrent_budget_edits_compare_revision(self):
        ident,_=self.original();req=self.change(ident,5)
        def run(v):
            try:return goals.command(self.root,v)
            except CoreError as exc:return exc.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,[req,{**req,'request_id':'other-budget-request','limit_units':6}]))
        self.assertEqual(sum(isinstance(r,dict) for r in results),1)
        self.assertIn('work_budget_conflict',results)

    def test_dispatch_transaction_rechecks_root_budget_before_original_charge(self):
        ident,_=self.original();child=self.rework(ident);new=self.approve(child)
        prepare=self.core.tasks.prepare
        def corrupt(*args):
            action=prepare(*args)
            self.core.db.connection.execute('UPDATE work_budgets SET limit_units=3 WHERE root_goal=?',(ident,))
            return action
        with patch.object(self.core.tasks,'prepare',side_effect=corrupt):result=self.core.run_task(new)
        self.assertEqual((result['status'],result['error'],result['spent']),('WAITING','work_budget_exhausted',0))
        self.assertEqual(self.core.db.one('SELECT spent FROM grants WHERE id=?',(child+'-execute',))['spent'],0)

    def test_effect_boundary_stops_if_budget_evidence_changes_after_charge(self):
        ident,_=self.original();child=self.rework(ident);new=self.approve(child);execute=self.core.registry.execute
        def corrupt(*args):
            self.core.db.connection.execute('UPDATE work_budgets SET limit_units=3 WHERE root_goal=?',(ident,))
            return execute(*args)
        with patch.object(self.core.registry,'execute',side_effect=corrupt):result=self.core.run_task(new)
        self.assertEqual(result['status'],'WAITING');self.assertEqual(self.core.tasks.actions(new)[0]['status'],'UNKNOWN')
        self.assertFalse(any(a['status']=='CONFIRMED' for a in self.core.tasks.actions(new)))

    def test_missing_reservation_is_not_recreated_by_budget_edit(self):
        ident,_=self.original();child=self.rework(ident);new=self.approve(child)
        self.core.db.connection.execute('DELETE FROM work_allocations WHERE task_id=?',(new,))
        self.assertEqual(self.core.run_task(new)['error'],'work_budget_invalid')
        self.code('work_budget_invalid',goals.command,self.root,self.change(ident,20))
        self.assertEqual(self.core.tasks.get(new)['spent'],0)

    def test_budget_is_not_a_replacement_for_revoked_execution_grant(self):
        ident,_=self.original();child=self.rework(ident);new=self.approve(child)
        self.core.grants.revoke(child+'-execute');goals.command(self.root,self.change(ident,20))
        self.assertEqual(self.core.run_task(new)['error'],'denied')
        action=self.core.tasks.actions(new)[0]
        self.assertEqual((action['status'],action['attempts'],action['result']),('PREPARED',0,None))
        self.assertEqual(self.core.tasks.get(new)['spent'],0)

    def test_cancelled_root_cannot_receive_fresh_budget_or_reactivate(self):
        ident,_=self.original();req=self.change(ident,5);goals.command(self.root,req)
        goals.command(self.root,{'action':'cancel_work','id':ident,'work_revision':1})
        self.assertTrue(goals.command(self.root,req)['existing'])
        self.code('work_conflict',goals.command,self.root,self.change(ident,20))
        self.assertTrue(self.detail(ident)['work']['cancelled'])

    def test_invalid_or_insufficient_initial_limits_rollback_all_admission(self):
        ident,req=self.prepared()
        for limit in [None,True,0,-1,1.5,'5',1001]:
            with self.subTest(limit=limit):self.code('work_budget_invalid',goals.command,self.root,{**req,'budget_limit':limit})
        self.code('work_budget_exhausted',goals.command,self.root,{**req,'budget_limit':2})
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        self.assertEqual(self.core.db.all('SELECT * FROM work_owners'),[])
        self.assertIsNone(self.core.db.one('SELECT * FROM grants WHERE id=?',(ident+'-execute',)))

    def test_schema_upgrade_preserves_legacy_inflight_then_requires_explicit_adoption(self):
        ident,req=self.prepared();tid=goals.command(self.root,req)['task_id'];identity=self.core.identity.describe()
        for table in ['work_budget_changes','work_allocations','work_budgets']:self.core.db.connection.execute('DROP TABLE '+table)
        self.core.db.connection.execute("UPDATE meta SET value='1' WHERE key='work_schema'")
        self.core.close();self.core=Core(self.root)
        self.assertFalse(self.budget(ident)['enforced']);self.assertEqual(self.core.identity.describe(),identity)
        self.assertEqual(self.core.run_task(tid)['status'],'SUCCEEDED')
        child=self.rework(ident);self.code('work_budget_required',self.approve,child)
        goals.command(self.root,self.change(ident,5))
        self.assertEqual(self.budget(ident)['spent_units'],3)
        self.assertEqual(self.core.run_task(self.approve(child))['status'],'SUCCEEDED')
        self.assertEqual(self.budget(child)['available_units'],0)

    def test_real_process_crash_around_reservation_is_atomic(self):
        ident,_=self.original();child=self.rework(ident);req={'action':'approve','id':child,'revision':1}
        marker={'fixture_root':str(self.root.resolve()),'request':req,'crash_event':'work.budget_reserved'}
        (self.root/'handoff-crash-fixture.json').write_text(json.dumps(marker),encoding='utf-8')
        for mode,expected in [('before',91),('after',92)]:
            result=subprocess.run([sys.executable,'-m','tools.handoff_crash_worker',str(self.root),mode],cwd=base.base.ROOT,timeout=30)
            self.assertEqual(result.returncode,expected)
            self.assertEqual(self.budget(child)['reserved_units'],0 if mode=='before' else 2)
        tid=goals.command(self.root,req)['task_id']
        self.assertEqual(len(self.core.db.all('SELECT * FROM work_allocations')),2)
        self.assertEqual(self.core.run_task(tid)['status'],'SUCCEEDED')

    def test_real_process_crash_around_budget_update_keeps_one_revision(self):
        ident,_=self.original();req=self.change(ident,5)
        marker={'fixture_root':str(self.root.resolve()),'request':req,'crash_event':'work.budget_changed'}
        (self.root/'handoff-crash-fixture.json').write_text(json.dumps(marker),encoding='utf-8')
        for mode,expected in [('before',91),('after',92)]:
            result=subprocess.run([sys.executable,'-m','tools.handoff_crash_worker',str(self.root),mode],cwd=base.base.ROOT,timeout=30)
            self.assertEqual(result.returncode,expected)
            self.assertEqual(self.budget(ident)['revision'],1 if mode=='before' else 2)
        self.assertTrue(goals.command(self.root,req)['existing'])
        self.assertEqual(len(self.core.db.all('SELECT * FROM work_budget_changes')),1)


if __name__=='__main__':unittest.main()
