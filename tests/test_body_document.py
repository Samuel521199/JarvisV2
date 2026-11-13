import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from host.core import Core
from host.dialogue import DialogueHost
from host.delivery_review import materialize
from modules.dialogue.store import Dialogues
from modules.dialogue.document_format import FORMAT,context_basis
from modules.preferences.store import resolve
from modules.task_resource import body_document,body_evidence
from sdk.protocol import CoreError,canonical,decode,digest
from tools import work_trials
import json
import test_preferences_dialogue as pref

FACT='开发调用require_online被拒绝，未开启直接外联。'
PLAN='退出后核对新目录，不自动重试UNKNOWN。'


class BodyDocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        core=Core.initialize(self.root);self.catalog=pref.fixture();core.preferences.install(self.catalog,{});core.close()
        self.store=Dialogues(self.root);self.addCleanup(self.store.close);self.chat=self.store.create()
    def begin(self,**changes):
        command={'chat_id':self.chat,'request_id':'one','text':FACT+'\n'+PLAN,'provider':'openai','model':'fixture','reasoning':'default',
            'memory_enabled':False,'assistant_mode':True,'delivery_format':FORMAT,
            'delivery_basis':{'expected_revision':0,'facts':[FACT],'plans':[PLAN]}}
        command.update(changes);self.store.begin(command,[resolve(self.catalog,'openai')],allow_queue=True)
        return self.store.turn(command['request_id'])
    def value(self):
        evidence={'facts':[{'source':'F1','quote':FACT}],'plans':[{'source':'P1','quote':PLAN}],'suggestions':[]}
        return {'business_result':False,'evidence':evidence,'document':'model body without Markdown escaping'}
    def result(self,value=None):return {'status':'SUCCEEDED','text':canonical(value or self.value()),'assistant_action':{'kind':'chat'},'usage':{'total_tokens':1}}
    def test_explicit_render_changes_only_document_and_records_digests(self):
        turn=self.begin();original=self.result();saved=copy.deepcopy(original);result,receipt=materialize(turn,original)
        value=decode(result['text']);expected=self.value();expected['document']=body_evidence.render(expected['evidence'])
        self.assertEqual(value,expected);self.assertIn('require\\_online',value['document'])
        self.assertEqual(original,saved);self.assertEqual(receipt['state'],'RENDERED')
        self.assertEqual(receipt['original_reply_digest'],digest(original['text']));self.assertEqual(receipt['model_calls'],0)
        self.assertIsNone(receipt['quality_score']);self.assertNotIn('original_reply',receipt)
    def test_default_shadow_never_rewrites_a_reply(self):
        turn=self.begin();command=decode(turn['request']);del command['delivery_format'];turn={**turn,'request':canonical(command)}
        original=self.result();result,receipt=materialize(turn,original)
        self.assertEqual(result,original);self.assertIsNone(receipt)
    def test_repeated_render_is_idempotent_and_cannot_expand_past_reply_bound(self):
        turn=self.begin();rendered,_=materialize(turn,self.result());again,receipt=materialize(turn,rendered)
        self.assertEqual(again,rendered);self.assertEqual(receipt['state'],'UNCHANGED')
        value=self.value();value['document']='';value['pad']='';value['pad']='x'*(29980-len(canonical(value)))
        original=self.result(value);self.assertLess(len(original['text']),30000)
        output,receipt=materialize(turn,original)
        self.assertEqual(output,original);self.assertEqual(receipt['reason'],'rendered_reply_bound')
    def test_context_dedup_keeps_time_revision_and_falls_back_on_ambiguous_ids(self):
        turn=self.begin();basis=decode(turn['delivery_basis']);original=copy.deepcopy(basis)
        text='F1：'+FACT+'\nP1：'+PLAN
        compact=context_basis(basis,text)
        self.assertEqual(compact['quote_locations'],'visible_message_id_lines')
        self.assertEqual(compact['digest'],basis['digest']);self.assertEqual(compact['source_time_utc'],basis['source_time_utc'])
        self.assertNotIn('quote',compact['entries'][0]);self.assertEqual(basis,original)
        for ambiguous in [text+'\nF1：过期的事实。',text.replace(FACT,'别的事实。'),FACT+'\n'+PLAN]:
            fallback=context_basis(basis,ambiguous)
            self.assertEqual(fallback['quote_locations'],'entries');self.assertEqual(fallback['entries'][0]['quote'],FACT)
    def test_wrong_missing_stale_and_duplicate_sources_are_not_repaired(self):
        turn=self.begin();values=[]
        wrong=self.value();wrong['evidence']['facts'][0]['quote']='invented cause';values.append(wrong)
        missing=self.value();missing['evidence']['plans']=[];values.append(missing)
        extra=self.value();extra['evidence']['facts'].append({'source':'F2','quote':'old withdrawn fact'});values.append(extra)
        duplicate=self.value();duplicate['evidence']['facts']*=2;values.append(duplicate)
        for value in values:
            original=self.result(value);result,receipt=materialize(turn,original)
            self.assertEqual(result,original);self.assertEqual(receipt['state'],'DECLINED')
    def test_duplicate_json_keys_and_nonfinite_values_are_not_normalized(self):
        turn=self.begin()
        for raw in ['{"document":"first","document":"last","evidence":{}}','{"document":"","value":NaN}']:
            original={**self.result(),'text':raw};result,receipt=materialize(turn,original)
            self.assertEqual(result,original);self.assertEqual(receipt['state'],'DECLINED')
    def test_failed_cancelled_and_nonchat_actions_are_not_rendered(self):
        turn=self.begin()
        for status,action in [('FAILED','chat'),('CANCELLED','chat'),('SUCCEEDED','goal'),('SUCCEEDED','commitment')]:
            original={**self.result(),'status':status,'assistant_action':{'kind':action}}
            self.assertEqual(materialize(turn,original),(original,None))
    def test_unknown_format_and_missing_basis_reject_atomically(self):
        for changes in [{'delivery_format':'unknown'},{'delivery_basis':{'expected_revision':0,'facts':[],'plans':[]}}]:
            with self.assertRaises(CoreError):self.begin(**changes)
            self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM turns').fetchone()[0],0)
            self.assertEqual(self.store.basis(self.chat)['revision'],0)
    def test_real_host_persists_rendered_reply_receipt_and_session_file(self):
        host=DialogueHost(self.root);self.begin()
        try:
            wire={'schema':'jarvis.assistant-turn.v1','reply':canonical(self.value()),'action':{'kind':'chat','goal':'','input_text':'','target':''}}
            with patch('host.dialogue.NativeModel') as client:
                client.return_value.available.return_value=True
                client.return_value.complete.return_value={'status':'SUCCEEDED','text':canonical(wire),'usage':{'total_tokens':1}}
                host.run('one')
            row=self.store.turn('one');review=decode(row['delivery_review'])
            self.assertEqual(review['state'],'EXCERPT_MATCH');self.assertEqual(review['rendering']['state'],'RENDERED')
            self.assertEqual(decode(row['reply'])['document'],body_evidence.render(self.value()['evidence']))
            from modules.workspace.sessions import Sessions
            sessions=Sessions(self.root)
            try:self.assertEqual((sessions.path(self.chat)/'replies/one.md').read_bytes(),row['reply'].encode())
            finally:sessions.close()
            self.assertEqual(client.return_value.complete.call_count,1)
            core=Core(self.root)
            try:self.assertEqual(core.db.one('SELECT COUNT(*) AS n FROM tasks')['n'],0)
            finally:core.close()
        finally:host.close()

    def test_trial_recomputes_rendering_from_native_reply_not_a_claimed_pass(self):
        value=self.value();value['document']='';wire=canonical({'schema':'jarvis.assistant-turn.v1','reply':canonical(value),'action':{'kind':'chat','goal':'','input_text':'','target':''}})
        class Client:
            def available(self):return True
            def complete(self,*args,**kwargs):return {'status':'SUCCEEDED','text':wire,'usage':{}}
        cases=[];inputs={'schema':'jarvis.delivery-inputs.v1','cases':{}}
        for domain in ('comparison','documents','learning'):
            key='render-'+domain;inputs['cases'][key]=[{'expected_revision':0,'facts':[FACT],'plans':[PLAN]}]
            cases.append({'id':key,'domain':domain,'skill':'none','turns':[{'prompt':domain+'\n'+FACT+'\n'+PLAN,
                'expected':{'business_result':False},'unordered':[],'text_fields':['document'],'forbidden':{},
                'body_evidence':{'sources':{'F1':FACT,'P1':PLAN},'facts':['F1'],'plans':['P1']}}]})
        suite={'schema':'jarvis.work-trials.v2','origin':'synthetic','provenance':'Unit fixture, not independent task evidence','cases':cases}
        output=self.root/'trial';result=work_trials.run_suite(suite,output,self.catalog,work_trials.bounded_route(self.catalog,'openai'),lambda *_:Client(),execution='stub',basis_inputs=inputs,document_format=FORMAT)
        self.assertTrue(result['all_candidate_conditions_passed']);self.assertEqual(result,work_trials.summarize(output))
        path=next((output/'turns').glob('*.result.json'));row=json.loads(path.read_text(encoding='utf-8'))
        row['delivery_review']['rendering']['original_reply_digest']='0'*64;row['record_digest']=digest({k:v for k,v in row.items() if k!='record_digest'})
        path.write_text(canonical(row),encoding='utf-8')
        with self.assertRaises(CoreError):work_trials.summarize(output)
