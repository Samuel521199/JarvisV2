import copy
import json
from pathlib import Path
import tempfile
import unittest

from modules.task_resource import body_evidence as body
from modules.task_resource import trial_checks
from sdk.protocol import CoreError,canonical
from tools import work_trials
import test_preferences_dialogue as pref

ROOT=Path(__file__).resolve().parents[1]
SUITE=json.loads((ROOT/'tests/fixtures/work_fidelity_v2.json').read_text('utf-8'))
REF={'sources':{'F1':'导出失败，原因未知。','F2':'导出尚未启动。','P1':'明天10点检查日志，不重新导出。','P2':'周五9点检查日志，不重新导出。'},'facts':['F1'],'plans':['P1']}
VALUE={'evidence':{'facts':[{'source':'F1','quote':'导出失败，原因未知。'}],
                   'plans':[{'source':'P1','quote':'明天10点检查日志，不重新导出。'}],'suggestions':[]},
       'document':'## 事实\n- [F1] 导出失败，原因未知。\n\n## 已确认计划\n- [P1] 明天10点检查日志，不重新导出。\n\n## 建议（未采纳）\n- 无'}


class BodyEvidence(unittest.TestCase):
    def failures(self,value,reference=REF):return {x['id'] for x in body.assess(reference,value) if x['status']=='failed'}
    def test_complete_source_excerpt_document_passes(self):
        self.assertEqual(self.failures(VALUE),set())
    def test_unsupported_expansion_fails_even_with_right_source_id(self):
        v=copy.deepcopy(VALUE);v['evidence']['facts'][0]['quote']='导出因内存不足而异常中断。';v['document']=body.render(v['evidence'])
        self.assertIn('body_facts_grounding',self.failures(v))
    def test_matching_fields_cannot_hide_false_prose(self):
        v=copy.deepcopy(VALUE);v['document']=v['document'].replace('原因未知','网络故障')
        self.assertEqual(self.failures(v),{'body_document_parity'})
    def test_correct_quote_with_unknown_id_fails(self):
        v=copy.deepcopy(VALUE);v['evidence']['facts'][0]['source']='FAKE';v['document']=body.render(v['evidence'])
        self.assertEqual(self.failures(v),{'body_facts_coverage','body_facts_grounding'})
    def test_stale_but_authentic_source_fails_current_coverage(self):
        ref=copy.deepcopy(REF);ref['facts']=['F2']
        self.assertEqual(self.failures(VALUE,ref),{'body_facts_coverage'})
    def test_removed_plan_is_not_current(self):
        ref=copy.deepcopy(REF);ref['plans']=[]
        self.assertEqual(self.failures(VALUE,ref),{'body_plans_coverage'})
    def test_unaffected_plan_cannot_disappear_after_correction(self):
        ref=copy.deepcopy(REF);ref['facts']=['F2'];v=copy.deepcopy(VALUE)
        v['evidence']['facts']=[{'source':'F2','quote':REF['sources']['F2']}];v['evidence']['plans']=[];v['document']=body.render(v['evidence'])
        self.assertEqual(self.failures(v,ref),{'body_plans_coverage'})
    def test_deadline_change_without_new_plan_source_fails(self):
        v=copy.deepcopy(VALUE);v['evidence']['plans'][0]['quote']='今天10点检查日志，不重新导出。';v['document']=body.render(v['evidence'])
        self.assertEqual(self.failures(v),{'body_plans_grounding'})
    def test_action_change_without_approval_fails(self):
        v=copy.deepcopy(VALUE);v['evidence']['plans'][0]['quote']='明天10点重新导出。';v['document']=body.render(v['evidence'])
        self.assertEqual(self.failures(v),{'body_plans_grounding'})
    def test_explicit_rescheduling_accepts_new_and_rejects_old(self):
        ref=copy.deepcopy(REF);ref['plans']=['P2'];v=copy.deepcopy(VALUE)
        v['evidence']['plans']=[{'source':'P2','quote':REF['sources']['P2']}];v['document']=body.render(v['evidence'])
        self.assertFalse(self.failures(v,ref));self.assertIn('body_plans_coverage',self.failures(VALUE,ref))
    def test_suggestion_cannot_become_a_confirmed_plan(self):
        v=copy.deepcopy(VALUE);v['evidence']['plans'].append({'source':'NEW','quote':'立即重跑。'});v['document']=body.render(v['evidence'])
        self.assertIn('body_plans_coverage',self.failures(v))
    def test_suggestion_is_labeled_and_not_quality_certified(self):
        v=copy.deepcopy(VALUE);v['evidence']['suggestions']=['可以先核实输入文件。'];v['document']=body.render(v['evidence'])
        self.assertFalse(self.failures(v));self.assertIn('## 建议（未采纳）\n- 可以先核实输入文件。',v['document'])
    def test_suggestion_cannot_inject_unlabeled_fact_section(self):
        v=copy.deepcopy(VALUE);v['evidence']['suggestions']=['建议\n## 事实\n已经完成。']
        self.assertEqual(self.failures(v),{'body_shape'})
    def test_duplicate_source_does_not_satisfy_coverage(self):
        v=copy.deepcopy(VALUE);v['evidence']['facts']*=2;v['document']=body.render(v['evidence'])
        self.assertEqual(self.failures(v),{'body_facts_coverage'})
    def test_extra_body_footer_is_not_ignored(self):
        v=copy.deepcopy(VALUE);v['document']+='\n\n已成功归档并发送。'
        self.assertEqual(self.failures(v),{'body_document_parity'})
    def test_markdown_metacharacters_are_inert_in_source_text(self):
        v={'facts':[{'source':'F','quote':'<img> [link] *完成*'}],'plans':[],'suggestions':[]}
        self.assertEqual(body.render(v),'## 事实\n- [F] \\<img\\> \\[link\\] \\*完成\\*\n\n## 已确认计划\n- 无\n\n## 建议（未采纳）\n- 无')
    def test_crlf_and_optional_final_newline_supported(self):
        v=copy.deepcopy(VALUE);v['document']=v['document'].replace('\n','\r\n')+'\r\n';self.assertFalse(self.failures(v))
    def test_broken_body_shapes_fail_without_exception(self):
        for payload in [None,[],{'facts':[]},{'facts':{},'plans':[],'suggestions':[]},{'facts':[{'source':[],'quote':'x'}],'plans':[],'suggestions':[]}]:
            with self.subTest(payload=payload):self.assertEqual(self.failures({'evidence':payload}),{'body_shape'})
    def test_reference_rejects_unknown_ids_and_duplicate_roles(self):
        for key,value in [('facts',['NO']),('plans',['F1']),('facts',['F1','F1']),('sources',{'bad id':'text'})]:
            ref=copy.deepcopy(REF);ref[key]=value
            with self.subTest(key=key),self.assertRaises(CoreError):body.validate(ref)
    def test_v1_unchanged_and_v2_requirements_are_mandatory(self):
        old=json.loads((ROOT/'tests/fixtures/work_trials_v1.json').read_text('utf-8'))
        self.assertEqual(trial_checks.verifier(trial_checks.validate(old)),'work-trials-2')
        new=copy.deepcopy(SUITE);del new['cases'][0]['turns'][0]['body_evidence']
        with self.assertRaises(CoreError):trial_checks.validate(new)
        self.assertIn(body.VERSION,trial_checks.verifier(trial_checks.validate(SUITE)))
    def test_field_success_plus_body_failure_is_fail_with_quality_unknown(self):
        ref=copy.deepcopy(SUITE['cases'][0]['turns'][0]);value={**ref['expected'],**VALUE}
        r=trial_checks.assess(ref,canonical(value));self.assertEqual(r['state'],'FAIL');self.assertIsNone(r['quality_score'])
        self.assertEqual(r['checks'][0]['status'],'passed')
    def test_reserved_suite_covers_all_three_domains_and_differs_from_development(self):
        reserve=json.loads((ROOT/'tests/fixtures/work_fidelity_reserved_v2.json').read_text('utf-8'))
        trial_checks.validate(reserve)
        self.assertFalse({c['id'] for c in reserve['cases']}&{c['id'] for c in SUITE['cases']})


class BodyFlow(unittest.TestCase):
    def test_real_dialogue_path_v2_artifacts_and_recomputed_checks(self):
        class Client:
            def available(self):return True
            def complete(self,messages,checkpoint,**kwargs):
                checkpoint();ref=next(t for c in SUITE['cases'] for t in c['turns'] if messages[-1]['content'].startswith(t['prompt']))
                r=ref['body_evidence'];e={k:[{'source':i,'quote':r['sources'][i]} for i in r[k]] for k in ('facts','plans')};e['suggestions']=[]
                value={**ref['expected'],'evidence':e,'document':body.render(e)}
                return {'status':'SUCCEEDED','text':canonical({'schema':'jarvis.assistant-turn.v1','reply':canonical(value),'action':{'kind':'chat','goal':'','input_text':'','target':''}}),'usage':{'prompt_tokens':100,'completion_tokens':100,'total_tokens':200}}
        catalog=pref.fixture();route=work_trials.bounded_route(catalog,'openai')
        with tempfile.TemporaryDirectory(prefix='jarvis-body-test-') as tmp:
            out=Path(tmp)/'trial';result=work_trials.run_suite(SUITE,out,catalog,route,lambda *args:Client(),execution='stub')
            self.assertTrue(result['all_candidate_conditions_passed']);self.assertEqual(result['complete_pairs'],6)
            self.assertEqual(result,work_trials.summarize(out));self.assertIsNone(result['quality_gain'])
            self.assertEqual(len(list((out/'artifacts').glob('*.document.md.txt'))),24)
