"""Goal-level applicability challenges: explicit scoped cards, not semantic guesses."""
import copy,time,unittest
import test_goal_advice as fixture
from host import goal_context
from sdk.protocol import canonical

class Applicability(unittest.TestCase):
    setUp=fixture.GoalAdvice.setUp
    tearDown=fixture.GoalAdvice.tearDown
    publish=fixture.GoalAdvice.publish
    req=fixture.GoalAdvice.req
    detail=fixture.GoalAdvice.detail
    plan=fixture.GoalAdvice.plan
    code=fixture.GoalAdvice.code
    source=fixture.GoalAdvice.source
    seed=fixture.GoalAdvice.seed
    create=fixture.GoalAdvice.create
    edit_source=fixture.GoalAdvice.edit_source

    goal='比较报价，预算不超过236元，交期不超过7天，在合格报价中选择最低价，保留来源引用，保存报告'
    data={'schema':'jarvis.quote-input.v1','currency':'CNY','max_price_minor':23600,'max_delivery_days':7,
          'offers':[{'id':'current-A','price_minor':21000,'delivery_days':7,'source':'synthetic:current-A'}]}

    def scoped(self,**changes):
        return self.seed(requires={'channel':'task','planner':'goal-plan-v1','input_schema':'jarvis.quote-input.v1',
            'currency':'CNY','max_price_minor':23600,'max_delivery_days':7,'quote_requirements_ready':True},**changes)

    def request(self,ident='scoped-01',goal=None,data=None):
        return self.create(request_id=ident,goal=self.goal if goal is None else goal,input_text=canonical(self.data if data is None else data))

    def test_exact_scoped_goal_matches_but_generic_case_does_not(self):
        self.scoped();ident=self.request();self.assertTrue(self.detail(ident)['planning_advice']['current'])
        self.assertIsNone(self.detail(self.create(request_id='generic-other-domain'))['planning_advice'])

    def test_goal_reversal_and_uncovered_conditions_do_not_satisfy_ready(self):
        self.scoped()
        for i,goal in enumerate([self.goal.replace('最低价','最高价'),self.goal+'，只考虑绿色产品',
            self.goal+'，不要使用交期限制',self.goal.replace('236元','235元'),self.goal.replace('7天','6天'),
            'Choose the cheapest qualified offer within 236 CNY and seven days.']):
            with self.subTest(goal=goal):self.assertIsNone(self.detail(self.request('reversal-'+str(i),goal))['planning_advice'])

    def test_current_input_changes_require_new_matching_scope(self):
        self.scoped()
        for i,(key,value) in enumerate([('currency','USD'),('max_price_minor',23500),('max_delivery_days',6),('max_delivery_days',True),('schema','jarvis.notes-input.v1')]):
            data={**self.data,key:value}
            with self.subTest(key=key,value=value):self.assertIsNone(self.detail(self.request('input-change-'+str(i),data=data))['planning_advice'])

    def test_expiry_is_rechecked_after_binding_before_model_request(self):
        self.scoped(expires=time.time()+30);ident=self.request()
        from unittest.mock import patch
        with patch('modules.context_knowledge.methods.time.time',return_value=time.time()+60):
            result,provider=self.plan(ident)
        self.assertEqual(result['error'],'goal_context_changed');self.assertEqual(provider.prompts,[])

    def test_evidence_revocation_invalidates_bound_scoped_method(self):
        evidence,_,_=self.scoped();ident=self.request();self.edit_source(evidence['id'],paused=True)
        self.code('goal_context_changed',goal_context.check,self.core,ident)

    def test_stricter_method_edit_requires_refresh_instead_of_reusing_prior_receipt(self):
        _,method,card=self.scoped();ident=self.request();card=copy.deepcopy(card);card['requires']['max_price_minor']=23500
        self.edit_source(method['id'],text=canonical(card));self.code('goal_context_changed',goal_context.check,self.core,ident)
        self.assertIsNone(self.detail(self.request('after-scope-edit'))['planning_advice'])

    def test_plain_counterexample_text_does_not_become_machine_condition(self):
        # Retain this limitation: existing generic cards cannot be silently
        # reinterpreted or certified by words in their summary/counterexamples.
        self.seed(counterexamples=['Only appropriate for quote input; never use on prose.'])
        ident=self.create();self.assertIsNotNone(self.detail(ident)['planning_advice'])

    def test_general_method_can_transfer_to_new_budget_without_pinning_old_answer(self):
        self.seed(requires={'channel':'task','planner':'goal-plan-v1','input_schema':'jarvis.quote-input.v1',
            'currency':'CNY','quote_requirements_ready':True})
        for i,(budget,days) in enumerate([(236,7),(281,9)]):
            data={**self.data,'max_price_minor':budget*100,'max_delivery_days':days}
            goal=self.goal.replace('236元',str(budget)+'元').replace('7天',str(days)+'天')
            ident=self.request('transfer-'+str(i),goal,data)
            advice=self.detail(ident)['planning_advice'];self.assertTrue(advice['current'])
            methods=goal_context.advice(self.core,ident)
            self.assertNotIn('max_price_minor',methods[0]['requires'])
            self.assertEqual(goal_context.check(self.core,ident),goal_context.get(self.core,ident)['view']['facts'])

if __name__=='__main__':unittest.main()
