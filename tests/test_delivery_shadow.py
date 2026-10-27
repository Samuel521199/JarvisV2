import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from host.core import Core
from host.dialogue import DialogueHost
from host.delivery_review import observe
from modules.dialogue.store import Dialogues
from modules.dialogue import delivery_basis
from modules.preferences.store import resolve
from modules.task_resource import delivery_review,body_evidence
from modules.workspace.sessions import configuration
from sdk.protocol import CoreError,canonical,decode,digest
from tools import work_trials
import test_preferences_dialogue as pref

FACT='数据导出失败，原因未知。'
PLAN='明天10点检查日志，不重跑导出。'
TEXT=FACT+'\n'+PLAN
INPUT={'expected_revision':0,'facts':[FACT],'plans':[PLAN]}


def basis():return delivery_basis.update(INPUT,TEXT,'source-1',delivery_basis.empty())
def document(b):
    e={k:[{'source':x['id'],'quote':x['quote']} for x in b['entries'] if x['kind']==k] for k in ('facts','plans')};e['suggestions']=[]
    return {'evidence':e,'document':body_evidence.render(e)}


class ShadowPolicy(unittest.TestCase):
    def test_exact_free_prose_is_not_certified(self):
        r=delivery_review.review(basis(),TEXT,'SUCCEEDED');self.assertEqual(r['state'],'PROSE_UNVERIFIED');self.assertIsNone(r['quality_score']);self.assertFalse(r['would_block'])
    def test_paraphrase_is_only_suspected_not_proven_wrong(self):
        r=delivery_review.review(basis(),'导出未成功且原因尚不清楚；次日上午十时查日志，不重新执行。','SUCCEEDED')
        self.assertEqual(r['state'],'REVIEW');self.assertIn('paraphrase',r['reason']);self.assertFalse(r['would_block'])
    def test_missing_plan_detected(self):
        r=delivery_review.review(basis(),FACT,'SUCCEEDED');self.assertEqual(r['state'],'REVIEW')
        self.assertEqual(next(x for x in r['checks'] if x['id']=='P1')['status'],'literal_not_found')
    def test_correct_quotes_plus_invented_cause_remain_unverified(self):
        r=delivery_review.review(basis(),TEXT+'\n失败原因已经确认为内存不足。','SUCCEEDED')
        self.assertEqual(r['state'],'PROSE_UNVERIFIED');self.assertIn('additions',r['reason'])
    def test_fields_cannot_mask_missing_plan_in_document(self):
        value={'document':FACT,'plan':PLAN};r=delivery_review.review(basis(),canonical(value),'SUCCEEDED')
        self.assertEqual(r['state'],'REVIEW')
    def test_explicit_excerpt_format_matches(self):
        r=delivery_review.review(basis(),canonical(document(basis())),'SUCCEEDED')
        self.assertEqual(r['state'],'EXCERPT_MATCH');self.assertFalse(r['would_block'])
    def test_excerpt_extra_body_fails(self):
        v=document(basis());v['document']+='\n已完成导出。'
        r=delivery_review.review(basis(),canonical(v),'SUCCEEDED');self.assertEqual(r['state'],'REVIEW')
    def test_basis_removal_does_not_resurrect_old_plan(self):
        b=delivery_basis.update({'expected_revision':1,'facts':[FACT],'plans':[]},FACT,'source-2',basis())
        self.assertEqual(delivery_review.review(b,canonical(document(b)),'SUCCEEDED')['state'],'EXCERPT_MATCH')
        self.assertEqual(delivery_review.review(b,canonical(document(basis())),'SUCCEEDED')['state'],'REVIEW')
    def test_failed_cancelled_and_goal_are_not_certified(self):
        for status,action in [('FAILED',None),('CANCELLED',None),('SUCCEEDED','goal')]:
            self.assertEqual(delivery_review.review(basis(),TEXT,status,action)['state'],'NOT_APPLICABLE')
    def test_no_basis_stays_unknown(self):
        self.assertEqual(delivery_review.review(delivery_basis.empty(),'任意回答','SUCCEEDED')['state'],'NO_BASIS')
    def test_duplicate_json_keys_do_not_get_excerpt_match(self):
        raw='{"document":"'+TEXT.replace('\n','\\n')+'","document":"假资料","evidence":{}}'
        self.assertNotEqual(delivery_review.review(basis(),raw,'SUCCEEDED')['state'],'EXCERPT_MATCH')
    def test_observer_exception_does_not_veto_response(self):
        result={'status':'SUCCEEDED','text':TEXT};before=copy.deepcopy(result)
        with patch.object(delivery_review,'review',side_effect=RuntimeError('injected')):
            r=observe({'delivery_basis':canonical(basis())},result)
        self.assertEqual(result,before);self.assertEqual(r['state'],'UNAVAILABLE');self.assertFalse(r['would_block'])
    def test_source_spans_and_digest_bind_to_original_message(self):
        b=basis()
        for x in b['entries']:self.assertEqual(TEXT[x['start']:x['end']],x['quote'])
        self.assertEqual(b['digest'],digest({k:v for k,v in b.items() if k!='digest'}))
    def test_draft_settings_accept_and_bound_optional_basis(self):
        d={'delivery_basis':{'enabled':True,'expected_revision':1,'facts':FACT,'plans':PLAN}}
        self.assertEqual(configuration(d),d)
        d['delivery_basis']['expected_revision']=True
        with self.assertRaises(CoreError):configuration(d)


class ShadowStore(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jarvis-shadow-');self.root=Path(self.temp.name)
        core=Core.initialize(self.root);self.catalog=pref.fixture();core.preferences.install(self.catalog,{});core.close()
        self.store=Dialogues(self.root);self.chat=self.store.create()
    def tearDown(self):self.store.close();self.temp.cleanup()
    def command(self,key='first',text=TEXT,update=True):
        v={'chat_id':self.chat,'request_id':key,'text':text,'provider':'openai','model':'fixture','reasoning':'default','memory_enabled':False,'assistant_mode':True}
        if update:v['delivery_basis']=copy.deepcopy(INPUT)
        return v
    def begin(self,command):return self.store.begin(command,[resolve(self.catalog,'openai')],allow_queue=True)
    def test_snapshot_is_durable_and_inherited_without_new_update(self):
        self.begin(self.command());self.begin(self.command('second','按原计划继续整理',False));b=decode(self.store.turn('second')['delivery_basis'])
        self.assertEqual(b['revision'],1);self.assertEqual(b['source_turn'],'first')
        self.store.close();self.store=Dialogues(self.root);self.assertEqual(self.store.basis(self.chat),b)
    def test_future_update_cannot_change_queued_turn_snapshot(self):
        self.begin(self.command());original=self.store.turn('first')['delivery_basis']
        c=self.command('second',FACT);c['delivery_basis']={'expected_revision':1,'facts':[FACT],'plans':[]};self.begin(c)
        self.assertEqual(self.store.turn('first')['delivery_basis'],original);self.assertEqual(self.store.basis(self.chat)['revision'],2)
    def test_stale_writer_rejected_atomically(self):
        self.begin(self.command())
        with self.assertRaises(CoreError) as e:self.begin(self.command('stale'))
        self.assertEqual(e.exception.code,'delivery_basis_conflict');self.assertEqual(self.store.basis(self.chat)['revision'],1)
        self.assertIsNone(self.store.db.execute("SELECT id FROM turns WHERE id='stale'").fetchone())
    def test_duplicate_request_is_idempotent_even_after_new_revision(self):
        first=self.command();self.begin(first);c=self.command('second',FACT);c['delivery_basis']={'expected_revision':1,'facts':[FACT],'plans':[]};self.begin(c)
        self.assertFalse(self.begin(first));self.assertEqual(self.store.basis(self.chat)['revision'],2)
    def test_unbound_reference_rejected_before_mutation(self):
        c=self.command(text='消息没有那些资料')
        with self.assertRaises(CoreError):self.begin(c)
        self.assertEqual(self.store.basis(self.chat)['revision'],0)
    def test_duplicate_or_overlong_basis_rejected(self):
        for bad in [{'expected_revision':0,'facts':[FACT,FACT],'plans':[]},{'expected_revision':True,'facts':[],'plans':[]},{'expected_revision':0,'facts':{},'plans':[]}]:
            c=self.command();c['delivery_basis']=bad
            with self.subTest(bad=bad),self.assertRaises(CoreError):self.begin(c)
    def test_total_basis_text_is_bounded(self):
        facts=['x'*1100+str(i) for i in range(6)];c=self.command(text='\n'.join(facts));c['delivery_basis']={'expected_revision':0,'facts':facts,'plans':[]}
        with self.assertRaises(CoreError):self.begin(c)
        self.assertEqual(self.store.basis(self.chat)['revision'],0)
    def test_cross_chat_does_not_inherit_basis(self):
        self.begin(self.command());other=self.store.create();c=self.command('other','普通消息',False);c['chat_id']=other;self.begin(c)
        self.assertIsNone(self.store.turn('other')['delivery_basis'])
    def test_archived_chat_cannot_change_basis(self):
        self.store.update(self.chat,{'archived':True})
        with self.assertRaises(CoreError):self.begin(self.command())
        self.assertEqual(self.store.basis(self.chat)['revision'],0)
    def test_recovery_preserves_basis_without_promoting_reply(self):
        self.begin(self.command());self.store.db.execute("UPDATE turns SET status='RUNNING' WHERE id='first'")
        self.store.recover();self.assertEqual(self.store.turn('first')['status'],'UNKNOWN');self.assertEqual(self.store.basis(self.chat)['revision'],1)
    def test_old_review_marked_stale_after_new_basis(self):
        self.begin(self.command());r={'status':'SUCCEEDED','text':TEXT};r['delivery_review']=observe(self.store.turn('first'),r);self.store.finish('first',r)
        self.assertFalse(self.store.read(self.chat)['turns'][0]['delivery_review']['stale'])
        c=self.command('second',FACT);c['delivery_basis']={'expected_revision':1,'facts':[FACT],'plans':[]};self.begin(c)
        self.assertTrue(self.store.read(self.chat)['turns'][0]['delivery_review']['stale'])
    def test_context_uses_frozen_basis_and_labels_no_authority(self):
        self.begin(self.command());content=self.store.context('first')[-1]['content']
        self.assertIn(PLAN,content);self.assertIn('不是外部执行授权',content);self.assertIn('"revision":1',content)


class ShadowHost(unittest.TestCase):
    setUp=ShadowStore.setUp
    tearDown=ShadowStore.tearDown
    command=ShadowStore.command
    begin=ShadowStore.begin
    def run_host(self,reply,broken=False):
        host=DialogueHost(self.root)
        try:
            self.begin(self.command());wire={'schema':'jarvis.assistant-turn.v1','reply':reply,'action':{'kind':'chat','goal':'','input_text':'','target':''}}
            with patch('host.dialogue.NativeModel') as client:
                client.return_value.available.return_value=True
                client.return_value.complete.return_value={'status':'SUCCEEDED','text':canonical(wire),'usage':{'total_tokens':1}}
                if broken:
                    with patch.object(delivery_review,'review',side_effect=RuntimeError('injected')):host.run('first')
                else:host.run('first')
            return self.store.turn('first')
        finally:host.close()
    def test_shadow_failure_never_rewrites_or_fails_reply(self):
        row=self.run_host('这是自由回答。',True);self.assertEqual(row['status'],'SUCCEEDED');self.assertEqual(row['reply'],'这是自由回答。')
        self.assertEqual(decode(row['delivery_review'])['state'],'UNAVAILABLE')
    def test_missing_plan_is_durable_observation_not_veto(self):
        row=self.run_host(FACT);self.assertEqual(row['status'],'SUCCEEDED');self.assertEqual(row['reply'],FACT)
        self.assertEqual(decode(row['delivery_review'])['state'],'REVIEW')
        core=Core(self.root)
        try:self.assertEqual(core.db.one('SELECT COUNT(*) AS n FROM tasks')['n'],0)
        finally:core.close()


class ShadowTrial(unittest.TestCase):
    def test_explicit_input_pack_has_exact_case_and_turn_mapping(self):
        root=Path(__file__).parent/'fixtures';suite=json.loads((root/'delivery_shadow_v2.json').read_text('utf-8'))
        inputs=json.loads((root/'delivery_shadow_inputs.json').read_text('utf-8'));work_trials.validate_basis_inputs(suite,inputs)
        del inputs['cases']['shadow-learning']
        with self.assertRaises(CoreError):work_trials.validate_basis_inputs(suite,inputs)
    def test_real_host_capture_and_shadow_recomputation(self):
        root=Path(__file__).parent/'fixtures';suite=json.loads((root/'delivery_shadow_v2.json').read_text('utf-8'))
        inputs=json.loads((root/'delivery_shadow_inputs.json').read_text('utf-8'));seen=[]
        class Client:
            def available(self):return True
            def complete(self,messages,checkpoint,**kwargs):
                checkpoint();seen.append(messages[-1]['content'])
                ref=next(t for c in suite['cases'] for t in c['turns'] if messages[-1]['content'].startswith(t['prompt']))
                r=ref['body_evidence'];e={k:[{'source':i,'quote':r['sources'][i]} for i in r[k]] for k in ('facts','plans')};e['suggestions']=[]
                value={**ref['expected'],'evidence':e,'document':body_evidence.render(e)}
                return {'status':'SUCCEEDED','text':canonical({'schema':'jarvis.assistant-turn.v1','reply':canonical(value),'action':{'kind':'chat','goal':'','input_text':'','target':''}}),'usage':{}}
        catalog=pref.fixture();route=work_trials.bounded_route(catalog,'openai')
        with tempfile.TemporaryDirectory(prefix='jarvis-shadow-capture-') as tmp:
            out=Path(tmp)/'trial';r=work_trials.run_suite(suite,out,catalog,route,lambda *args:Client(),execution='stub',basis_inputs=inputs)
            self.assertEqual(r['shadow_states'],{'EXCERPT_MATCH':12});self.assertTrue(r['all_candidate_conditions_passed'])
            self.assertEqual(r,work_trials.summarize(out));self.assertNotIn('"expected":',canonical(seen))
            p=next((out/'turns').glob('*.result.json'));row=json.loads(p.read_text('utf-8'));row['delivery_review']['state']='PROSE_UNVERIFIED'
            row['record_digest']=digest({k:v for k,v in row.items() if k!='record_digest'});p.write_text(canonical(row),encoding='utf-8')
            with self.assertRaises(CoreError):work_trials.summarize(out)
