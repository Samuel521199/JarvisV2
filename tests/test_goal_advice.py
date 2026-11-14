"""Real goal/planning/task ledgers; model stub only for deterministic fault tests."""
import copy,time,unittest
from unittest.mock import patch
import test_goal_plans as base
from host import goals,goal_context
from host.completion import refresh,command as feedback
from host.planning_advice import PlanningAdvice,KEY
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.methods import text_digest
from modules.task_resource.plans import Plans
from sdk.protocol import CoreError,canonical,decode


class GoalAdvice(unittest.TestCase):
    setUp=base.GoalPlans.setUp
    tearDown=base.GoalPlans.tearDown
    publish=base.GoalPlans.publish
    req=base.GoalPlans.req
    detail=base.GoalPlans.detail
    approve=base.GoalPlans.approve
    plan=base.GoalPlans.plan
    code=base.GoalPlans.code

    def source(self,text,title='Jarvis 中文 文本转为大写 方法',providers=None,scope='personal'):
        return Knowledge(self.core.db).save({'id':'','scope':scope,'title':title,'text':text,
            'providers':providers if providers is not None else ['openai','bailian','anthropic','gemini','vertex'],'paused':False},0)

    def edit_source(self,ident,**changes):
        lib=Knowledge(self.core.db);row=lib.detail('personal',ident)
        item={k:row[k] for k in ('id','scope','title','text','providers')};item['paused']=row['status']=='paused';item.update(changes)
        return lib.save(item,row['revision'])

    def seed(self,**changes):
        original='Observed a text transformation; current input must still be checked.'
        evidence=self.source(original,'Original observation')
        card={'schema':'jarvis.method-card.v1','id':'uppercase-advice','revision':1,'status':'CANDIDATE',
            'recipe':'current-text-plan','requires':{'channel':'task','planner':'goal-plan-v1'},
            'summary':'ADVICE_CANARY: use only the current text and an available uppercase capability. Never reuse a past answer.',
            'counterexamples':['A request to preserve case must not be forced into uppercase.'],
            'evidence':[{'source_id':evidence['id'],'revision':1,'sha256':text_digest(original)}],
            'expires':time.time()+3600}
        card.update(changes);method=self.source(canonical(card))
        return evidence,method,card

    def create(self,enabled=True,scope='personal',**changes):
        request=self.req(**changes)
        return goals.command(self.root,{'action':'create','request':request,
            'context':{'scope':scope,'enabled':enabled,'chat_id':'','turn_id':''}})['id']

    def rules(self,expected='JARVIS 中文'):
        return {'coverage':'complete','criteria':[{'id':'uppercase','step_id':'step-1','check':'text_equals','expected':expected}],
            'requirements':[{'id':'exact-current-output','text':'Explicit test expects current uppercase output','kind':'literal','criterion_ids':['uppercase']}]}

    def complete(self,ident,expected='JARVIS 中文'):
        self.plan(ident)
        tid=goals.command(self.root,{'action':'approve','id':ident,'revision':self.detail(ident)['plan']['revision'],
            'acceptance':self.rules(expected)})['task_id']
        self.core.run_task(tid);return tid

    def test_advice_is_automatically_assembled_but_not_promoted_or_authorized(self):
        evidence,method,_=self.seed();ident=self.create();self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        before=self.detail(ident)['planning_advice'];self.assertTrue(before['current']);self.assertFalse(before['model_dispatched'])
        planned,provider=self.plan(ident);self.assertEqual(planned['status'],'REVIEW')
        data=decode(provider.prompts[0].rsplit('\n',1)[1]);offered=data['conditional_advice']['methods']
        self.assertEqual(len(offered),1);self.assertEqual(offered[0]['source_id'],method['id'])
        self.assertNotIn('ADVICE_CANARY',canonical(data['applicable_background']))
        after=self.detail(ident)['planning_advice'];self.assertTrue(after['model_dispatched']);self.assertTrue(after['current'])
        self.assertEqual(len(after['model_calls']),1);self.assertFalse(after['automatic_promotion'])
        self.assertIsNone(after['causal_contribution']);self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])

    def test_disabled_and_missing_context_do_not_forward_advice(self):
        self.seed();ident=self.create(enabled=False);_,provider=self.plan(ident)
        data=decode(provider.prompts[0].rsplit('\n',1)[1]);self.assertNotIn('conditional_advice',data)
        other=goals.command(self.root,{'action':'create','request':self.req(request_id='plain-goal-002')})['id']
        self.assertIsNone(self.detail(other)['planning_advice'])

    def test_unknown_and_changed_conditions_do_not_match(self):
        self.seed(requires={'price_includes_fees':True});ident=self.create()
        self.assertIsNone(self.detail(ident)['planning_advice'])

    def test_fallback_requires_every_destination_to_allow_evidence(self):
        evidence,method,_=self.seed();self.edit_source(evidence['id'],providers=['openai'])
        ident=self.create();self.assertIsNone(self.detail(ident)['planning_advice'])

    def test_withdrawal_before_planning_sends_no_model_request(self):
        evidence,_,_=self.seed();ident=self.create();self.edit_source(evidence['id'],paused=True)
        result,provider=self.plan(ident);self.assertEqual(result['error'],'goal_context_changed')
        self.assertEqual(provider.prompts,[]);self.assertEqual(self.core.db.all('SELECT * FROM model_calls'),[])

    def test_withdrawal_after_planning_blocks_admission_before_grant(self):
        _,method,_=self.seed();ident=self.create();self.plan(ident);before=self.core.db.all('SELECT * FROM grants')
        self.edit_source(method['id'],paused=True)
        self.code('goal_context_changed',self.approve,ident)
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[]);self.assertEqual(self.core.db.all('SELECT * FROM grants'),before)

    def test_effect_boundary_rechecks_source_after_task_approval(self):
        evidence,_,_=self.seed();ident=self.create();self.plan(ident);tid=self.approve(ident)
        self.edit_source(evidence['id'],paused=True);result=self.core.run_task(tid)
        self.assertEqual(result['status'],'WAITING');self.assertFalse(self.core.db.all("SELECT * FROM actions WHERE status='CONFIRMED'"))

    def test_result_score_is_recorded_and_late_rejection_holds_future_same_revision(self):
        self.seed();ident=self.create();tid=self.complete(ident);result=refresh(self.core,tid)
        self.assertEqual(result['state'],'VERIFIED');observation=self.detail(ident)['planning_advice']['observation']
        self.assertEqual(observation['condition_score'],100);self.assertIsNone(observation['causal_contribution'])
        feedback(self.core,{'action':'completion_feedback','id':tid,'request_id':'reject-current-method','fingerprint':result['fingerprint'],
            'kind':'reject','note':'Unresolved issue; cause of advice is not established'})
        self.assertTrue(self.detail(ident)['planning_advice']['observation']['review_required'])
        newer=self.create(request_id='future-method-002');self.assertIsNone(self.detail(newer)['planning_advice'])
        current=refresh(self.core,tid)
        feedback(self.core,{'action':'completion_feedback','id':tid,'request_id':'withdraw-current-hold','fingerprint':current['fingerprint'],
            'kind':'withdraw','note':'Explicitly withdraw this feedback after review'})
        reviewed=self.create(request_id='reviewed-method-003');self.assertIsNotNone(self.detail(reviewed)['planning_advice'])

    def test_failure_after_other_goal_was_planned_blocks_its_pending_effects(self):
        self.seed();first=self.create();second=self.create(request_id='parallel-method-002')
        self.plan(second);tid=self.approve(second);self.complete(first,expected='INCORRECT EXPECTATION')
        self.assertEqual(self.core.run_task(tid)['status'],'WAITING')

    def test_explicit_amend_rebinds_and_keeps_historical_receipt(self):
        self.seed();ident=self.create();self.plan(ident);old=goal_context.get(self.core,ident)
        goal_context.amend(self.core,ident,Plans(self.core.db).get(ident)['revision'],'将当前文本转为大写并保存','Jarvis 中文')
        new=goal_context.get(self.core,ident);self.assertNotEqual(old['view'][KEY]['binding'],new['view'][KEY]['binding'])
        self.assertEqual(new['history'][-1][KEY]['receipt'],old['view'][KEY]['receipt'])
        self.assertTrue(self.detail(ident)['planning_advice']['current']);self.assertFalse(self.detail(ident)['planning_advice']['model_dispatched'])

    def test_cleanup_discovers_forgotten_evidence_used_only_as_advice(self):
        from host import knowledge_cleanup
        from modules.dialogue.store import Dialogues
        evidence,_,_=self.seed();ident=self.create();self.plan(ident)
        Knowledge(self.core.db).delete('personal',evidence['id'],1)
        store=Dialogues(self.root)
        try:preview=knowledge_cleanup.inspect(self.core.db,store,'personal',{'goals':'','turns':''})
        finally:store.close()
        self.assertIn(ident,[r['goal_id'] for r in preview['goals']])

    def test_atomic_prompt_assembly_does_not_resurrect_redacted_context(self):
        self.seed();ident=self.create();plan=Plans(self.core.db).get(ident);stale=goal_context.get(self.core,ident)
        current=copy.deepcopy(stale['view']);current['redacted']=True
        with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(current),ident))
        self.code('goal_context_changed',PlanningAdvice(self.core.db).assembly,plan,stale,ident,'old prompt')
        self.assertTrue(goal_context.get(self.core,ident)['view']['redacted'])

    def test_inherited_plan_keeps_original_advice_dependency_without_injecting_it(self):
        evidence,_,_=self.seed();ident=self.create();parent=Plans(self.core.db).get(ident);context=goal_context.get(self.core,ident)
        with self.core.db.transaction() as tx:
            child,_=Plans(self.core.db).create(self.req(request_id='inherited-child-002',goal='不同的后续目标'),parent['catalog'],parent['routes'],tx)
            inherited=goal_context.inherit_advice(self.core,Plans(self.core.db).get(child),parent,context)
            tx.execute('INSERT INTO goal_context(goal_id,scope,enabled,view) VALUES(?,?,?,?)',(child,'personal',1,canonical(inherited)))
        self.assertEqual(goal_context.advice(self.core,child),[]);goal_context.check(self.core,child)
        self.edit_source(evidence['id'],paused=True);self.code('goal_context_changed',goal_context.check,self.core,child)


    def test_dependency_invalidation_is_not_a_new_negative_vote_and_review_recovers(self):
        self.seed();a=self.create();b=self.create(request_id='another-completed-002')
        ta=self.complete(a);tb=self.complete(b)
        result=refresh(self.core,ta)
        feedback(self.core,{'action':'completion_feedback','id':ta,'request_id':'reject-root-counterexample','fingerprint':result['fingerprint'],
            'kind':'reject','note':'Temporary unresolved direct feedback'})
        self.assertEqual(refresh(self.core,tb)['state'],'INVALIDATED')
        current=refresh(self.core,ta)
        feedback(self.core,{'action':'completion_feedback','id':ta,'request_id':'withdraw-root-counterexample','fingerprint':current['fingerprint'],
            'kind':'withdraw','note':'Independent review withdraws root feedback'})
        self.assertEqual(refresh(self.core,ta)['state'],'VERIFIED')
        self.assertEqual(refresh(self.core,tb)['state'],'VERIFIED')
        self.assertTrue(self.detail(self.create(request_id='after-review-003'))['planning_advice']['current'])


    def test_no_advice_preserves_existing_model_prompt_prefix_exactly(self):
        import hashlib
        ident=self.create(enabled=False);_,provider=self.plan(ident)
        prefix=provider.prompts[0].rsplit('\n',1)[0]+'\n'
        self.assertEqual(hashlib.sha256(prefix.encode()).hexdigest(),'6f2e1e24639d97f6a2e3a8c8a126f22bfa238968c978fe83e94d14ed762ebb1b')

    def test_missing_evidence_dependency_inventory_cannot_be_admitted(self):
        self.seed();ident=self.create();context=goal_context.get(self.core,ident)
        context['view'][KEY]['dependencies']=[]
        with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(context['view']),ident))
        self.code('goal_context_changed',goal_context.check,self.core,ident)

    def test_unknown_mode_cannot_be_treated_as_supported_advice(self):
        self.seed();ident=self.create();context=goal_context.get(self.core,ident)
        context['view'][KEY]['mode']='future-automatic'
        with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(context['view']),ident))
        self.code('goal_context_changed',goal_context.check,self.core,ident)


    def test_copy_renaming_renewal_and_new_observation_ids_do_not_escape_hold(self):
        _,_,card=self.seed();ident=self.create();self.complete(ident,expected='NOT THE REQUESTED OUTPUT')
        original='Observed a text transformation; current input must still be checked.'
        copy_evidence=self.source(original,'Copied observation under a new identity')
        copied=copy.deepcopy(card);copied.update(id='renamed-copy',recipe='renamed-label',revision=9,expires=card['expires']+3600,
            evidence=[{'source_id':copy_evidence['id'],'revision':1,'sha256':text_digest(original)}])
        self.source(canonical(copied),'Jarvis 中文 文本转为大写 新副本')
        newer=self.create(request_id='renamed-method-copy-002')
        self.assertIsNone(self.detail(newer)['planning_advice'])


    def test_chat_and_goal_detail_share_the_same_advice_receipt_projection(self):
        from test_assistant_goals import AssistantGoals
        from host import assistant
        from modules.dialogue.store import Dialogues
        self.seed();chat=AssistantGoals.chat(self,ident='chat-advice-projection-001')
        ident=assistant.goal_from_turn(self.root,'chat-advice-projection-001')['id']
        self.plan(ident);tid=self.approve(ident);self.core.run_task(tid)
        store=Dialogues(self.root)
        try:linked=assistant.projection(self.root,store.read(chat))['turns'][0]['linked_goal']['planning_advice']
        finally:store.close()
        detail=self.detail(ident)['planning_advice']
        self.assertEqual(linked,detail);self.assertTrue(linked['model_dispatched']);self.assertEqual(linked['observation']['task_id'],tid)
