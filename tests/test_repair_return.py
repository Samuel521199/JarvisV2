"""Real restricted workers and original work ledgers; deterministic models only."""
import unittest
from unittest.mock import patch
from host import repair_return, goals
from host.completion import refresh, command as feedback
from host.settings_operations import command
from modules.task_resource import repair_returns
from modules.task_resource.plans import Plans
from sdk.protocol import CoreError, decode
import test_lesson_repair as fixture


class RepairReturnTests(unittest.TestCase):
    def begin_auto(self,domain='practice',wrong_original=False):
        goal,tid=self.candidate(domain,wrong_original=True) if wrong_original else self.failed(domain)
        draft=self.prepare_repair(tid)
        ident=self.begin_repair(tid,draft,action='lesson_repair_begin_auto')['id']
        logic=fixture.TOOLS[domain][2]
        source="import json\ndef run(text):\n    v=json.loads(text)\n    "+logic+"\n    return json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))\n"
        provider=self.bind_repair(ident,source)
        return goal,tid,ident,provider

    def execute(self,ident,provider,**kw):
        from control.network import NetworkGate
        with patch('host.core.NativeModel',return_value=provider),patch.object(NetworkGate,'require_model_online'):
            return repair_return.run(self.root,ident,**kw)

    def test_three_domains_rejoin_same_work_preserve_requirements_and_actual_receipts(self):
        for domain in fixture.TOOLS:
            with self.subTest(domain=domain):
                goal,tid,ident,provider=self.begin_auto(domain)
                original=self.core.tasks.get(tid);before=self.core.db.all('SELECT * FROM release_slots WHERE capability NOT LIKE ?',('plugin.repair-%',))
                result=self.execute(ident,provider)
                self.assertEqual(result['status'],'CLOSED',result)
                self.assertEqual(result['actual']['score_delta'],0)  # Original passed but unseen cases failed.
                self.assertEqual(result['actual']['condition_score'],100)
                self.assertEqual(refresh(self.core,tid)['state'],'VERIFIED')
                self.assertEqual(self.core.tasks.get(tid),original)
                self.assertEqual(self.core.works.owner(goal)['current_goal'],result['child_goal'])
                self.assertEqual(self.core.works.link(result['child_goal'])['parent_goal'],goal)
                self.assertEqual(before,self.core.db.all('SELECT * FROM release_slots WHERE capability NOT LIKE ?',('plugin.repair-%',)))
                self.assertEqual(refresh(self.core,tid)['learning_candidate']['validation']['trial']['result']['status'],'FAILED')
                counts={t:len(self.core.db.all('SELECT * FROM '+t)) for t in ('tasks','actions','model_calls','work_revisions')}
                self.assertEqual(self.execute(ident,provider)['status'],'CLOSED')
                for table,n in counts.items():self.assertEqual(len(self.core.db.all('SELECT * FROM '+table)),n)

    def test_source_cancel_before_model_preserves_old_tool_and_calls(self):
        goal,tid,ident,provider=self.begin_auto()
        from host.work_revisions import cancel
        cancel(self.core,goal,self.core.works.owner(goal)['revision'])
        result=self.execute(ident,provider)
        self.assertEqual(result['status'],'FAILED');self.assertFalse(provider.prompts)
        self.assertFalse(result['child_goal'])

    def test_actual_failed_original_improves_without_rewriting_original_score(self):
        for domain in fixture.TOOLS:
            with self.subTest(domain=domain):
                goal,tid,ident,provider=self.begin_auto(domain,wrong_original=True)
                self.assertEqual(refresh(self.core,tid)['condition_score'],0)
                result=self.execute(ident,provider)
                self.assertEqual(result['status'],'CLOSED',result)
                self.assertEqual(result['actual']['score_delta'],100)
                self.assertEqual(refresh(self.core,tid)['condition_score'],0)

    def test_shadow_rejects_candidate_that_only_handles_generated_cases(self):
        goal,tid,ident,_=self.begin_auto()
        spec=self.core.development.get(ident)['spec']
        table={c['input']:c['expected'] for c in spec['public_cases']+spec['evaluation_cases']}
        provider=self.bind_repair(ident,'def run(text):\n    return '+repr(table)+'.get(text,\'{}\')\n')
        result=self.execute(ident,provider)
        self.assertEqual((result['status'],result['error']),('FAILED','repair_actual_failed'),result)
        self.assertIsNone(self.core.packages.slot(spec['capability']));self.assertFalse(result['child_goal'])

    def test_late_feedback_regresses_closed_return_and_quarantines_only_candidate(self):
        goal,tid,ident,provider=self.begin_auto();result=self.execute(ident,provider)
        self.assertEqual(result['status'],'CLOSED',result)
        child=result['child_task'];current=refresh(self.core,child)
        feedback(self.core,{'action':'completion_feedback','id':child,'request_id':'late-repair-reject',
            'fingerprint':current['fingerprint'],'kind':'reject','note':'Actual result needs correction'})
        result=self.execute(ident,provider)
        self.assertEqual(result['status'],'REGRESSED')
        self.assertFalse(self.core.packages.slot(result['capability'])['enabled'])
        for cap,binding in self.core.tasks.get(tid)['bindings'].items():self.assertEqual(self.core.registry.binding(cap),binding)

    def test_cancel_and_foreground_do_not_reset_mandate(self):
        _,tid,ident,provider=self.begin_auto()
        self.assertEqual(self.execute(ident,provider,interrupted=lambda:True)['status'],'deferred')
        self.assertFalse(provider.prompts)
        command(self.root,{'action':'lesson_repair_return_cancel','id':ident})
        self.assertEqual(self.execute(ident,provider)['status'],'CANCELLED')
        self.assertFalse(provider.prompts)

    def test_crash_after_child_creation_recovers_same_work_request(self):
        goal,tid,ident,provider=self.begin_auto();create=repair_return.work_revisions.create
        def crash(core,value):
            create(core,value);raise RuntimeError('simulated process loss')
        with patch.object(repair_return.work_revisions,'create',crash),self.assertRaises(RuntimeError):self.execute(ident,provider)
        result=self.execute(ident,provider)
        self.assertEqual(result['status'],'CLOSED',result)
        self.assertEqual(len(self.core.db.all('SELECT * FROM work_revisions WHERE parent_goal=?',(goal,))),1)

    def test_stop_resume_and_cancel_during_shadow(self):
        _,_,ident,provider=self.begin_auto()
        self.core.gate.stop();self.assertEqual(self.execute(ident,provider)['status'],'deferred')
        self.assertFalse(provider.prompts);self.core.gate.resume(self.core.gate.token())
        verify=repair_return.verify_text
        def cancelled(core,value,text):
            command(self.root,{'action':'lesson_repair_return_cancel','id':ident})
            return verify(core,value,text)
        with patch.object(repair_return,'verify_text',cancelled):result=self.execute(ident,provider)
        self.assertEqual(result['status'],'CANCELLED',result)
        self.assertFalse(result.get('child_goal'));self.assertIsNone(self.core.packages.slot(result['capability']))

    def test_unknown_return_action_is_not_replayed(self):
        _,_,ident,provider=self.begin_auto()
        from host.core import Core
        original=Core.run_task
        def crash(core,tid):
            result=original(core,tid)
            if core.db.one('SELECT id FROM goal_plans WHERE task_id=?',(tid,)):
                with core.db.transaction() as tx:tx.execute("UPDATE actions SET status='UNKNOWN' WHERE task_id=? AND step_id='step-1'",(tid,))
                raise RuntimeError('simulated lost acknowledgement')
            return result
        with patch.object(Core,'run_task',crash),self.assertRaises(RuntimeError):self.execute(ident,provider)
        with patch.object(Core,'run_task',side_effect=AssertionError('unknown action replayed')):
            result=self.execute(ident,provider)
        self.assertEqual((result['status'],result['error']),('WAITING','reconciliation_required'))

    def test_original_grant_withdrawal_and_work_budget_prevent_automatic_start(self):
        goal,tid=self.failed();draft=self.prepare_repair(tid)
        from host.work_revisions import configure_budget
        from modules.task_resource.work_budgets import WorkBudgets
        budget=WorkBudgets(self.core.db).projection(goal)
        configure_budget(self.core,{'id':goal,'revision':budget['revision'],'request_id':'repair-budget-test','limit_units':budget['spent_units'],'note':'No remaining allowance'})
        with self.assertRaises(CoreError) as raised:self.begin_repair(tid,draft,action='lesson_repair_begin_auto')
        self.assertEqual(raised.exception.code,'work_budget_exhausted')
        self.assertFalse(self.core.db.all('SELECT * FROM development_runs'))
        self.core.grants.revoke(self.core.tasks.get(tid)['body']['grant_id'])
        with self.assertRaises(CoreError) as raised:self.begin_repair(tid,draft,action='lesson_repair_begin_auto')
        self.assertEqual(raised.exception.code,'denied')

    def test_multistage_acceptance_is_not_silently_dropped(self):
        from host.lesson_validation import run
        _,tid=self.candidate(stages=2,overfit=True);self.enable();run(self.root,tid)
        draft=self.prepare_repair(tid)
        with self.assertRaises(CoreError) as raised:self.begin_repair(tid,draft,action='lesson_repair_begin_auto')
        self.assertEqual(raised.exception.code,'repair_return_unsupported')
        self.assertFalse(self.core.db.all('SELECT * FROM development_runs'))

    def test_shadow_process_loss_requires_reconciliation_without_repeating_worker(self):
        _,_,ident,provider=self.begin_auto()
        with patch.object(repair_return,'verify_text',side_effect=RuntimeError('shadow receipt lost')),self.assertRaises(RuntimeError):
            self.execute(ident,provider)
        from control.worker.runtime import RestrictedWorker
        with patch.object(RestrictedWorker,'run',side_effect=AssertionError('shadow replayed')):
            result=self.execute(ident,provider)
        self.assertEqual((result['status'],result['error']),('WAITING','shadow_reconciliation_required'))
        self.assertIsNone(self.core.packages.slot(result['capability']))

    def test_changed_child_proposal_is_stopped_before_admission(self):
        _,_,ident,provider=self.begin_auto();create=repair_return.work_revisions.create
        def crash(core,value):create(core,value);raise RuntimeError('lost child link')
        with patch.object(repair_return.work_revisions,'create',crash),self.assertRaises(RuntimeError):self.execute(ident,provider)
        from sdk.protocol import canonical
        value=repair_returns.get(self.core.db,ident)
        child=self.core.db.one('SELECT goal_id FROM work_revisions WHERE request_id=?',(value['rework_request']['request_id'],))['goal_id']
        proposal=Plans(self.core.db).get(child)['proposal'];proposal['input_text']='changed'
        with self.core.db.transaction() as tx:tx.execute('UPDATE goal_plans SET proposal=? WHERE id=?',(canonical(proposal),child))
        result=self.execute(ident,provider)
        self.assertEqual((result['status'],result['error']),('FAILED','repair_source_changed'))
        self.assertFalse(Plans(self.core.db).get(child)['task_id'])

    def test_upgrade_handoff_defers_without_revoking_or_regressing(self):
        _,_,ident,provider=self.begin_auto()
        from control.application_runtime import publish
        publish(self.root,'a'*64,1,'draining')
        self.assertEqual(self.execute(ident,provider),{'status':'deferred','error':'application_maintenance'})
        self.assertFalse(provider.prompts)
        publish(self.root,'a'*64,1,'active');value=self.execute(ident,provider)
        self.assertEqual(value['status'],'CLOSED',value)
        publish(self.root,'a'*64,1,'draining')
        class Lane:
            def state(self):return {'status':'idle'}
            def submit(self,*args):raise AssertionError('maintenance must not dispatch')
        repair_return._last.pop(str(self.root),None)
        repair_return.advance(self.root,Lane())
        self.assertEqual(repair_returns.get(self.core.db,ident)['status'],'CLOSED')
        publish(self.root,'a'*64,1,'active');self.assertEqual(self.execute(ident,provider)['status'],'CLOSED')

    def test_memory_opt_out_during_model_stops_before_next_phase(self):
        goal,_,ident,provider=self.begin_auto();generate=provider.generate
        def withdraw(prompt,checkpoint):
            result=generate(prompt,checkpoint)
            with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET enabled=0 WHERE goal_id=?',(goal,))
            return result
        with patch.object(provider,'generate',withdraw):result=self.execute(ident,provider)
        self.assertEqual(result['status'],'FAILED',result);self.assertEqual(len(provider.prompts),1)
        self.assertFalse(result['child_goal']);self.assertIsNone(self.core.packages.slot(result['capability']))

    def test_normal_followup_does_not_regress_prior_closure_or_disable_tool(self):
        _,_,ident,provider=self.begin_auto();value=self.execute(ident,provider)
        self.assertEqual(value['status'],'CLOSED',value)
        p=Plans(self.core.db).get(value['child_goal']);owner=self.core.works.owner(p['id'])
        child=repair_return.work_revisions.create(self.core,{'action':'rework','id':p['id'],'revision':p['revision'],
            'work_revision':owner['revision'],'start_step':1,'request_id':'normal-next-request','kind':'new_requirement',
            'goal':p['request']['goal'],'note':'Another explicitly requested delivery'})['id']
        self.assertEqual(self.execute(ident,provider)['status'],'CLOSED')
        self.assertEqual(self.core.works.owner(child)['current_goal'],child)
        command(self.root,{'action':'lesson_repair_return_cancel','id':ident})
        self.assertTrue(self.core.packages.slot(value['capability'])['enabled'])
        self.assertFalse(self.core.works.owner(child)['cancelled'])

    def test_cancel_racing_admission_cannot_leave_a_live_child_grant(self):
        _,_,ident,provider=self.begin_auto();approve=goals.command
        def cancel_after(root,value):
            result=approve(root,value)
            if value['action']=='approve':command(root,{'action':'lesson_repair_return_cancel','id':ident})
            return result
        with patch.object(goals,'command',cancel_after):result=self.execute(ident,provider)
        self.assertEqual(result['status'],'CANCELLED',result)
        task=self.core.tasks.get(result['child_task'])
        self.assertEqual(task['status'],'CANCELLED')
        self.assertTrue(self.core.db.one('SELECT revoked FROM grants WHERE id=?',(task['body']['grant_id'],))['revoked'])
        self.assertFalse(self.core.tasks.actions(task['id']))

    def test_cancel_before_admission_prevents_new_task_and_grant(self):
        _,_,ident,provider=self.begin_auto();approve=goals.command
        def cancel_before(root,value):
            if value['action']=='approve':command(root,{'action':'lesson_repair_return_cancel','id':ident})
            return approve(root,value)
        with patch.object(goals,'command',cancel_before):result=self.execute(ident,provider)
        self.assertEqual(result['status'],'CANCELLED',result)
        self.assertFalse(Plans(self.core.db).get(result['child_goal'])['task_id'])

    def test_changed_admitted_binding_is_blocked_before_first_business_effect(self):
        _,tid,ident,provider=self.begin_auto();approve=goals.command
        from sdk.protocol import canonical
        def wrong_binding(root,value):
            result=approve(root,value)
            if value['action']=='approve':
                task=self.core.tasks.get(result['task_id']);cap=task['body']['steps'][0]['capability']
                binding=self.core.tasks.get(tid)['bindings'];old=next(v for k,v in binding.items() if k.startswith('plugin.'))
                with self.core.db.transaction() as tx:tx.execute('UPDATE tasks SET bindings=? WHERE id=?',(canonical({**task['bindings'],cap:old}),task['id']))
            return result
        with patch.object(goals,'command',wrong_binding):result=self.execute(ident,provider)
        self.assertEqual((result['status'],result['error']),('FAILED','repair_source_changed'))
        self.assertFalse(self.core.tasks.actions(result['child_task']))

for name in ('setUp','tearDown','publish','req','detail','plan','code','source','seed','create','edit_source','rules','candidate','enable','failed','prepare_repair','begin_repair','bind_repair'):
    setattr(RepairReturnTests,name,getattr(fixture.LessonRepairTests,name))

if __name__=='__main__':unittest.main()
