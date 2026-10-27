"""Real local pipelines: version linkage, no prefix replay and revocation counterexamples."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_goal_plans as base
import test_assistant_goals as assistant_base
from host import goals
from host.core import Core
from host.completion import command as feedback, refresh
from host import work_revisions
from modules.task_resource.scheduling import Scheduling
from sdk.protocol import canonical, decode


class WorkRevisions(unittest.TestCase):
    setUp = base.GoalPlans.setUp
    tearDown = base.GoalPlans.tearDown
    publish = base.GoalPlans.publish
    req = base.GoalPlans.req
    create = base.GoalPlans.create
    detail = base.GoalPlans.detail
    approve = base.GoalPlans.approve
    def code(self, expected, fn, *args, **kwargs):
        from sdk.protocol import CoreError
        with self.assertRaises(CoreError) as exc:fn(*args,**kwargs)
        self.assertEqual(exc.exception.code,expected)

    def original(self, context=None):
        value={'action':'create','request':self.req()}
        if context is not None:value['context']=context
        ident=goals.command(self.root,value)['id']
        goals.command(self.root,{'action':'edit','id':ident,'revision':1,'proposal':base.proposal(chain=True)})
        tid=self.approve(ident)
        self.assertEqual(self.core.run_task(tid)['status'],'SUCCEEDED')
        return ident,tid

    def request(self, ident, **changes):
        d=self.detail(ident)
        return {'action':'rework','id':ident,'revision':d['plan']['revision'],'work_revision':d['work']['revision'] if d['work'] else 1,
                'request_id':'followup-request-'+str(d['work']['revision'] if d['work'] else 1),'kind':'new_requirement',
                'goal':'保留已经完成的转换，修改最后一步','note':'第二步需要调整','start_step':2,**changes}

    def rework(self,ident,**changes):return goals.command(self.root,self.request(ident,**changes))['id']

    def reject(self,tid,request='late-reject'):
        current=refresh(self.core,tid)
        return feedback(self.core,{'action':'completion_feedback','id':tid,'request_id':request,
            'fingerprint':current['fingerprint'],'kind':'reject','note':'后来发现需要改进'})

    def test_owner_identity_persists_and_no_extra_authority_on_draft(self):
        ident,tid=self.original();identity=self.core.identity.describe()
        before=self.core.db.all('SELECT * FROM grants'); child=self.rework(ident)
        self.assertEqual(self.core.db.all('SELECT * FROM grants'),before)
        self.assertEqual(len(self.core.db.all('SELECT * FROM tasks')),1)
        self.core.close();self.core=Core(self.root)
        w=self.detail(child)['work']
        self.assertEqual(w['assistant_id'],identity['assistant_id']);self.assertEqual(w['current_goal'],child)
        self.assertEqual(w['owner_bot_id'],'default');self.assertEqual(len(w['versions']),2)
        self.assertTrue(w['cumulative_budget_enforced'])
        self.assertEqual(w['budget']['spent_units'],3)

    def test_only_suffix_executes_and_original_actions_are_unchanged(self):
        ident,tid=self.original();old=self.core.tasks.actions(tid); child=self.rework(ident)
        d=self.detail(child);self.assertEqual(d['plan']['proposal']['input_text'],'JARVIS 中文')
        self.assertEqual(len(d['plan']['proposal']['steps']),1)
        new=self.approve(child);self.assertEqual(self.core.run_task(new)['status'],'SUCCEEDED')
        self.assertEqual(self.core.tasks.actions(tid),old)
        self.assertEqual(len(self.core.tasks.actions(new)),2)
        self.assertEqual(self.detail(child)['work']['spent_cost_units'],5)
        self.assertEqual(len(self.core.db.all('SELECT * FROM model_calls')),0)

    def test_idempotent_request_survives_restart_and_changed_payload_conflicts(self):
        ident,_=self.original();req=self.request(ident);first=goals.command(self.root,req)
        self.core.close();self.core=Core(self.root)
        second=goals.command(self.root,req)
        self.assertEqual(first['id'],second['id']);self.assertTrue(second['existing'])
        self.code('conflict',goals.command,self.root,{**req,'note':'changed'})
        self.assertEqual(len(self.core.db.all('SELECT * FROM goal_plans')),2)

    def test_competing_stale_revision_does_not_fork(self):
        ident,_=self.original();req=self.request(ident);goals.command(self.root,req)
        self.code('work_conflict',goals.command,self.root,{**req,'request_id':'different-request'})
        self.assertEqual(len(self.core.db.all('SELECT * FROM goal_plans')),2)

    def test_new_requirement_preserves_parent_evaluation(self):
        ident,tid=self.original();before=refresh(self.core,tid);self.rework(ident)
        after=refresh(self.core,tid)
        self.assertEqual(before['fingerprint'],after['fingerprint']);self.assertEqual(before['state'],after['state'])
        self.assertEqual(self.core.db.all('SELECT * FROM completion_feedback'),[])

    def test_correction_records_negative_feedback_and_child_can_repair(self):
        ident,tid=self.original();old=self.core.tasks.actions(tid)
        child=self.rework(ident,kind='correction');self.assertEqual(refresh(self.core,tid)['state'],'NEEDS_CORRECTION')
        new=self.approve(child);self.assertEqual(self.core.run_task(new)['status'],'SUCCEEDED')
        self.assertEqual(self.core.tasks.actions(tid),old)
        self.assertEqual(len(self.core.db.all('SELECT * FROM completion_feedback')),1)

    def test_late_feedback_blocks_unadmitted_child_without_grant(self):
        ident,tid=self.original();child=self.rework(ident);self.reject(tid)
        self.code('rework_source_changed',self.approve,child)
        self.assertIsNone(self.core.db.one('SELECT * FROM grants WHERE id=?',(child+'-execute',)))

    def test_late_feedback_blocks_admitted_child_before_effect(self):
        ident,tid=self.original();child=self.rework(ident);new=self.approve(child);self.reject(tid)
        result=self.core.run_task(new)
        self.assertEqual(result['status'],'WAITING');self.assertEqual(result['error'],'rework_source_changed')
        self.assertEqual(self.core.tasks.actions(new),[])

    def test_completed_child_is_invalidated_by_late_source_feedback(self):
        ident,tid=self.original();child=self.rework(ident);new=self.approve(child);self.core.run_task(new)
        self.reject(tid)
        self.assertEqual(refresh(self.core,new)['state'],'INVALIDATED')

    def test_source_file_change_blocks_before_effect(self):
        ident,tid=self.original();child=self.rework(ident);new=self.approve(child)
        path=self.root/decode(self.core.tasks.actions(tid)[-1]['result'])['relative_path'];path.write_text('changed')
        self.assertEqual(self.core.run_task(new)['error'],'rework_source_changed')
        self.assertEqual(self.core.tasks.actions(new),[])

    def test_reused_capability_switch_invalidates_prefix(self):
        ident,_=self.original();child=self.rework(ident);new=self.approve(child);self.publish('!')
        self.assertEqual(self.core.run_task(new)['error'],'rework_source_changed')
        self.assertEqual(self.core.tasks.actions(new),[])

    def test_context_revocation_propagates_to_child(self):
        ident,_=self.original({'scope':'personal','enabled':False,'chat_id':'','turn_id':''})
        child=self.rework(ident);new=self.approve(child)
        self.core.db.connection.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical({'redacted':True}),ident))
        self.assertEqual(self.core.run_task(new)['error'],'rework_source_changed')

    def test_pinned_input_cannot_be_edited_or_automatically_replanned(self):
        ident,_=self.original();child=self.rework(ident);d=self.detail(child)
        p={**d['plan']['proposal'],'input_text':'偷偷替换前段输出'}
        self.code('rework_invalid',goals.command,self.root,{'action':'edit','id':child,'revision':1,'proposal':p})
        self.code('rework_invalid',goals.command,self.root,{'action':'amend','id':child,'revision':1,'goal':'new','input_text':'new'})

    def test_full_rework_allows_new_input_but_keeps_original(self):
        ident,tid=self.original();child=self.rework(ident,start_step=1);d=self.detail(child)
        p={**d['plan']['proposal'],'input_text':'new input'}
        goals.command(self.root,{'action':'edit','id':child,'revision':1,'proposal':p})
        new=self.approve(child);self.assertEqual(self.core.run_task(new)['status'],'SUCCEEDED')
        self.assertEqual(decode(self.core.tasks.actions(new)[0]['result'])['text'],'NEW INPUT')
        self.assertEqual(decode(self.core.tasks.actions(tid)[0]['result'])['text'],'JARVIS 中文')

    def test_whole_work_cancel_stops_draft_and_preserves_original_success(self):
        ident,tid=self.original();child=self.rework(ident)
        req={'action':'cancel_work','id':ident,'work_revision':2}
        goals.command(self.root,req);goals.command(self.root,req)
        self.assertEqual(self.core.tasks.get(tid)['status'],'SUCCEEDED')
        self.assertEqual(self.detail(child)['plan']['status'],'CANCELLED')
        self.code('work_conflict',self.approve,child)
        self.code('work_conflict',self.rework,ident,request_id='after-cancel-01')

    def test_whole_work_cancel_revokes_queued_child(self):
        ident,_=self.original();child=self.rework(ident)
        req={'action':'approve_and_run','id':child,'revision':1}
        new=goals.command(self.root,req)['task_id']
        goals.command(self.root,{'action':'cancel_work','id':ident,'work_revision':2})
        self.assertEqual(self.core.db.one('SELECT revoked FROM grants WHERE id=?',(child+'-execute',))['revoked'],1)
        Scheduling(self.core.db).admit_waiting()
        self.assertEqual(self.core.tasks.get(new)['status'],'CANCELLED')
        self.code('invalid_state',self.core.run_task,new)
        self.assertEqual(self.core.tasks.actions(new),[])
        self.code('work_conflict',goals.command,self.root,req)

    def test_followup_limit_is_shared_across_versions(self):
        ident,_=self.original()
        for i in range(3):
            ident=self.rework(ident,start_step=1,request_id='bounded-'+str(i));self.core.run_task(self.approve(ident))
        self.code('work_limit',self.rework,ident,start_step=1,request_id='bounded-overflow')
        self.assertEqual(len(self.core.db.all('SELECT * FROM goal_plans')),4)

    def test_unfinished_and_non_linear_sources_are_rejected(self):
        ident=self.create();goals.command(self.root,{'action':'edit','id':ident,'revision':1,'proposal':base.proposal(chain=True)})
        tid=self.approve(ident);self.code('rework_unsupported',self.rework,ident)
        self.core.run_task(tid)
        p=self.detail(ident)['plan']['proposal'];p['steps'][1]['source']='input'
        self.core.db.connection.execute('UPDATE goal_plans SET proposal=? WHERE id=?',(canonical(p),ident))
        self.code('rework_unsupported',self.rework,ident)

    def test_legacy_work_adoption_does_not_fabricate_admission_history(self):
        ident,tid=self.original()
        self.core.db.connection.execute('DELETE FROM work_allocations WHERE root_goal=?',(ident,))
        self.core.db.connection.execute('DELETE FROM work_budgets WHERE root_goal=?',(ident,))
        self.core.db.connection.execute('DELETE FROM work_revisions WHERE goal_id=?',(ident,))
        self.core.db.connection.execute('DELETE FROM work_owners WHERE root_goal=?',(ident,))
        self.assertIsNone(self.detail(ident)['work']);self.core.close();self.core=Core(self.root)
        self.assertIsNone(self.detail(ident)['work'])
        child=self.rework(ident)
        self.assertEqual(self.detail(child)['work']['registration'],'followup_adoption')

    def test_rejection_at_effect_checkpoint_does_not_replay_or_confirm(self):
        ident,tid=self.original();child=self.rework(ident);new=self.approve(child)
        original=self.core.registry.execute
        def changed(*args):
            self.reject(tid);return original(*args)
        with patch.object(self.core.registry,'execute',side_effect=changed):result=self.core.run_task(new)
        self.assertEqual(result['status'],'WAITING')
        self.assertEqual(self.core.tasks.actions(new)[0]['status'],'UNKNOWN')
        self.assertFalse(any(a['status']=='CONFIRMED' for a in self.core.tasks.actions(new)))

    def test_crash_before_and_after_commit_leave_one_link_and_no_new_grants(self):
        ident,_=self.original();req=self.request(ident,kind='correction')
        marker={'fixture_root':str(self.root.resolve()),'request':req,'crash_event':'work.revision_created'}
        (self.root/'handoff-crash-fixture.json').write_text(json.dumps(marker),encoding='utf-8')
        for mode,expected in [('before',91),('after',92)]:
            result=subprocess.run([sys.executable,'-m','tools.handoff_crash_worker',str(self.root),mode],cwd=base.ROOT,timeout=30)
            self.assertEqual(result.returncode,expected)
            self.assertEqual(len(self.core.db.all('SELECT * FROM goal_plans')),1 if mode=='before' else 2)
            self.assertEqual(len(self.core.db.all('SELECT * FROM completion_feedback')),0 if mode=='before' else 1)
        child=goals.command(self.root,req)['id']
        self.assertIsNone(self.core.db.one('SELECT * FROM grants WHERE id=?',(child+'-execute',)))
        self.assertEqual(len(self.core.db.all('SELECT * FROM work_revisions')),2)

    def test_chat_projection_delivery_and_archival_follow_root(self):
        from host import assistant
        from modules.dialogue.store import Dialogues
        from modules.workspace.sessions import Sessions
        chat=assistant_base.AssistantGoals.chat(self)
        ident=assistant.goal_from_turn(self.root,'chat-turn-1')['id']
        goals.command(self.root,{'action':'edit','id':ident,'revision':1,'proposal':base.proposal(chain=True)})
        self.core.run_task(self.approve(ident));child=self.rework(ident);new=self.approve(child)
        self.assertEqual(self.core.run_task(new)['status'],'SUCCEEDED')
        chats=Dialogues(self.root);sessions=Sessions(self.root)
        try:
            linked=assistant.projection(self.root,chats.read(chat))['turns'][0]['linked_goal']
            self.assertEqual(linked['id'],ident);self.assertEqual(linked['work']['current_goal'],child)
            self.assertTrue(any(f['path'].startswith('artifacts/'+new+'/') for f in sessions.files(chat)['files']))
            latest=self.rework(child,start_step=1);tid=self.approve(latest)
            chats.update(chat,{'archived':True})
            self.assertEqual(self.core.run_task(tid)['error'],'rework_source_changed')
            self.assertEqual(self.core.tasks.actions(tid),[])
        finally:sessions.close();chats.close()

    def test_external_source_and_unknown_effect_are_never_replayed(self):
        ident,tid=self.original()
        self.core.db.connection.execute("UPDATE actions SET status='UNKNOWN' WHERE task_id=? AND step_id='step-1'",(tid,))
        self.code('rework_source_changed',self.rework,ident)
        self.core.db.connection.execute("UPDATE actions SET status='CONFIRMED' WHERE task_id=? AND step_id='step-1'",(tid,))
        p=self.detail(ident)['plan']['proposal'];p['steps'][0]['capability']='mcp.external.v1'
        self.core.db.connection.execute('UPDATE goal_plans SET proposal=? WHERE id=?',(canonical(p),ident))
        self.code('rework_unsupported',self.rework,ident)

    def review(self,child):
        d=self.detail(child)
        return {'action':'review_rework_source','id':child,'revision':d['plan']['revision'],
                'work_revision':d['work']['revision'],'note':'已核对迟到反馈，仅影响末步；保留前段输出'}

    def test_explicit_source_review_recovers_unadmitted_draft_without_erasing_feedback(self):
        ident,tid=self.original();child=self.rework(ident);self.reject(tid)
        old={'action':'approve','id':child,'revision':1};review=self.review(child)
        goals.command(self.root,review)
        self.code('conflict',goals.command,self.root,old)
        self.assertEqual(refresh(self.core,tid)['state'],'NEEDS_CORRECTION')
        self.assertEqual(len(self.core.db.all('SELECT * FROM tasks')),1)
        self.assertEqual(self.core.run_task(self.approve(child))['status'],'SUCCEEDED')
        self.assertEqual(len(self.core.db.all("SELECT * FROM events WHERE kind='work.source_reviewed'")),1)
        self.code('work_conflict',goals.command,self.root,review)

    def test_source_review_cannot_rewrite_admitted_task(self):
        ident,tid=self.original();child=self.rework(ident);new=self.approve(child);self.reject(tid)
        self.code('work_conflict',goals.command,self.root,self.review(child))
        self.assertEqual(self.core.run_task(new)['error'],'rework_source_changed')

    def test_source_review_does_not_bless_changed_file(self):
        ident,tid=self.original();child=self.rework(ident)
        path=self.root/decode(self.core.tasks.actions(tid)[-1]['result'])['relative_path'];path.write_text('changed')
        self.code('rework_source_changed',goals.command,self.root,self.review(child))
        self.assertEqual(self.detail(child)['plan']['revision'],1)

    def test_chat_domain_switch_cannot_carry_old_source_into_new_domain(self):
        from host import assistant, memory_domains
        from modules.context_knowledge.domains import Domains
        chat=assistant_base.AssistantGoals.chat(self)
        ident=assistant.goal_from_turn(self.root,'chat-turn-1')['id']
        goals.command(self.root,{'action':'edit','id':ident,'revision':1,'proposal':base.proposal(chain=True)})
        self.core.run_task(self.approve(ident));child=self.rework(ident);new=self.approve(child)
        domain=Domains(self.core.db).create('personal','world','另一资料域',False)['id']
        memory_domains.command(self.root,{'action':'bind','chat_id':chat,'scope':domain,'revision':0})
        self.assertEqual(self.core.run_task(new)['error'],'rework_source_changed')
        self.assertEqual(self.core.tasks.actions(new),[])


if __name__=='__main__':unittest.main()
