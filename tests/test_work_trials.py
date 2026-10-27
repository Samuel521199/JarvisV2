"""Three-domain evidence, missingness and replay integrity, with no paid calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from modules.task_resource import trial_checks as policy
from sdk.protocol import CoreError, canonical, digest
from tools import work_trials as runner
import test_preferences_dialogue as pref

SUITE=json.loads((Path(__file__).parent/'fixtures/work_trials_v1.json').read_text('utf-8'))


class TrialPolicy(unittest.TestCase):
    def ref(self):return SUITE['cases'][0]['turns'][0]
    def test_all_three_domains_required(self):
        s=copy.deepcopy(SUITE);s['cases']=s['cases'][:4]
        with self.assertRaises(CoreError):policy.validate(s)
    def test_duplicate_cases_do_not_inflate_independence(self):
        for kind in ('id','content'):
            s=copy.deepcopy(SUITE);c=copy.deepcopy(s['cases'][0]);c['id']=c['id'] if kind=='id' else 'copy';s['cases'].append(c)
            with self.subTest(kind=kind),self.assertRaises(CoreError):policy.validate(s)
    def test_invalid_shapes_are_rejected(self):
        for field,value in [('origin','real_verified'),('cases',{}),('schema','other')]:
            s=copy.deepcopy(SUITE);s[field]=value
            with self.subTest(field=field),self.assertRaises(CoreError):policy.validate(s)
        s=copy.deepcopy(SUITE);s['cases'][0]['turns'][0]['unordered']=[{}]
        with self.assertRaises(CoreError):policy.validate(s)
    def test_order_of_eligible_items_is_not_quality_failure(self):
        ref=self.ref();v={**ref['expected'],'eligible_ids':['B','A']}
        self.assertEqual(policy.assess(ref,canonical(v))['state'],'PASS')
    def test_duplicates_or_missing_eligible_items_fail(self):
        for values in [['A','A','B'],['B']]:
            v={**self.ref()['expected'],'eligible_ids':values}
            self.assertEqual(policy.assess(self.ref(),canonical(v))['state'],'FAIL')
    def test_duplicate_json_keys_and_nonfinite_rejected(self):
        for v in ['{"a":1,"a":2}','{"a":NaN}','[]','not-json']:
            self.assertEqual(policy.assess(self.ref(),v)['state'],'FAIL')
    def test_boolean_is_not_numeric_or_text_mastery(self):
        ref=SUITE['cases'][-1]['turns'][-1]
        for v in [0,'false',None]:
            x={**ref['expected'],'next_step':'practice','independent_mastery':v}
            self.assertEqual(policy.assess(ref,canonical(x))['state'],'FAIL')
    def test_unanswered_retry_cannot_be_marked_mastered(self):
        ref=SUITE['cases'][-1]['turns'][-1];v={**ref['expected'],'next_step':'practice','independent_mastery':True}
        self.assertEqual(policy.assess(ref,canonical(v))['state'],'FAIL')
    def test_document_current_truth_and_sources_must_both_match(self):
        ref=SUITE['cases'][2]['turns'][1];v={**ref['expected'],'document':'# report','minutes':20}
        self.assertEqual(policy.assess(ref,canonical(v))['state'],'FAIL')
        v.update(minutes=15,sources=['S1']);self.assertEqual(policy.assess(ref,canonical(v))['state'],'FAIL')
    def test_no_records_means_unmeasured_not_zero_quality(self):
        r=policy.summary(SUITE,[])
        self.assertEqual(r['complete_pairs'],0);self.assertFalse(r['all_candidate_conditions_passed']);self.assertIsNone(r['quality_gain'])
        self.assertEqual(r['domains']['learning']['workflow_on']['UNMEASURED'],2)
    def test_one_failed_domain_cannot_hide_in_average(self):
        rows=[]
        for c in SUITE['cases']:
            for arm in policy.ARMS:
                for i in range(len(c['turns'])):rows.append({'case_id':c['id'],'arm':arm,'turn':i,'assessment':{'state':'FAIL' if c['domain']=='learning' and arm=='workflow_on' else 'PASS'}})
        r=policy.summary(SUITE,rows)
        self.assertFalse(r['all_candidate_conditions_passed']);self.assertEqual(r['descriptive_regressed_pairs'],2)
        self.assertEqual(r['independent_cases'],6);self.assertFalse(r['all_functional_excellence_verified'])
    def test_unplanned_or_duplicate_slots_rejected(self):
        row={'case_id':'unknown','arm':'workflow_on','turn':0,'assessment':{'state':'PASS'}}
        with self.assertRaises(CoreError):policy.summary(SUITE,[row])
        row['case_id']=SUITE['cases'][0]['id']
        with self.assertRaises(CoreError):policy.summary(SUITE,[row,row])
    def test_missing_price_and_usage_are_not_zero(self):
        r=runner.cost_summary([{'attempts':[{'usage':{},'estimate':{'amount':None,'currency':None}}]}])
        self.assertIsNone(r['total_tokens']);self.assertEqual(r['unpriced_attempts'],1);self.assertIsNone(r['full_cost'])
    def test_currencies_remain_separate(self):
        r=runner.cost_summary([{'attempts':[{'usage':{'total_tokens':10},'estimate':{'amount':1,'currency':c}} for c in ['CNY','USD']]}])
        self.assertEqual(r['known_api_estimates'],{'CNY':1,'USD':1});self.assertEqual(r['total_tokens'],20)
    def test_failure_plus_missing_turns_is_not_complete_pair(self):
        c=SUITE['cases'][2];rows=[{'case_id':c['id'],'arm':a,'turn':0,'assessment':{'state':'FAIL'}} for a in policy.ARMS]
        r=policy.summary(SUITE,rows);self.assertEqual(r['complete_pairs'],0);self.assertFalse(r['comparison_complete'])
        self.assertEqual(r['domains']['documents']['workflow_on']['FAIL'],1)
    def test_failed_delivery_unknown_and_cancel_have_separate_meaning(self):
        for state,expected in [('FAILED','FAIL'),('INVALID','FAIL'),('UNKNOWN','UNMEASURED'),('CANCELLED','UNMEASURED')]:
            r=policy.observation(self.ref(),None,state,False,False);self.assertEqual(r['state'],expected);self.assertIsNone(r['quality_score'])
    def test_output_budget_override_bounded_and_does_not_change_catalog(self):
        catalog=pref.fixture();before=copy.deepcopy(catalog);r=runner.bounded_route(catalog,'openai',reasoning='low',max_output_tokens=4096)
        self.assertEqual(r['max_output_tokens'],4096);self.assertEqual(catalog,before)
        for n in [True,0,8193]:
            with self.assertRaises(CoreError):runner.bounded_route(catalog,'openai',max_output_tokens=n)


class TrialFlow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jarvis-trial-test-');self.out=Path(self.temp.name)/'experiment'
        self.catalog=pref.fixture();self.route=runner.bounded_route(self.catalog,'openai');self.seen=[]
    def tearDown(self):self.temp.cleanup()
    def factory(self,mode='correct'):
        seen=self.seen
        class Client:
            def available(self):return True
            def complete(self,messages,checkpoint,**kwargs):
                checkpoint();seen.append(messages)
                if mode=='unknown':return {'status':'UNKNOWN','code':'injected_transport_timeout','usage':{}}
                case=next(c for c in SUITE['cases'] if messages[0]['content'].startswith(c['turns'][0]['prompt']))
                ref=next(t for t in case['turns'] if messages[-1]['content'].startswith(t['prompt']))
                v={**ref['expected'],**{k:'# 合成测试正文' for k in ref['text_fields']}}
                if mode=='wrong' and 'selected_id' in v:v['selected_id']='wrong'
                return {'status':'SUCCEEDED','text':canonical({'schema':'jarvis.assistant-turn.v1','reply':canonical(v),
                    'action':{'kind':'chat','goal':'','input_text':'','target':''}}),'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150}}
        return lambda *args:Client()
    def run_case(self,mode='correct'):
        return runner.run_suite(SUITE,self.out,self.catalog,self.route,self.factory(mode),execution='stub')
    def test_real_host_paths_all_domains_artifacts_and_ab_ba_order(self):
        r=self.run_case();self.assertTrue(r['comparison_complete']);self.assertTrue(r['all_candidate_conditions_passed'])
        self.assertEqual(len(self.seen),24);self.assertEqual(r['independent_cases'],6);self.assertIsNone(r['quality_gain'])
        f=json.loads((self.out/'frozen.json').read_text('utf-8'))
        self.assertEqual([x['arm'] for x in f['order'][:4]],['workflow_off','workflow_on','workflow_on','workflow_off'])
        self.assertEqual(len(list((self.out/'artifacts').glob('*.reply.md.txt'))),24)
        self.assertEqual(len(list((self.out/'artifacts').glob('*.document.md.txt'))),8)
        self.assertEqual(len(list((self.out/'artifacts').glob('*.native.json'))),24)
        self.assertNotIn('expected',canonical(self.seen[0]));self.assertEqual(r['costs']['attempts'],24)
    def test_unknown_calls_stop_and_missing_domains_stay_unmeasured(self):
        r=self.run_case('unknown');self.assertEqual(len(self.seen),3);self.assertFalse(r['comparison_complete'])
        self.assertEqual(r['domains']['learning']['workflow_on']['UNMEASURED'],2)
    def test_content_failure_does_not_skip_other_domains(self):
        r=self.run_case('wrong');self.assertEqual(len(self.seen),24)
        self.assertEqual(r['domains']['comparison']['workflow_on']['FAIL'],2)
        self.assertEqual(r['domains']['learning']['workflow_on']['PASS'],2)
    def test_existing_experiment_is_not_replayed(self):
        self.out.mkdir()
        with self.assertRaises(FileExistsError):self.run_case()
        self.assertEqual(self.seen,[])
    def test_owner_stop_prevents_call(self):
        def stopped():raise CoreError('stopped','owner stop')
        with self.assertRaises(CoreError):runner.run_suite(SUITE,self.out,self.catalog,self.route,self.factory(),execution='stub',owner_checkpoint=stopped)
        self.assertEqual(self.seen,[]);self.assertTrue((self.out/'frozen.json').exists())
    def test_source_change_stops_before_call(self):
        with patch.object(runner,'source_snapshot',side_effect=[{'a':'before'},{'a':'after'}]):
            with self.assertRaises(CoreError):self.run_case()
        self.assertEqual(self.seen,[])
    def test_tampered_result_or_artifact_refuses_summary(self):
        self.run_case();p=next((self.out/'turns').glob('*.result.json'));raw=p.read_bytes();r=json.loads(raw)
        r['reply']='changed';p.write_text(json.dumps(r),encoding='utf-8')
        with self.assertRaises(CoreError):runner.summarize(self.out)
        p.write_bytes(raw);next((self.out/'artifacts').glob('*.reply.md.txt')).write_text('changed',encoding='utf-8')
        with self.assertRaises(CoreError):runner.summarize(self.out)
