"""Requirement lineage across executed Work revisions and independent results."""
import copy
import json
import sqlite3
import unittest
from unittest.mock import patch
import test_quote_changes as base
from host import goals, quote_sources
from host.completion import command, refresh
from host.core import Core
from modules.task_resource import inheritance_checks as policy
from modules.task_resource.completion import Completion
from sdk.protocol import canonical, decode

GOAL=base.GOAL;INPUT=base.INPUT;REVISED=base.REVISED;INPUT90=base.INPUT90;REPLACE=base.REPLACE


class ReworkPolicy(unittest.TestCase):
    def review(self,note=REPLACE,goal=REVISED,text=INPUT90,kind='new_requirement',parent=None):
        parent=parent or base.ChangePolicy().review()
        return policy.analyze(goal,text,parent,INPUT,{'goal_id':'child','parent_goal':'root','ordinal':2,'note':note,'kind':kind},'receipt')

    def test_old_history_not_mutated(self):
        p=base.ChangePolicy().review();before=copy.deepcopy(p);r=self.review(parent=p)
        self.assertEqual(p,before);self.assertTrue(r['ready']);self.assertEqual(r['active_count'],5)
        self.assertEqual([n['text'] for n in r['requirements_history'] if n['state']=='replaced'],['预算不超过100元'])

    def test_unknown_source_issue_is_never_discarded(self):
        p=base.ChangePolicy().review();p['issues'].append({'code':'future_source_problem','blocking':False})
        self.assertFalse(self.review(parent=p)['ready'])

    def test_correction_cannot_change_conditions(self):
        r=self.review(kind='correction');self.assertTrue(r['blocking'])
        self.assertIn('rework_correction_must_keep',[i['code'] for i in r['issues']])

    def test_keep_does_not_hide_dropped_condition(self):
        self.assertTrue(self.review(note=policy.KEEP,goal=GOAL.replace('，保留来源引用',''),text=INPUT,kind='correction')['blocking'])

    def test_data_cannot_change_with_requirement(self):
        v=json.loads(INPUT90);v['offers'][0]['source']='forged'
        self.assertTrue(self.review(text=json.dumps(v))['blocking'])

    def test_implicit_overwrite_not_supported(self):
        self.assertTrue(self.review(note='预算改成90元')['blocking'])

    def test_old_attachment_remains_historical_input(self):
        p=base.ChangePolicy().review();p['sources'].append({'id':'file','kind':'reference','name':'quotes','text':INPUT,'status':'input_identical'})
        self.assertEqual(self.review(parent=p)['sources'][-2]['status'],'historical_input_identical')


class ReworkIntegration(unittest.TestCase):
    setUp=base.ChangeIntegration.setUp
    tearDown=base.ChangeIntegration.tearDown
    publish=base.ChangeIntegration.publish
    detail=base.ChangeIntegration.detail
    code=base.ChangeIntegration.code
    req=base.ChangeIntegration.req
    create=base.ChangeIntegration.create
    make=base.ChangeIntegration.make
    mutate=base.ChangeIntegration.mutate
    request=base.ChangeIntegration.request
    edit=base.ChangeIntegration.edit
    amend=base.ChangeIntegration.amend

    def review(self,ident):
        return goals.command(self.root,{'action':'review_quote_rework','id':ident,'revision':self.detail(ident)['plan']['revision']})

    def root_version(self,**kwargs):
        ident,_=self.make(**kwargs);r=base.ChangeIntegration.review(self,ident)
        tid=goals.command(self.root,self.request(ident,r))['task_id'];self.core.run_task(tid)
        return ident,tid

    def child(self,parent,goal=REVISED,note=REPLACE,kind='new_requirement',text=INPUT90,start=1):
        d=self.detail(parent)
        result=goals.command(self.root,{'action':'rework','id':parent,'revision':d['plan']['revision'],
            'work_revision':d['work']['revision'],'request_id':'inherit-'+str(len(d['work']['versions'])),
            'kind':kind,'note':note,'goal':goal,'start_step':start})
        self.edit(result['id'],text);return result['id']

    def finish(self,ident):
        r=self.review(ident);tid=goals.command(self.root,self.request(ident,r))['task_id']
        self.core.run_task(tid);return tid,self.detail(ident)

    def prepared(self):
        root,tid=self.root_version();return root,tid,self.child(root)

    def test_replacement_closes_without_rewriting_parent(self):
        root,old,child=self.prepared();before=self.core.tasks.actions(old)
        self.assertTrue(self.review(child)['ready']);tid,d=self.finish(child)
        self.assertEqual(d['completion']['state'],'VERIFIED');self.assertEqual(d['work_closure']['state'],'COMPLETE')
        self.assertEqual(self.core.tasks.actions(old),before);self.assertEqual(d['work']['spent_cost_units'],4)
        self.core.close();self.core=Core(self.root)
        self.assertEqual(self.detail(child)['completion']['fingerprint'],d['completion']['fingerprint'])

    def test_unknown_requirement_inherited_until_explicitly_withdrawn(self):
        goal=GOAL+'，必须保修三年';root,_=self.root_version(raw=goal,goal=goal)
        child=self.child(root,goal=goal,note=policy.KEEP,kind='correction',text=INPUT)
        tid,d=self.finish(child);self.assertEqual(d['completion']['state'],'WAITING_EVIDENCE')
        self.assertFalse(d['completion']['method_available'])
        self.code('feedback_invalid',command,self.core,{'action':'completion_feedback','id':tid,'request_id':'cannot-bless-child','fingerprint':d['completion']['fingerprint'],'kind':'accept','note':''})
        final=self.child(child,goal=GOAL,note='撤销要求「必须保修三年」',text=INPUT)
        _,d=self.finish(final);self.assertEqual(d['completion']['state'],'VERIFIED')

    def test_wrong_result_can_be_corrected_without_weakening_requirements(self):
        self.publish(True);root,old=self.root_version();self.assertEqual(self.detail(root)['completion']['state'],'NEEDS_CORRECTION')
        before=self.core.tasks.actions(old);self.publish(False)
        child=self.child(root,goal=GOAL,note=policy.KEEP,kind='correction',text=INPUT)
        _,d=self.finish(child);self.assertEqual(d['completion']['state'],'VERIFIED');self.assertEqual(self.core.tasks.actions(old),before)
        self.assertEqual(self.detail(root)['completion']['state'],'NEEDS_CORRECTION')

    def test_successful_wrong_child_is_not_verified(self):
        root,_=self.root_version();self.publish(True);child=self.child(root)
        _,d=self.finish(child);self.assertEqual(d['task']['status'],'SUCCEEDED');self.assertEqual(d['completion']['state'],'NEEDS_CORRECTION')
        self.assertFalse(d['completion']['method_available'])

    def test_dropped_survivor_blocks_admission(self):
        root,_=self.root_version();child=self.child(root,goal=REVISED.replace('，保留来源引用',''))
        before=self.core.db.all('SELECT * FROM grants');r=self.review(child)
        self.code('acceptance_invalid',goals.command,self.root,self.request(child,r))
        self.assertIsNone(self.detail(child)['task']);self.assertEqual(self.core.db.all('SELECT * FROM grants'),before)

    def test_unknown_addition_stays_partial(self):
        root,_=self.root_version();child=self.child(root,goal=GOAL+'，必须保修三年',note='新增要求「必须保修三年」',text=INPUT)
        _,d=self.finish(child);self.assertEqual(d['completion']['state'],'WAITING_EVIDENCE')

    def test_missing_parent_source_acceptance_rejected(self):
        root,_=self.make();tid=goals.command(self.root,{'action':'approve','id':root,'revision':self.detail(root)['plan']['revision']})['task_id']
        self.core.run_task(tid);child=self.child(root)
        self.code('acceptance_invalid',self.review,child)

    def test_parent_raw_source_change_invalidates_before_effect(self):
        _,_,child=self.prepared();r=self.review(child);tid=goals.command(self.root,self.request(child,r))['task_id']
        self.mutate('text',GOAL+'，必须保修三年',True);self.core.run_task(tid)
        self.assertEqual(self.core.tasks.get(tid)['status'],'WAITING');self.assertEqual(self.core.tasks.actions(tid),[])

    def test_source_change_between_effects_stops_delivery(self):
        _,_,child=self.prepared();tid=goals.command(self.root,self.request(child,self.review(child)))['task_id'];original=self.core.registry.execute
        def execute(*args,**kwargs):
            result=original(*args,**kwargs)
            if args[3]=='plugin.quote.v1':self.mutate('text',GOAL+'，必须保修三年',True)
            return result
        with patch.object(self.core.registry,'execute',side_effect=execute):self.core.run_task(tid)
        self.assertEqual(self.core.tasks.get(tid)['status'],'WAITING');self.assertEqual(self.core.tasks.get(tid)['spent'],1)
        self.assertEqual(len(self.core.tasks.actions(tid)),1)

    def test_link_note_mutation_invalidates_frozen_review(self):
        _,_,child=self.prepared();tid,_=self.finish(child)
        self.core.db.connection.execute('UPDATE work_revisions SET note=? WHERE goal_id=?',('新增要求「必须保修三年」',child))
        self.assertEqual(refresh(self.core,tid)['state'],'INVALIDATED')

    def test_policy_version_invalidates_new_mode_only(self):
        root,old,child=self.prepared();tid,_=self.finish(child)
        with patch.object(policy,'VERSION','changed'):
            self.assertEqual(refresh(self.core,tid)['state'],'INVALIDATED');self.assertEqual(refresh(self.core,old)['state'],'VERIFIED')

    def test_old_change_mode_still_rejects_work_merge(self):
        _,_,child=self.prepared();self.code('acceptance_invalid',base.ChangeIntegration.review,self,child)

    def test_three_revisions_preserve_history_and_shared_spending(self):
        root,_=self.root_version();child=self.child(root);self.finish(child)
        second=self.child(child,goal=REVISED+'，必须保修三年',note='新增要求「必须保修三年」');self.finish(second)
        third=self.child(second,note='撤销要求「必须保修三年」');_,d=self.finish(third)
        self.assertEqual(d['completion']['state'],'VERIFIED');self.assertEqual(d['work']['spent_cost_units'],8)
        r=self.review(third);self.assertEqual(len(r['rework_versions']),3);self.assertEqual(len(r['changes']),3)

    def test_no_raw_note_copied_to_completion(self):
        _,_,child=self.prepared();tid,_=self.finish(child)
        for table in ('task_acceptance','task_completion'):
            self.assertNotIn(REPLACE,self.core.db.one('SELECT body FROM '+table+' WHERE task_id=?',(tid,))['body'])

    def test_missing_port_cannot_admit(self):
        _,_,child=self.prepared();r=self.review(child)
        tid=goals.command(self.root,{'action':'approve','id':child,'revision':r['revision']})['task_id']
        self.code('acceptance_invalid',Completion(self.core.db).configure,tid,0,r['acceptance'])

    def test_shared_budget_exhaustion_still_blocks_atomically(self):
        _,_,child=self.prepared();d=self.detail(child);b=d['work']['budget']
        goals.command(self.root,{'action':'set_work_budget','id':child,'revision':b['revision'],'request_id':'budget-limit-child','limit_units':3,'note':'Only one unit remains'})
        self.code('work_budget_exhausted',goals.command,self.root,self.request(child,self.review(child)))
        self.assertIsNone(self.detail(child)['task'])

    def test_cancel_work_stops_new_effects(self):
        _,_,child=self.prepared();tid=goals.command(self.root,self.request(child,self.review(child)))['task_id']
        d=self.detail(child);goals.command(self.root,{'action':'cancel_work','id':child,'work_revision':d['work']['revision']})
        self.code('invalid_state',self.core.run_task,tid)
        self.assertEqual(self.core.tasks.get(tid)['status'],'CANCELLED');self.assertEqual(self.core.tasks.actions(tid),[])

    def test_changed_parent_delivery_stops_inheritance(self):
        root,old,child=self.prepared();delivery=decode(self.core.tasks.actions(old)[-1]['result'])
        (self.root/delivery['relative_path']).write_text('changed',encoding='utf-8')
        self.code('rework_source_changed',self.review,child)

    def test_changed_parent_feedback_requires_new_binding(self):
        root,old,child=self.prepared();r=self.review(child);d=self.detail(root)
        command(self.core,{'action':'completion_feedback','id':old,'request_id':'late-parent-correction','fingerprint':d['completion']['fingerprint'],'kind':'reject','note':'late evidence'})
        self.code('rework_source_changed',self.review,child)
        p=self.core.db.one('SELECT revision FROM goal_plans WHERE id=?',(child,));w=self.core.works.owner(child)
        goals.command(self.root,{'action':'review_rework_source','id':child,'revision':p['revision'],'work_revision':w['revision'],'note':'Review late feedback for full rerun'})
        self.assertNotEqual(self.review(child)['binding'],r['binding'])

    def test_partial_prefix_mode_is_explicitly_unsupported(self):
        _,_,child=self.prepared()
        self.core.db.connection.execute('UPDATE work_revisions SET start_step=2 WHERE goal_id=?',(child,))
        self.code('acceptance_invalid',self.review,child)

    def test_prior_context_uncertainty_survives_rework(self):
        root,_=self.root_version(prior=True);child=self.child(root);_,d=self.finish(child)
        self.assertEqual(d['completion']['state'],'WAITING_EVIDENCE')
        self.assertIn('prior_context_unreviewed',[i['code'] for i in self.review(child)['issues']])

    def test_detail_cannot_mix_prepared_action_with_later_success(self):
        root,tid=self.root_version();delivery=self.core.tasks.actions(tid)[-1]
        with self.core.db.transaction() as tx:
            tx.execute("UPDATE tasks SET status='RUNNING' WHERE id=?",(tid,))
            tx.execute("UPDATE actions SET status='PREPARED',result=NULL,attempts=0 WHERE id=?",(delivery['id'],))
        writer=sqlite3.connect(self.root/'state/core.sqlite3',timeout=0,isolation_level=None)
        def finish_elsewhere():
            try:
                writer.execute('BEGIN IMMEDIATE')
                writer.execute("UPDATE actions SET status='CONFIRMED',result=?,attempts=? WHERE id=?",(delivery['result'],delivery['attempts'],delivery['id']))
                writer.execute("UPDATE tasks SET status='SUCCEEDED' WHERE id=?",(tid,));writer.execute('COMMIT')
            except BaseException:
                if writer.in_transaction:writer.rollback()
                raise
        actions=self.core.tasks.actions;attempted=[]
        def racing_read(task_id):
            rows=actions(task_id)
            if not attempted:
                attempted.append(True)
                try:finish_elsewhere()
                except sqlite3.OperationalError as exc:
                    if 'locked' not in str(exc):raise
            return rows
        try:
            with patch.object(self.core.tasks,'actions',side_effect=racing_read):d=goals.detail(self.core,root)
            self.assertTrue(attempted)
            self.assertFalse(d['task']['status']=='SUCCEEDED' and any(a['status']!='CONFIRMED' for a in d['actions']))
            finish_elsewhere();d=goals.detail(self.core,root)
            self.assertEqual(d['task']['status'],'SUCCEEDED');self.assertTrue(all(a['status']=='CONFIRMED' for a in d['actions']))
            self.assertEqual(d['completion']['state'],'VERIFIED');self.assertNotEqual(d['outcome']['state'],'UNAVAILABLE')
        finally:writer.close()
