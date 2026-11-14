"""Real task/receipt ledgers and NativeModel's actual envelope guard; no network."""
import copy,unittest
from unittest.mock import patch
import test_goal_advice as fixtures
import test_goal_plans as plans_fixture
from test_development import Provider
from adapters.models.native import NativeModel
from host import goals,goal_context
from host.planning_advice import PlanningAdvice,KEY
from modules.task_resource.plans import Plans
from modules.context_knowledge.memory import Memory
from modules.preferences.store import fallback_routes
from sdk.protocol import canonical,decode


def envelope(prompt):return len(canonical([{'role':'user','content':prompt}]).encode('utf-8'))


class GuardPassed(Exception):pass


class GuardedProvider(Provider):
    def __init__(self,route,responses):
        super().__init__(responses);self.config=route
    def generate(self,prompt,checkpoint):
        # The real adapter enforces its envelope budget before requesting a
        # credential. Stop there; no credential, subprocess or cloud request.
        def credential(*args):raise GuardPassed()
        try:NativeModel(self.config,credential).generate(prompt,checkpoint)
        except GuardPassed:pass
        return super().generate(prompt,checkpoint)


class GoalAdviceBudget(unittest.TestCase):
    setUp=fixtures.GoalAdvice.setUp
    tearDown=fixtures.GoalAdvice.tearDown
    publish=fixtures.GoalAdvice.publish
    req=fixtures.GoalAdvice.req
    detail=fixtures.GoalAdvice.detail
    approve=fixtures.GoalAdvice.approve
    code=fixtures.GoalAdvice.code
    source=fixtures.GoalAdvice.source
    seed=fixtures.GoalAdvice.seed
    edit_source=fixtures.GoalAdvice.edit_source
    create=fixtures.GoalAdvice.create

    def limit(self,limit):
        catalog=self.core.preferences.read()['catalog'];catalog['max_prompt_bytes']=limit
        self.core.preferences.db.execute('UPDATE models SET catalog=?,revision=revision+1 WHERE id=1',(canonical(catalog),))

    def plan(self,ident,responses=None,retry=False):
        row=Plans(self.core.db).get(ident)
        provider=GuardedProvider(row['routes'][0],responses if responses is not None else [plans_fixture.proposal(row['request']['input_text'])])
        with patch('host.goals.NativeModel',return_value=provider):result=goals.execute(self.root,ident,retry)
        return result,provider

    def baseline(self,text='Jarvis 中文'):
        ident=self.create(enabled=False,request_id='baseline-before-advice',input_text=text)
        result,provider=self.plan(ident);self.assertEqual(result['status'],'REVIEW')
        return provider.prompts[0]

    def calls(self,ident):return self.core.db.all('SELECT * FROM model_calls WHERE run_id=?',(ident,))
    def omitted(self,ident):
        return [decode(r['data']) for r in self.core.db.all("SELECT data FROM events WHERE kind='goal.advice_omitted'") if decode(r['data'])['goal_id']==ident]

    def test_exact_base_budget_omits_unused_advice_and_current_task_still_executes(self):
        base=self.baseline();self.limit(envelope(base));evidence,method,_=self.seed();ident=self.create()
        original=copy.deepcopy(goal_context.get(self.core,ident)['view']);self.assertIn(KEY,original)
        result,provider=self.plan(ident);self.assertEqual(result['status'],'REVIEW');self.assertEqual(provider.prompts,[base])
        original.pop(KEY);self.assertEqual(goal_context.get(self.core,ident)['view'],original)
        event=self.omitted(ident);self.assertEqual(len(event),1);self.assertEqual(event[0]['base_message_bytes'],envelope(base))
        self.assertEqual(event[0]['max_prompt_bytes'],envelope(base));self.assertGreater(event[0]['full_message_bytes'],envelope(base))
        self.assertEqual(event[0]['input_digest'],self.calls(ident)[0]['input_digest']);self.assertEqual(len(self.calls(ident)),1)
        self.assertEqual(self.core.db.one('SELECT spent FROM grants WHERE id=?',(ident+'-plan',))['spent'],1)
        self.edit_source(evidence['id'],paused=True)
        tid=self.approve(ident);self.assertEqual(self.core.run_task(tid)['status'],'SUCCEEDED')
        action=self.core.db.one("SELECT result FROM actions WHERE task_id=? AND capability='plugin.upper.v1'",(tid,))
        self.assertEqual(decode(action['result'])['text'],'JARVIS 中文')
        self.assertIsNone(self.detail(ident)['planning_advice'])

    def test_full_prompt_exact_boundary_retains_advice_and_one_byte_less_omits(self):
        self.seed();first=self.create();_,p=self.plan(first);full=p.prompts[0]
        for limit,expected_advice in [(envelope(full),True),(envelope(full)-1,False)]:
            with self.subTest(limit=limit):
                self.limit(limit);ident=self.create(request_id='boundary-'+str(limit));result,p=self.plan(ident)
                self.assertEqual(result['status'],'REVIEW')
                self.assertEqual('conditional_advice' in decode(p.prompts[0].rsplit('\n',1)[1]),expected_advice)
                self.assertEqual(bool(self.omitted(ident)),not expected_advice)
                self.assertEqual(len(self.calls(ident)),1)

    def test_unicode_quotes_newlines_use_native_message_envelope_not_raw_prompt_length(self):
        text=('Jarvis 中文 🙂\n"quoted" \\ path'*300);base=self.baseline(text);self.assertGreater(envelope(base),len(base.encode('utf-8')))
        self.limit(envelope(base));self.seed();ident=self.create(input_text=text);result,p=self.plan(ident)
        self.assertEqual(result['status'],'REVIEW');self.assertEqual(p.prompts,[base]);self.assertEqual(result['proposal']['input_text'],text)
        self.assertEqual(len(self.calls(ident)),1)

    def test_original_oversize_stops_before_reserving_call_or_erasing_advice(self):
        base=self.baseline();self.limit(envelope(base)-1);self.seed();ident=self.create();before=goal_context.get(self.core,ident)
        result,p=self.plan(ident);self.assertEqual(result['error'],'model_input_limit');self.assertEqual(p.prompts,[])
        self.assertEqual(self.calls(ident),[]);self.assertEqual(goal_context.get(self.core,ident),before)
        self.assertEqual(self.omitted(ident),[]);self.assertEqual(self.core.db.one('SELECT spent FROM grants WHERE id=?',(ident+'-plan',))['spent'],0)

    def test_every_existing_receipt_status_preserves_dependencies_and_input_binding(self):
        self.seed();ident=self.create();self.plan(ident)
        with self.core.db.transaction() as tx:tx.execute("UPDATE goal_plans SET status='PLANNING' WHERE id=?",(ident,))
        plan=Plans(self.core.db).get(ident);context=goal_context.get(self.core,ident);long='x'*50001
        for status in ['DISPATCHING','UNKNOWN','ACKNOWLEDGED','REJECTED','INVALID','SUCCEEDED']:
            with self.subTest(status=status):
                with self.core.db.transaction() as tx:tx.execute('UPDATE model_calls SET status=? WHERE run_id=?',(status,ident))
                old=self.calls(ident)
                self.assertEqual(PlanningAdvice(self.core.db).fit(plan,context,long,'base'),long)
                self.assertEqual(self.calls(ident),old);self.assertEqual(goal_context.get(self.core,ident),context)
        self.assertEqual(self.omitted(ident),[])

    def test_inherited_dependencies_cannot_be_dropped_by_a_new_child_budget(self):
        evidence,_,_=self.seed();ident=self.create();parent=Plans(self.core.db).get(ident);context=goal_context.get(self.core,ident)
        with self.core.db.transaction() as tx:
            child,_=Plans(self.core.db).create(self.req(request_id='inherited-budget-child'),parent['catalog'],parent['routes'],tx)
            inherited=goal_context.inherit_advice(self.core,Plans(self.core.db).get(child),parent,context)
            tx.execute('INSERT INTO goal_context(goal_id,scope,enabled,view) VALUES(?,?,?,?)',(child,'personal',1,canonical(inherited)))
        plan=Plans(self.core.db).get(child);current=goal_context.get(self.core,child);long='x'*50001
        self.assertEqual(PlanningAdvice(self.core.db).fit(plan,current,long,'base'),long)
        self.assertEqual(goal_context.get(self.core,child),current)
        self.edit_source(evidence['id'],paused=True);self.code('goal_context_changed',goal_context.check,self.core,child)

    def test_stale_view_cannot_undo_concurrent_redaction_during_omission(self):
        self.seed();ident=self.create();plan=Plans(self.core.db).get(ident);stale=goal_context.get(self.core,ident)
        changed=copy.deepcopy(stale['view']);changed['redacted']=True
        with self.core.db.transaction() as tx:
            tx.execute("UPDATE goal_plans SET status='PLANNING' WHERE id=?",(ident,))
            tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(changed),ident))
        self.code('goal_context_changed',PlanningAdvice(self.core.db).fit,plan,stale,'x'*50001,'base')
        self.assertTrue(goal_context.get(self.core,ident)['view']['redacted']);self.assertEqual(self.omitted(ident),[])

    def test_smallest_frozen_fallback_budget_is_used_without_removing_fallback(self):
        base=self.baseline();self.seed()
        def smaller(catalog,primary,**options):return [{**r,'max_prompt_bytes':envelope(base)} for r in fallback_routes(catalog,primary,**options)]
        with patch('host.goals.fallback_routes',side_effect=smaller):ident=self.create()
        routes=Plans(self.core.db).get(ident)['routes'];self.assertEqual(len(routes),2)
        primary=GuardedProvider(routes[0],[{'status':'REJECTED','code':'test-known-rejection'}])
        backup=GuardedProvider(routes[1],[plans_fixture.proposal()])
        providers={r['id']:p for r,p in zip(routes,[primary,backup])}
        with patch('host.goals.NativeModel',side_effect=lambda route,*args:providers[route['id']]):result=goals.execute(self.root,ident)
        self.assertEqual(result['status'],'REVIEW');self.assertEqual(primary.prompts,[base]);self.assertEqual(backup.prompts,[base])
        self.assertEqual(len(self.calls(ident)),2);self.assertEqual(self.omitted(ident)[0]['max_prompt_bytes'],envelope(base))

    def test_smaller_backup_cannot_block_original_prompt_that_primary_accepts(self):
        base=self.baseline();self.seed()
        def smaller(catalog,primary,**options):return [{**r,'max_prompt_bytes':envelope(base)-1} for r in fallback_routes(catalog,primary,**options)]
        with patch('host.goals.fallback_routes',side_effect=smaller):ident=self.create()
        before=Plans(self.core.db).get(ident)['routes'];result,p=self.plan(ident)
        self.assertEqual(result['status'],'REVIEW');self.assertEqual(p.prompts,[base])
        self.assertEqual(Plans(self.core.db).get(ident)['routes'],before)
        self.assertEqual(len(self.calls(ident)),1);self.assertEqual(self.omitted(ident)[0]['base_message_bytes'],envelope(base))

    def test_assembly_without_call_can_be_omitted_and_is_not_counted_as_exposure(self):
        base=self.baseline();self.limit(envelope(base));self.seed();ident=self.create();plan=Plans(self.core.db).get(ident)
        PlanningAdvice(self.core.db).assembly(plan,goal_context.get(self.core,ident),ident,'assembled but never sent')
        self.assertFalse(self.detail(ident)['planning_advice']['model_dispatched']);result,p=self.plan(ident)
        self.assertEqual(result['status'],'REVIEW');self.assertEqual(p.prompts,[base]);self.assertEqual(len(self.omitted(ident)),1)

    def test_omission_is_durable_unknown_does_not_retry_and_ack_keeps_original_context(self):
        base=self.baseline();self.limit(envelope(base));evidence,_,_=self.seed();ident=self.create()
        result,p=self.plan(ident,[{'status':'UNKNOWN','code':'synthetic-timeout'}]);self.assertEqual(result['error'],'model_unknown');self.assertEqual(p.prompts,[base])
        self.edit_source(evidence['id'],paused=True)
        result,p=self.plan(ident,[]);self.assertEqual(result['error'],'model_unknown');self.assertEqual(p.prompts,[])
        result,p=self.plan(ident,retry=True);self.assertEqual(result['status'],'REVIEW');self.assertEqual(p.prompts,[base])
        self.assertEqual([r['status'] for r in self.calls(ident)],['ACKNOWLEDGED','SUCCEEDED'])
        self.assertEqual(len({r['input_digest'] for r in self.calls(ident)}),1);self.assertEqual(len(self.omitted(ident)),1)
        self.assertEqual(self.core.db.one('SELECT spent FROM grants WHERE id=?',(ident+'-plan',))['spent'],2)

    def test_ordinary_fact_dependencies_are_preserved_when_optional_advice_is_omitted(self):
        Memory(self.core.db).save({'scope':'personal','key':'文本格式','value':'当前文本格式保持可核对','kind':'knowledge','purpose':'personal',
            'providers':['openai','bailian'],'paused':False,'expires':None},0)
        plain=self.create(request_id='facts-before-advice');_,provider=self.plan(plain);base=provider.prompts[0]
        self.limit(envelope(base));self.seed();ident=self.create();original=copy.deepcopy(goal_context.get(self.core,ident)['view']);original.pop(KEY)
        self.assertTrue(original['facts']);result,provider=self.plan(ident);self.assertEqual(result['status'],'REVIEW')
        self.assertEqual(provider.prompts,[base]);self.assertEqual(goal_context.get(self.core,ident)['view'],original)

if __name__=='__main__':unittest.main()
