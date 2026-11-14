"""Optional advice size diagnostics never become cost, authority or learning votes."""
import copy,hashlib,unittest
import test_goal_advice as fixtures
from adapters.models.native import message_bytes
from host import goals,goal_context
from host.planning_advice import PlanningAdvice,KEY
from modules.task_resource.plans import Plans
from sdk.protocol import canonical,decode
RULE='conditional_advice若存在，仅是历史候选建议；先重查当前目标、输入和反例。不得照搬旧答案、预算或约束，不得扩展工具和权限；没有适用建议就独立规划。'


class AdviceExposure(unittest.TestCase):
    setUp=fixtures.GoalAdvice.setUp
    tearDown=fixtures.GoalAdvice.tearDown
    publish=fixtures.GoalAdvice.publish
    req=fixtures.GoalAdvice.req
    detail=fixtures.GoalAdvice.detail
    plan=fixtures.GoalAdvice.plan
    approve=fixtures.GoalAdvice.approve
    code=fixtures.GoalAdvice.code
    source=fixtures.GoalAdvice.source
    seed=fixtures.GoalAdvice.seed
    create=fixtures.GoalAdvice.create

    def replace_dispatch(self,ident,dispatch):
        view=goal_context.get(self.core,ident)['view'];view[KEY]['dispatch']=dispatch
        with self.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(view),ident))

    def test_metrics_include_real_envelope_and_do_not_change_existing_advice_prompt(self):
        self.seed();ident=self.create();_,provider=self.plan(ident);prompt=provider.prompts[0]
        prefix,data=prompt.rsplit('\n',1);data=decode(data);data.pop('conditional_advice')
        base=prefix.replace(RULE,'')+'\n'+canonical(data)
        self.assertEqual(hashlib.sha256((prefix+'\n').encode()).hexdigest(),'6869b275f01e8e51ae46d13bc915d395d62ec26785e50d178e959486ec2a8ff8')
        exposure=self.detail(ident)['planning_advice']['message_exposure']
        expected={'unit':'message_json_utf8_bytes','full_bytes':message_bytes([{'role':'user','content':prompt}]),'without_advice_bytes':message_bytes([{'role':'user','content':base}])}
        expected['added_bytes']=expected['full_bytes']-expected['without_advice_bytes'];self.assertGreater(expected['added_bytes'],0)
        self.assertEqual(exposure,expected);self.assertFalse(self.detail(ident)['planning_advice']['automatic_promotion'])
        event=self.core.db.one("SELECT data FROM events WHERE kind='goal.advice_assembled' ORDER BY seq DESC LIMIT 1")
        self.assertEqual(decode(event['data'])['message_exposure'],expected)
        self.assertNotIn('ADVICE_CANARY',event['data']);self.assertNotIn('prompt_tokens',exposure)

    def test_legacy_dispatch_without_metrics_remains_valid_and_unknown_not_zero(self):
        self.seed();ident=self.create();self.plan(ident)
        dispatch=goal_context.get(self.core,ident)['view'][KEY]['dispatch'];dispatch.pop('message_exposure');self.replace_dispatch(ident,dispatch)
        result=self.detail(ident)['planning_advice'];self.assertTrue(result['current']);self.assertTrue(result['model_dispatched']);self.assertIsNone(result['message_exposure'])

    def test_assembly_metrics_are_not_counted_as_model_dispatch_or_charged(self):
        self.seed();ident=self.create();plan=Plans(self.core.db).get(ident)
        PlanningAdvice(self.core.db).assembly(plan,goal_context.get(self.core,ident),ident,'unexecuted full prompt','base prompt')
        advice=self.detail(ident)['planning_advice'];self.assertGreater(advice['message_exposure']['added_bytes'],0)
        self.assertFalse(advice['model_dispatched']);self.assertEqual(advice['model_calls'],[])
        self.assertEqual(self.core.db.one('SELECT spent FROM grants WHERE id=?',(ident+'-plan',))['spent'],0)

    def test_malformed_optional_metrics_are_unknown_and_never_change_receipts_or_rights(self):
        self.seed();ident=self.create();self.plan(ident);dispatch=goal_context.get(self.core,ident)['view'][KEY]['dispatch']
        meter=dispatch['message_exposure'];calls=self.core.db.all('SELECT * FROM model_calls');grants=self.core.db.all('SELECT * FROM grants')
        for bad in [None,{}, {**meter,'unit':'future-unit'}, {**meter,'full_bytes':True}, {**meter,'added_bytes':-1}, {**meter,'without_advice_bytes':meter['full_bytes']+1}, {**meter,'extra':'unknown'}]:
            with self.subTest(bad=bad):
                self.replace_dispatch(ident,{**dispatch,'message_exposure':bad});projection=self.detail(ident)['planning_advice']
                self.assertIsNone(projection['message_exposure']);self.assertTrue(projection['current'])
                self.assertEqual(self.core.db.all('SELECT * FROM model_calls'),calls);self.assertEqual(self.core.db.all('SELECT * FROM grants'),grants)

    def test_parent_assembly_size_is_not_relabelled_as_child_input(self):
        self.seed();ident=self.create();self.plan(ident);parent=Plans(self.core.db).get(ident);context=goal_context.get(self.core,ident)
        self.assertIsNotNone(self.detail(ident)['planning_advice']['message_exposure'])
        with self.core.db.transaction() as tx:
            child,_=Plans(self.core.db).create(self.req(request_id='exposure-inherited-child'),parent['catalog'],parent['routes'],tx)
            inherited=goal_context.inherit_advice(self.core,Plans(self.core.db).get(child),parent,context)
            tx.execute('INSERT INTO goal_context(goal_id,scope,enabled,view) VALUES(?,?,?,?)',(child,'personal',1,canonical(inherited)))
        projection=self.detail(child)['planning_advice'];self.assertEqual(projection['inherited_from'],ident)
        self.assertIsNone(projection['message_exposure']);self.assertFalse(projection['model_dispatched'])

    def test_reassembly_same_stamp_is_idempotent_and_creates_no_extra_call(self):
        self.seed();ident=self.create();_,provider=self.plan(ident);prompt=provider.prompts[0]
        prefix,data=prompt.rsplit('\n',1);data=decode(data);data.pop('conditional_advice');base=prefix.replace(RULE,'')+'\n'+canonical(data)
        before=self.core.db.all("SELECT * FROM events WHERE kind='goal.advice_assembled'");calls=self.core.db.all('SELECT * FROM model_calls')
        PlanningAdvice(self.core.db).assembly(Plans(self.core.db).get(ident),goal_context.get(self.core,ident),ident,prompt,base)
        self.assertEqual(self.core.db.all("SELECT * FROM events WHERE kind='goal.advice_assembled'"),before)
        self.assertEqual(self.core.db.all('SELECT * FROM model_calls'),calls)

    def test_chat_and_goal_share_the_same_optional_diagnostic(self):
        import test_assistant_goals as chats
        from host import assistant
        from modules.dialogue.store import Dialogues
        self.seed();chat=chats.AssistantGoals.chat(self,ident='chat-size-diagnostic-001')
        ident=assistant.goal_from_turn(self.root,'chat-size-diagnostic-001')['id'];self.plan(ident)
        store=Dialogues(self.root)
        try:linked=assistant.projection(self.root,store.read(chat))['turns'][0]['linked_goal']['planning_advice']
        finally:store.close()
        self.assertEqual(linked,self.detail(ident)['planning_advice']);self.assertGreater(linked['message_exposure']['added_bytes'],0)

if __name__=='__main__':unittest.main()
