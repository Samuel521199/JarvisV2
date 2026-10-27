"""Real work versions: conservative impact, evidence reopening and bounded costs."""
import copy
import unittest
from unittest.mock import patch

import test_work_revisions as base
import test_assistant_goals as chatbase
from host import goals
from host import assistant
from host.core import Core
from sdk.protocol import decode, digest


class WorkflowClosure(unittest.TestCase):
    setUp=base.WorkRevisions.setUp
    tearDown=base.WorkRevisions.tearDown
    publish=base.WorkRevisions.publish
    req=base.WorkRevisions.req
    detail=base.WorkRevisions.detail
    approve=base.WorkRevisions.approve
    original=base.WorkRevisions.original
    code=base.WorkRevisions.code
    reject=base.WorkRevisions.reject
    chat=chatbase.AssistantGoals.chat

    def original_chat(self):
        chat=self.chat();ident=assistant.goal_from_turn(self.root,'chat-turn-1')['id']
        goals.command(self.root,{'action':'edit','id':ident,'revision':1,'proposal':base.base.proposal(chain=True)})
        tid=self.approve(ident);self.core.run_task(tid)
        return chat,ident,tid

    def analysis_request(self, ident):
        d=self.detail(ident);p=copy.deepcopy(d['plan']['proposal'])
        p['steps'][-1]['expected']='新核对：结果保留中文'
        return {'action':'analyze_rework','id':ident,'revision':d['plan']['revision'],
                'work_revision':d['work']['revision'],'goal':d['plan']['request']['goal'],'proposal':p}

    def application(self, req):
        analysis=goals.command(self.root,req)
        return {**req,'action':'rework_auto','request_id':'auto-followup-01','kind':'new_requirement',
                'note':'只改变后段要求','analysis_digest':analysis['analysis_digest']}

    def rules(self, text='JARVIS 中文', step=1, complete=True):
        rules={'coverage':'complete','criteria':[{'id':'literal' if i==step else 'intermediate-'+str(i),
            'step_id':'step-'+str(i),'check':'text_equals','expected':text} for i in range(1,step+1)]}
        if complete:rules['requirements']=[{'id':'output','text':'字面输出等于约定文本','kind':'literal','criterion_ids':['literal']}]
        return rules

    def execute_child(self, request, rules=None):
        child=goals.command(self.root,request)['id']
        tid=goals.command(self.root,{'action':'approve','id':child,'revision':1,'acceptance':rules or self.rules()})['task_id']
        self.assertEqual(self.core.run_task(tid)['status'],'SUCCEEDED')
        return child,tid

    def test_second_step_change_reuses_prefix_without_new_task_or_grant_during_analysis(self):
        ident,tid=self.original();old=self.core.tasks.actions(tid);req=self.analysis_request(ident)
        grants=self.core.db.all('SELECT * FROM grants');tasks=self.core.db.all('SELECT * FROM tasks')
        result=goals.command(self.root,req)
        self.assertEqual(result['start_step'],2);self.assertEqual(result['reused_steps'],[1]);self.assertEqual(result['planned_cost_units'],2)
        self.assertFalse(result['semantic_impact_verified'])
        self.assertEqual(self.core.db.all('SELECT * FROM grants'),grants);self.assertEqual(self.core.db.all('SELECT * FROM tasks'),tasks)
        child,new=self.execute_child(self.application(req))
        self.assertEqual(self.core.tasks.actions(tid),old);self.assertEqual(self.core.tasks.get(new)['spent'],2)
        self.assertEqual(self.detail(child)['work']['spent_cost_units'],5)
        event=self.core.db.one("SELECT data FROM events WHERE kind='work.impact_applied'")
        audit=decode(event['data'])
        self.assertEqual(audit['analysis'],result)
        self.assertEqual(set(audit),{'goal_id','parent_goal','analysis','complete_proposal_sha256','revised_goal_sha256'})
        self.assertEqual(audit['complete_proposal_sha256'],digest(req['proposal']))
        self.assertEqual(audit['revised_goal_sha256'],digest(req['goal']))
        for text in (req['goal'],req['proposal']['input_text'],req['proposal']['steps'][-1]['expected']):
            self.assertNotIn(text,event['data'])

    def test_new_input_forces_full_rework_and_is_actually_used(self):
        ident,tid=self.original();old=self.core.tasks.actions(tid);req=self.analysis_request(ident)
        req['proposal']['input_text']='new 中文'
        self.assertEqual(goals.command(self.root,req)['start_step'],1)
        child,new=self.execute_child(self.application(req),self.rules('NEW 中文',step=2))
        self.assertEqual(self.core.tasks.get(new)['spent'],3)
        self.assertEqual(self.detail(child)['work_closure']['state'],'COMPLETE')
        self.assertEqual(self.core.tasks.actions(tid),old)

    def test_goal_text_change_conservatively_forces_full_rework(self):
        ident,_=self.original();req=self.analysis_request(ident);req['goal']='追加语义要求无法证明只影响后段'
        result=goals.command(self.root,req)
        self.assertEqual(result['start_step'],1);self.assertIn('goal_changed',result['reasons'])

    def test_first_step_and_binding_changes_force_full_rework(self):
        ident,_=self.original();req=self.analysis_request(ident);req['proposal']['steps'][0]['expected']='changed'
        self.assertEqual(goals.command(self.root,req)['start_step'],1)
        req=self.analysis_request(ident);self.publish('!')
        self.assertEqual(goals.command(self.root,req)['start_step'],1)

    def test_appending_and_removing_tail_remain_valid_and_bounded(self):
        ident,_=self.original();req=self.analysis_request(ident)
        original=self.detail(ident)['plan']['proposal'];req['proposal']=copy.deepcopy(original)
        req['proposal']['steps'].append({**original['steps'][-1],'expected':'third'})
        result=goals.command(self.root,req)
        self.assertEqual(result['start_step'],2);self.assertEqual(result['planned_cost_units'],3)
        # The existing protocol cannot pin the last step as an empty old suffix;
        # rerun that last step conservatively, then the appended step.
        req['proposal']=copy.deepcopy(original);req['proposal']['steps'].pop()
        self.assertEqual(goals.command(self.root,req)['start_step'],1)
        child,new=self.execute_child(self.application(req))
        self.assertEqual(self.core.tasks.get(new)['spent'],2)

    def test_no_change_or_summary_only_does_not_create_another_version(self):
        ident,_=self.original();req=self.analysis_request(ident);req['proposal']=self.detail(ident)['plan']['proposal']
        req['proposal']['summary']='仅修改说明，不增加重复执行'
        self.code('rework_no_change',goals.command,self.root,req)
        self.assertEqual(len(self.detail(ident)['work']['versions']),1)

    def test_non_linear_or_unresolved_plan_rejected(self):
        ident,_=self.original();req=self.analysis_request(ident);req['proposal']['steps'][1]['source']='input'
        self.code('rework_unsupported',goals.command,self.root,req)
        req=self.analysis_request(ident);req['proposal']['questions']=['尚未明确']
        self.code('rework_unsupported',goals.command,self.root,req)

    def test_edited_candidate_cannot_use_old_analysis(self):
        ident,_=self.original();req=self.application(self.analysis_request(ident));req['proposal']['input_text']='changed'
        self.code('rework_analysis_changed',goals.command,self.root,req)
        self.assertEqual(len(self.detail(ident)['work']['versions']),1)

    def test_late_feedback_and_tool_switch_invalidate_analysis(self):
        ident,tid=self.original();req=self.application(self.analysis_request(ident));self.reject(tid)
        self.code('rework_analysis_changed',goals.command,self.root,req)
        req=self.application(self.analysis_request(ident));self.publish('!')
        self.code('rework_analysis_changed',goals.command,self.root,req)
        self.assertEqual(len(self.detail(ident)['work']['versions']),1)

    def test_missing_source_artifact_rejects_analysis(self):
        ident,tid=self.original();req=self.analysis_request(ident)
        path=self.root/decode(self.core.tasks.actions(tid)[-1]['result'])['relative_path'];path.write_text('tampered')
        self.code('rework_source_changed',goals.command,self.root,req)

    def test_retry_after_restart_returns_same_draft_without_extra_authority(self):
        ident,_=self.original();req=self.application(self.analysis_request(ident));grants=self.core.db.all('SELECT * FROM grants')
        first=goals.command(self.root,req);self.core.close();self.core=Core(self.root)
        second=goals.command(self.root,req);self.assertEqual(first['id'],second['id']);self.assertTrue(second['existing'])
        self.assertEqual(self.core.db.all('SELECT * FROM grants'),grants)
        self.code('conflict',goals.command,self.root,{**req,'note':'不同请求内容'})

    def test_competing_analysis_cannot_fork_current_work(self):
        ident,_=self.original();req=self.application(self.analysis_request(ident));goals.command(self.root,req)
        self.code('work_conflict',goals.command,self.root,{**req,'request_id':'competing-auto-02'})

    def test_atomic_failure_before_append_leaves_no_draft_or_feedback(self):
        ident,_=self.original();req={**self.application(self.analysis_request(ident)),'kind':'correction'}
        with patch('modules.task_resource.works.Works.append',side_effect=RuntimeError('transaction fault')):
            with self.assertRaises(RuntimeError):goals.command(self.root,req)
        self.assertEqual(len(self.core.db.all('SELECT * FROM goal_plans')),1)
        self.assertEqual(self.core.db.all('SELECT * FROM completion_feedback'),[])

    def test_current_version_closes_and_late_feedback_reopens_all_entrypoints(self):
        ident,tid=self.original();child,new=self.execute_child(self.application(self.analysis_request(ident)))
        a=self.detail(ident)['work_closure'];b=self.detail(child)['work_closure']
        self.assertEqual(a,b);self.assertEqual(a['state'],'COMPLETE');self.assertIsNone(a['quality_score'])
        self.reject(new);self.assertEqual(self.detail(ident)['work_closure']['state'],'NEEDS_EVIDENCE')
        self.assertEqual(self.core.tasks.get(new)['status'],'SUCCEEDED')

    def test_original_success_cannot_hide_draft_or_failed_acceptance(self):
        ident,_=self.original();req=self.application(self.analysis_request(ident));child=goals.command(self.root,req)['id']
        self.assertEqual(self.detail(ident)['work_closure']['state'],'NEEDS_REVIEW')
        tid=goals.command(self.root,{'action':'approve','id':child,'revision':1,'acceptance':self.rules('wrong')})['task_id']
        self.assertEqual(self.detail(ident)['work_closure']['state'],'IN_PROGRESS')
        self.core.run_task(tid);closed=self.detail(ident)['work_closure']
        self.assertEqual(closed['state'],'NEEDS_EVIDENCE');self.assertEqual(closed['condition_score'],0)

    def test_partial_checks_do_not_close_work_even_at_one_hundred_percent(self):
        ident,_=self.original();child,_=self.execute_child(self.application(self.analysis_request(ident)),self.rules(complete=False))
        state=self.detail(child)['work_closure'];self.assertEqual(state['condition_score'],100)
        self.assertEqual(state['completion_state'],'SATISFIED');self.assertFalse(state['complete'])

    def test_source_feedback_invalidates_completed_descendant(self):
        ident,tid=self.original();child,_=self.execute_child(self.application(self.analysis_request(ident)))
        self.reject(tid);current=self.detail(child)['work_closure']
        self.assertFalse(current['complete']);self.assertEqual(current['completion_state'],'INVALIDATED')

    def test_whole_work_stop_preserves_completed_task_and_prevents_auto_followup(self):
        ident,tid=self.original();req=self.application(self.analysis_request(ident));d=self.detail(ident)
        goals.command(self.root,{'action':'cancel_work','id':ident,'work_revision':d['work']['revision']})
        self.assertEqual(self.detail(ident)['work_closure']['state'],'STOPPED')
        self.assertEqual(self.core.tasks.get(tid)['status'],'SUCCEEDED')
        self.code('work_conflict',goals.command,self.root,req)

    def test_unavailable_observer_cannot_keep_work_complete(self):
        ident,_=self.original();child,_=self.execute_child(self.application(self.analysis_request(ident)))
        with patch('host.completion.refresh',side_effect=RuntimeError('observer unavailable')):
            self.assertEqual(self.detail(child)['work_closure']['state'],'NEEDS_EVIDENCE')

    def test_missing_budget_allocation_cannot_close_work(self):
        ident,_=self.original();child,tid=self.execute_child(self.application(self.analysis_request(ident)))
        self.core.db.connection.execute('DELETE FROM work_allocations WHERE task_id=?',(tid,))
        value=self.detail(child)['work_closure'];self.assertFalse(value['complete']);self.assertIn('budget_evidence_invalid',value['reasons'])

    def test_invalid_lowered_total_cannot_leave_a_completed_projection(self):
        ident,_=self.original();child,_=self.execute_child(self.application(self.analysis_request(ident)))
        self.core.db.connection.execute('UPDATE work_budgets SET limit_units=1 WHERE root_goal=?',(ident,))
        value=self.detail(child)['work_closure'];self.assertFalse(value['complete']);self.assertIn('budget_overcommitted',value['reasons'])

    def test_conversation_context_follows_current_draft_and_retains_historical_link(self):
        chat,ident,_=self.original_chat();child=goals.command(self.root,self.application(self.analysis_request(ident)))['id']
        value=assistant.context(self.root,chat)[0]
        self.assertEqual(value['id'],child);self.assertEqual(value['root_goal'],ident)
        self.assertEqual(value['confirmed_output'],'');self.assertEqual(value['work_closure']['state'],'NEEDS_REVIEW')

    def test_conversation_can_cancel_current_child_and_remembers_operation(self):
        from modules.dialogue.store import Dialogues
        chat,ident,tid=self.original_chat();child=goals.command(self.root,self.application(self.analysis_request(ident)))['id']
        self.chat('cancel-current',{**chatbase.action('cancel',target=child),'target_revision':1},chat)
        self.assertEqual(assistant.accept(self.root,{'turn_id':'cancel-current'})['id'],child)
        self.assertEqual(self.detail(ident)['work_closure']['state'],'STOPPED')
        self.assertEqual(self.core.tasks.get(tid)['status'],'SUCCEEDED')
        store=Dialogues(self.root)
        try:projected=assistant.projection(self.root,store.read(chat))
        finally:store.close()
        self.assertEqual(projected['turns'][-1]['applied_action']['id'],child)

    def test_conversation_stale_parent_and_foreign_chat_cannot_target_child(self):
        chat,ident,_=self.original_chat();revision=self.detail(ident)['plan']['revision']
        self.chat('old-resume',{**chatbase.action('resume',target=ident),'target_revision':revision},chat)
        child=goals.command(self.root,self.application(self.analysis_request(ident)))['id']
        self.code('work_conflict',assistant.accept,self.root,{'turn_id':'old-resume'})
        self.chat('foreign-cancel',{**chatbase.action('cancel',target=child),'target_revision':1})
        self.code('denied',assistant.accept,self.root,{'turn_id':'foreign-cancel'})
        self.assertEqual(self.detail(child)['plan']['status'],'REVIEW')

    def test_conversation_and_workbench_share_current_closure_without_erasing_old_result(self):
        from modules.dialogue.store import Dialogues
        chat,ident,_=self.original_chat();child,_=self.execute_child(self.application(self.analysis_request(ident)))
        state=assistant.context(self.root,chat)[0]
        self.assertEqual(state['id'],child);self.assertEqual(state['work_closure'],self.detail(child)['work_closure'])
        store=Dialogues(self.root)
        try:linked=assistant.projection(self.root,store.read(chat))['turns'][0]['linked_goal']
        finally:store.close()
        self.assertEqual(linked['id'],ident);self.assertEqual(linked['output'],'JARVIS 中文')
        self.assertEqual(linked['work_closure'],state['work_closure'])

    def test_conversation_does_not_expose_invalidated_ancestor_context(self):
        chat,ident,tid=self.original_chat();self.execute_child(self.application(self.analysis_request(ident)))
        self.reject(tid);value=assistant.context(self.root,chat)[0]
        self.assertFalse(value['context_current']);self.assertEqual(value['confirmed_output'],'')
        self.assertEqual(value['goal'],'');self.assertEqual(value['memory_dependencies'],[])
        self.assertIsNone(value['work_closure'])

    def test_changed_goal_or_input_cannot_misrepresent_partial_ancestor_as_full_rework(self):
        ident,_=self.original();child,_=self.execute_child(self.application(self.analysis_request(ident)))
        req=self.analysis_request(child);req['goal']='改变完整目标，需要重新检查最初的前段'
        self.code('rework_full_plan_required',goals.command,self.root,req)
        req=self.analysis_request(child);req['proposal']['input_text']='new source'
        self.code('rework_full_plan_required',goals.command,self.root,req)
        self.assertEqual(len(self.detail(child)['work']['versions']),2)

    def test_unchanged_input_and_goal_can_continue_a_local_suffix_after_prior_reuse(self):
        ident,tid=self.original();child,_=self.execute_child(self.application(self.analysis_request(ident)));old=self.core.tasks.actions(tid)
        req=self.analysis_request(child);req['proposal']['steps'][0]['expected']='新的局部核对，目标和输入保持不变'
        a=goals.command(self.root,req);self.assertTrue(a['ancestor_prefix_reused']);self.assertEqual(a['start_step'],1)
        third,_=self.execute_child({**self.application(req),'request_id':'auto-third-followup'})
        self.assertEqual(self.detail(third)['work_closure']['state'],'COMPLETE');self.assertEqual(self.core.tasks.actions(tid),old)


if __name__=='__main__':unittest.main()
