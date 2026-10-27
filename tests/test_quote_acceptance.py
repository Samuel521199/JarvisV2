"""Finite quote oracle adversarial cases and real task/closure integration."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_goal_plans as base
from host import goals
from host.core import Core
from host.completion import refresh, command
from modules.task_resource import quote_checks as q, coverage
from modules.task_resource.completion import Completion
from sdk.protocol import CoreError, decode

FIXTURE = json.loads((Path(__file__).parent/'fixtures/quote_acceptance_v1.json').read_text('utf-8'))


def text(value): return json.dumps(value, ensure_ascii=False)


def body(value):
    return {'steps': [{'step_id': 'step-1', 'capability': 'plugin.quote.v1', 'arguments': {'text': text(value)}},
                     {'step_id': 'deliver', 'capability': 'artifact.write.v1', 'arguments': {'name': 'result.json'}, 'input_from': 'step-1'}]}


def rules(value):
    return {'coverage': 'complete', 'criteria': [{'id': 'quote', 'step_id': 'step-1', 'check': 'quote_selection', 'expected': q.source_digest(text(value))}],
            'requirements': [{'id': 'domain', 'text': q.REQUIREMENT, 'kind': 'quote_selection', 'criterion_ids': ['quote']}]}


class QuoteOracle(unittest.TestCase):
    def check(self, source=None, report=None, state='passed', reason='quote_verified'):
        source = FIXTURE['input'] if source is None else source
        report = FIXTURE['correct'] if report is None else report
        result = q.verify(body(source), rules(source)['criteria'][0], text(report))
        self.assertEqual((result['status'], result['reason']), (state, reason))
        self.assertEqual(result['verifier'], q.VERSION)

    def test_correct_report(self): self.check()

    def test_wrong_minimum_despite_success_shape(self):
        self.check(report=FIXTURE['wrong_cheapest'], state='failed', reason='quote_selection_mismatch')

    def test_budget_and_deadline_boundaries(self):
        v=copy.deepcopy(FIXTURE['input']);v['offers'][1]['price_minor']=10000
        self.check(v,FIXTURE['wrong_cheapest'])

    def test_budget_failure_cannot_be_admitted_as_eligible(self):
        self.check(report={**FIXTURE['correct'],'eligible_ids':['A','B','D']},state='failed',reason='quote_eligible_mismatch')

    def test_deadline_failure_cannot_be_admitted_as_eligible(self):
        self.check(report={**FIXTURE['correct'],'eligible_ids':['A','B','C']},state='failed',reason='quote_eligible_mismatch')

    def test_missing_candidate(self):
        self.check(report={**FIXTURE['correct'],'eligible_ids':['B']},state='failed',reason='quote_eligible_mismatch')

    def test_forged_source(self):
        self.check(report={**FIXTURE['correct'],'selected_source':'provided:A'},state='failed',reason='quote_source_mismatch')

    def test_tied_minima_accept_either(self):
        v=copy.deepcopy(FIXTURE['input']);v['offers'][0]['price_minor']=8000
        self.check(v);self.check(v,FIXTURE['wrong_cheapest'])

    def test_no_eligible_is_valid_and_requires_null_selection(self):
        v={**FIXTURE['input'],'max_price_minor':0}
        report={'schema':'jarvis.quote-result.v1','eligible_ids':[],'selected_id':None,'selected_source':None}
        self.check(v,report,reason='quote_no_eligible')
        self.check(v,{**report,'selected_id':'B'},state='failed',reason='quote_selection_mismatch')

    def test_zero_values_and_reordered_json_are_valid(self):
        v={**FIXTURE['input'],'max_price_minor':0,'max_delivery_days':0,'offers':[{'id':'free','price_minor':0,'delivery_days':0,'source':'receipt'}]}
        self.check(v,{'selected_source':'receipt','selected_id':'free','eligible_ids':['free'],'schema':'jarvis.quote-result.v1'})
        self.check(report={**FIXTURE['correct'],'eligible_ids':['B','A']})

    def test_invalid_numbers_rejected(self):
        for value in (True,False,-1,1.0,10**12+1,'8000',float('nan')):
            v=copy.deepcopy(FIXTURE['input']);v['offers'][0]['price_minor']=value
            with self.subTest(value=value),self.assertRaises(CoreError): q.parse_source(text(v))

    def test_unrecognized_constraints_rejected(self):
        for v in ({**FIXTURE['input'],'warranty_required':True}, {**FIXTURE['input'],'currency':'cny'}):
            with self.assertRaises(CoreError):q.parse_source(text(v))

    def test_duplicate_keys_and_offer_ids_rejected(self):
        with self.assertRaises(CoreError):q.parse_source(text(FIXTURE['input']).replace('"currency":','"currency":"USD","currency":'))
        v=copy.deepcopy(FIXTURE['input']);v['offers'][1]['id']='A'
        with self.assertRaises(CoreError):q.parse_source(text(v))

    def test_bounds_and_empty_fields(self):
        for field,value in [('max_delivery_days',3651),('offers',[]),('offers',FIXTURE['input']['offers']*26)]:
            with self.assertRaises(CoreError):q.parse_source(text({**FIXTURE['input'],field:value}))
        for field,value in [('id',' '),('id','A\n'),('source',''),('source','x'*301),('delivery_days',True)]:
            v=copy.deepcopy(FIXTURE['input']);v['offers'][0][field]=value
            with self.assertRaises(CoreError):q.parse_source(text(v))

    def test_malformed_report_not_unknown_or_passed(self):
        for report in ([1],None,{**FIXTURE['correct'],'eligible_ids':['A','A','B']},{**FIXTURE['correct'],'selected_id':{}},{**FIXTURE['correct'],'unverified':'claim'}):
            self.check(report=report if report is not None else 'not a report',state='failed',reason='quote_report_invalid')
        result=q.verify(body(FIXTURE['input']),rules(FIXTURE['input'])['criteria'][0],'not JSON')
        self.assertEqual(result['reason'],'quote_report_invalid')

    def test_source_digest_bound_to_exact_bytes(self):
        b=body(FIXTURE['input']);b['steps'][0]['arguments']['text']+=' '
        self.assertEqual(q.verify(b,rules(FIXTURE['input'])['criteria'][0],text(FIXTURE['correct']))['status'],'invalid')

    def test_intermediate_report_cannot_replace_original_offers(self):
        b=body(FIXTURE['input']);b['steps'].insert(1,{'step_id':'step-2','capability':'plugin.choose.v1','arguments':{},'input_from':'step-1'})
        b['steps'][-1]['input_from']='step-2';rule={**rules(FIXTURE['input'])['criteria'][0],'step_id':'step-2'}
        result=q.verify(b,rule,text({**FIXTURE['wrong_cheapest'],'eligible_ids':['A']}))
        self.assertEqual(result['reason'],'quote_eligible_mismatch')
        b['steps'][1]['arguments']={'text':text(FIXTURE['input'])}
        self.assertEqual(q.verify(b,rule,text(FIXTURE['correct']))['status'],'invalid')

    def test_external_or_unchecked_final_output_rejected(self):
        for change in ('external','delivery'):
            b=body(FIXTURE['input'])
            if change=='external':b['steps'][0]['capability']='mcp.quote.v1'
            else:b['steps'][-1]['input_from']='other'
            with self.assertRaises(CoreError):q.bound_source(b,rules(FIXTURE['input'])['criteria'][0])

    def test_arbitrary_semantics_cannot_hide_under_domain_kind(self):
        r=rules(FIXTURE['input']);r['requirements'][0]['text']='供应商信用良好，保修十年'
        with self.assertRaises(CoreError):coverage.validate(r)
        r['requirements'][0]['kind']='semantic';coverage.validate(r)
        result=coverage.evaluate(r,[{'id':'quote','status':'passed'}])
        self.assertFalse(result['complete']);self.assertFalse(result['semantic_goal_verified'])


class QuoteIntegration(unittest.TestCase):
    setUp=base.GoalPlans.setUp
    tearDown=base.GoalPlans.tearDown
    req=base.GoalPlans.req
    create=base.GoalPlans.create
    detail=base.GoalPlans.detail
    code=base.GoalPlans.code

    def publish(self,wrong=False):
        output=text(FIXTURE['wrong_cheapest' if wrong else 'correct'])
        spec=base.specification('quote-wrong' if wrong else 'quote-correct');spec['capability']='plugin.quote.v1'
        for case in spec['public_cases']+spec['evaluation_cases']:case['expected']=output
        ident=self.core.packages.stage(base.candidate('def run(text):\n    return '+repr(output)+'\n'),spec)
        self.assertTrue(self.core.packages.verify(ident)['passed'])
        slot=self.core.packages.slot(spec['capability']);self.core.packages.activate(ident,slot['revision'] if slot else 0)
        return ident

    def prepare(self,wrong=False):
        if wrong:self.publish(True)
        ident=self.create(input_text=text(FIXTURE['input']),goal='按预算和交期选择最低报价，保存来源')
        proposal=base.proposal(text(FIXTURE['input']));proposal['steps'][0].update(capability='plugin.quote.v1',title='报价选择',expected='冻结条件内最低价')
        goals.command(self.root,{'action':'edit','id':ident,'revision':1,'proposal':proposal})
        return ident,{'action':'approve','id':ident,'revision':self.detail(ident)['plan']['revision'],'acceptance':rules(FIXTURE['input'])}

    def run_quote(self,wrong=False):
        ident,request=self.prepare(wrong);tid=goals.command(self.root,request)['task_id']
        self.assertEqual(self.core.run_task(tid)['status'],'SUCCEEDED')
        return ident,tid,self.detail(ident)

    def test_correct_result_closes_and_reloads_without_dispatch(self):
        ident,tid,d=self.run_quote()
        self.assertEqual(d['completion']['state'],'VERIFIED');self.assertEqual(d['work_closure']['state'],'COMPLETE')
        self.assertFalse(d['completion']['requirement_coverage']['semantic_goal_verified'])
        before=self.core.tasks.actions(tid);self.core.close();self.core=Core(self.root)
        self.assertEqual(self.detail(ident)['completion']['fingerprint'],d['completion']['fingerprint'])
        self.assertEqual(self.core.tasks.actions(tid),before)
        self.assertEqual(self.core.db.one('SELECT COUNT(*) AS n FROM model_calls')['n'],0)

    def test_successful_wrong_tool_is_rejected_and_not_learned(self):
        _,tid,d=self.run_quote(True)
        self.assertEqual(d['completion']['state'],'NEEDS_CORRECTION');self.assertEqual(d['completion']['checks'][0]['reason'],'quote_selection_mismatch')
        self.assertFalse(d['completion']['method_available']);self.assertNotEqual(d['work_closure']['state'],'COMPLETE')
        self.assertEqual(self.core.tasks.get(tid)['spent'],2)

    def test_weak_literal_can_pass_same_wrong_result_but_domain_cannot(self):
        ident,request=self.prepare(True)
        request['acceptance']={'coverage':'recipe','criteria':[{'id':'weak','step_id':'step-1','check':'text_contains','expected':'selected_id'}]}
        tid=goals.command(self.root,request)['task_id'];self.core.run_task(tid)
        d=self.detail(ident);self.assertEqual(d['completion']['state'],'SATISFIED')
        self.assertFalse(d['completion']['requirement_coverage']['complete'])
        result=q.verify(self.core.tasks.get(tid)['body'],rules(FIXTURE['input'])['criteria'][0],decode(self.core.tasks.actions(tid)[0]['result'])['text'])
        self.assertEqual(result['status'],'failed')

    def test_bad_digest_rolls_back_task_grant_and_work_admission(self):
        ident,request=self.prepare();request['acceptance']['criteria'][0]['expected']='0'*64
        grants=self.core.db.all('SELECT * FROM grants');work=self.detail(ident)['work']
        self.code('acceptance_invalid',goals.command,self.root,request)
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[]);self.assertEqual(self.core.db.all('SELECT * FROM grants'),grants)
        self.assertEqual(self.detail(ident)['work'],work)

    def test_first_action_freezes_conditions(self):
        _,tid,_=self.run_quote()
        self.code('acceptance_frozen',Completion(self.core.db).configure,tid,1,rules(FIXTURE['input']))

    def test_verifier_revision_invalidates_previous_acceptance(self):
        _,tid,d=self.run_quote()
        command(self.core,{'action':'completion_feedback','id':tid,'request_id':'quote-owner-accept','fingerprint':d['completion']['fingerprint'],'kind':'accept','note':''})
        self.assertEqual(refresh(self.core,tid)['state'],'ACCEPTED')
        with patch.object(q,'VERSION','quote-selection-test-revision'):
            current=refresh(self.core,tid)
        self.assertEqual(current['state'],'VERIFIED')
        self.assertNotEqual(current['fingerprint'],d['completion']['fingerprint'])

    def test_delayed_correction_reopens_without_rewriting_action_receipts(self):
        ident,tid,d=self.run_quote();before=self.core.tasks.actions(tid)
        command(self.core,{'action':'completion_feedback','id':tid,'request_id':'late-quote-feedback','fingerprint':d['completion']['fingerprint'],'kind':'reject','note':'真实报价后来被供应商撤回'})
        self.assertEqual(self.detail(ident)['completion']['state'],'NEEDS_CORRECTION')
        self.assertNotEqual(self.detail(ident)['work_closure']['state'],'COMPLETE')
        self.assertEqual(self.core.tasks.actions(tid),before)

    def test_tampered_delivered_artifact_invalidates_domain_pass(self):
        _,tid,_=self.run_quote();receipt=decode(self.core.tasks.actions(tid)[-1]['result'])
        (self.root/receipt['relative_path']).write_text('changed',encoding='utf-8')
        current=refresh(self.core,tid)
        self.assertEqual(current['state'],'NEEDS_CORRECTION')
        self.assertFalse(current['evidence_ready'])
        self.assertFalse(current['requirement_coverage']['complete'])

    def test_cancellation_still_blocks_execution(self):
        ident,request=self.prepare();tid=goals.command(self.root,request)['task_id'];d=self.detail(ident)
        goals.command(self.root,{'action':'cancel_work','id':ident,'work_revision':d['work']['revision']})
        self.code('invalid_state',self.core.run_task,tid)
        self.assertEqual(refresh(self.core,tid)['state'],'CANCELLED');self.assertEqual(self.core.tasks.actions(tid),[])


if __name__=='__main__':unittest.main()
