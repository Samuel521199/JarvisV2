import base64
from contextlib import closing
import sqlite3
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from control.credentials import Credentials, crypt, load_envelope
from control.atomic import write_json
from host.core import Core
from host.dialogue import DialogueHost
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences, resolve, validate_catalog
from sdk.protocol import CoreError, canonical, decode
from adapters.models.native import NativeModel
from adapters.models.native_transport import request, extract, vertex_token
from adapters.models.windows_signing import sign_rs256
from apps.migrate_settings import migrate


def fixture():
    return {'schema_version': 1, 'default_provider': 'openai', 'automatic_fallback': True,
            'fallback_order': ['openai', 'bailian'], 'max_output_tokens': 512, 'max_prompt_bytes': 50000,
            'providers': {
                'openai': {'adapter': 'openai', 'label': 'Test OpenAI', 'model': 'test-model',
                    'models': {'test-model': {'parameters': {'reasoning_effort': 'medium'}, 'reasoning_levels': ['low','medium','high']}}},
                'bailian': {'adapter': 'bailian', 'region': 'beijing', 'model': 'test-backup',
                    'models': {'test-backup': {'parameters': {'enable_thinking': True}, 'reasoning_levels': ['off','on']}}}}}


class PreferenceDialogueCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='jarvis-settings-'); self.root = Path(self.tmp.name)
        Core.initialize(self.root).close(); self.prefs = Preferences(self.root)
        self.prefs.install(fixture(), {'model':'test-coder','reasoning':'medium','enabled':True,'revision':1})

    def tearDown(self): self.prefs.close(); self.tmp.cleanup()

    def command(self, **changes):
        return {'revision': 1, 'provider': 'bailian', 'model': 'test-backup', 'reasoning':'off',
                'automatic_fallback': True, 'fallback_order':['bailian','openai'], **changes}

    def test_default_selection_reasoning_and_ui_survive_restart(self):
        self.prefs.update(self.command()); self.prefs.save_ui({'nav_width':280,'panel_width':420,'motion_off':True,'page':'chat'})
        other = Preferences(self.root)
        try:
            selected = resolve(other.read()['catalog'])
            self.assertEqual(selected['id'],'bailian'); self.assertFalse(selected['parameters']['enable_thinking'])
            self.assertEqual(other.ui()['panel_width'],420)
        finally: other.close()
        core=Core(self.root)
        try: self.assertEqual(core.routed_models.order,['bailian','openai'])
        finally: core.close()

    def test_stale_revision_and_invalid_reasoning_do_not_change_config(self):
        original=self.prefs.read()
        for cmd in [self.command(revision=0),self.command(reasoning='high'),self.command(fallback_order=['unknown']),self.command(automatic_fallback='yes')]:
            with self.assertRaises(CoreError): self.prefs.update(cmd)
            self.assertEqual(self.prefs.read(),original)

    def test_unrecognized_parameters_and_plaintext_endpoint_rejected(self):
        config=fixture();config['providers']['openai']['models']['test-model']['parameters']['api_key']='never'
        with self.assertRaises(CoreError):validate_catalog(config)
        config=fixture();config['providers']['openai'].update(adapter='compatible',base_url='http://untrusted.test')
        with self.assertRaises(CoreError):validate_catalog(config)

    def test_dpapi_roundtrip_and_public_settings_never_expose_secrets(self):
        vault=Credentials(self.root);vault.save({'openai':{'api_key':'sentinel-test-key'}})
        self.assertEqual(vault.get('openai')['api_key'],'sentinel-test-key')
        self.assertNotIn(b'sentinel-test-key',vault.path.read_bytes())
        public=self.prefs.public(vault.available)
        self.assertNotIn('sentinel-test-key',canonical(public))
        self.assertTrue(next(p for p in public['connections'] if p['id']=='openai')['credential_available'])
        self.assertEqual(public['coding']['adapter_state'],'not_implemented')

    def test_credential_binding_rejects_cross_provider_and_wrong_envelope(self):
        vault=Credentials(self.root);vault.save({'_managed':{'one':{'connection':'openai','credential':{'api_key':'sentinel'}}}})
        with self.assertRaises(CoreError):vault.get('bailian','one')
        write_json(vault.path,{'schema_version':2,'format':'plaintext','payload':'bad'})
        with self.assertRaises(CoreError):load_envelope(vault.path)
        self.assertEqual(decode(vault.path.read_bytes())['schema_version'],2)

    def test_cng_rejects_non_pkcs8_key_without_persistence(self):
        with self.assertRaises(ValueError):sign_rs256('not-a-key',b'test')

    def test_provider_wire_formats_and_reasoning(self):
        config=fixture(); route=resolve(config,'openai',reasoning='high')
        url,headers,body=request(route,{'api_key':'test-key'},[{'role':'user','content':'JSON'}],True)
        self.assertTrue(url.endswith('/responses'));self.assertFalse(body['store']);self.assertEqual(body['reasoning']['effort'],'high')
        self.assertEqual(body['text']['format']['type'],'json_object')
        route=resolve(config,'bailian',reasoning='off')
        url,headers,body=request(route,{'api_key':'test-key'},[{'role':'user','content':'JSON'}],True)
        self.assertFalse(body['enable_thinking']);self.assertEqual(body['response_format']['type'],'json_object')
        route.update(adapter='gemini',model='test-gemini',parameters={'thinking_level':'MEDIUM'})
        url,headers,body=request(route,{'api_key':'test-key'},[{'role':'assistant','content':'hello'},{'role':'user','content':'JSON'}],True)
        self.assertEqual(body['contents'][0]['role'],'model');self.assertEqual(body['generationConfig']['responseMimeType'],'application/json')
        self.assertNotIn('test-key',url)

    def test_incomplete_function_call_and_refusal_are_not_answers(self):
        self.assertEqual(extract('openai',{'status':'incomplete','output':[]})['status'],'INVALID')
        self.assertEqual(extract('vertex',{'candidates':[{'finishReason':'STOP','content':{'parts':[{'functionCall':{'name':'danger'}}]}}]})['status'],'INVALID')
        self.assertEqual(extract('openai',{'status':'completed','output':[{'type':'message','content':[{'type':'refusal'}]}]})['status'],'INVALID')
        reply=extract('openai',{'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'ok'}]}],'usage':{'total_tokens':True,'input_tokens':5}})
        self.assertEqual(reply['usage'],{'prompt_tokens':5});self.assertEqual(reply['text'],'ok')

    def test_auth_metadata_cannot_redirect_private_key_or_token(self):
        with patch('adapters.models.native_transport.post') as post:
            with self.assertRaises(ValueError):vertex_token({'type':'service_account','token_uri':'https://attacker.test'})
            post.assert_not_called()

    def test_conversations_idempotence_and_recovery_do_not_repeat_call(self):
        store=Dialogues(self.root)
        try:
            chat=store.create();cmd={'chat_id':chat,'request_id':'request-one','text':'hello','provider':'auto','model':'','reasoning':'default'}
            routes=[resolve(fixture())]
            self.assertTrue(store.begin(cmd,routes));self.assertFalse(store.begin(cmd,routes))
            with self.assertRaises(CoreError):store.begin({**cmd,'text':'different'},routes)
            store.context('request-one');attempt=store.start_attempt('request-one',routes[0]);store.recover()
            self.assertEqual(store.turn('request-one')['status'],'UNKNOWN');self.assertFalse(store.begin(cmd,routes))
            self.assertEqual(store.db.execute('SELECT status FROM attempts WHERE id=?',(attempt,)).fetchone()[0],'UNKNOWN')
        finally:store.close()

    def test_history_contains_only_successful_turns_and_is_bounded(self):
        store=Dialogues(self.root)
        try:
            chat=store.create()
            for i in range(8):
                cmd={'chat_id':chat,'request_id':str(i),'text':'A'*10000,'provider':'auto','model':'','reasoning':'default'}
                store.begin(cmd,[resolve(fixture())]);store.finish(str(i),{'status':'SUCCEEDED','text':'B'*10000})
            cmd={**cmd,'request_id':'latest','text':'now'};store.begin(cmd,[resolve(fixture())]);context=store.context('latest')
            self.assertLessEqual(len(canonical(context).encode()),50000);self.assertEqual(context[-1]['content'],'now')
            self.assertEqual(len(store.read(chat)['turns']),9)
        finally:store.close()

    def _wait(self,host,store,ident):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            row=store.turn(ident)
            if row['status'] not in {'READY','RUNNING'}:return row
            time.sleep(.02)
        self.fail('Turn did not finish')

    def test_unknown_response_does_not_fallback_and_other_chat_still_runs(self):
        store=Dialogues(self.root);host=DialogueHost(self.root)
        try:
            def complete(_self,messages,checkpoint,**kwargs):
                if messages[-1]['content']=='unknown':return {'status':'UNKNOWN','code':'model_timeout'}
                return {'status':'SUCCEEDED','text':'ok','usage':{'total_tokens':1}}
            with patch.object(NativeModel,'available',return_value=True),patch.object(NativeModel,'complete',complete):
                for text in ['unknown','hello']:
                    chat=store.create();host.submit({'chat_id':chat,'request_id':text,'text':text,'provider':'auto','model':'','reasoning':'default'})
                    row=self._wait(host,store,text)
                    self.assertEqual(row['status'],'UNKNOWN' if text=='unknown' else 'SUCCEEDED')
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM attempts WHERE turn_id=?',('unknown',)).fetchone()[0],1)
        finally:host.close();store.close()

    def test_explicit_model_never_silently_switches_provider(self):
        store=Dialogues(self.root);host=DialogueHost(self.root)
        try:
            with patch.object(NativeModel,'available',return_value=True),patch.object(NativeModel,'complete',return_value={'status':'REJECTED','code':'http_403'}) as call:
                cmd={'chat_id':store.create(),'request_id':'manual','text':'test','provider':'openai','model':'test-model','reasoning':'low'}
                host.submit(cmd);self.assertEqual(self._wait(host,store,'manual')['status'],'FAILED');self.assertEqual(call.call_count,1)
        finally:host.close();store.close()

    def test_only_one_dialogue_host_can_recover_a_data_root(self):
        host=DialogueHost(self.root)
        try:
            with self.assertRaises(CoreError):DialogueHost(self.root)
        finally:host.close()

    def test_cancellation_stops_transport_and_leaves_other_chat_available(self):
        store=Dialogues(self.root);host=DialogueHost(self.root)
        try:
            def complete(_self,messages,checkpoint,**kwargs):
                while True: checkpoint();time.sleep(.01)
            with patch.object(NativeModel,'available',return_value=True),patch.object(NativeModel,'complete',complete):
                host.submit({'chat_id':store.create(),'request_id':'cancel','text':'test','provider':'auto','model':'','reasoning':'default'})
                store.cancel('cancel');row=self._wait(host,store,'cancel');self.assertEqual(row['status'],'CANCELLED')
            self.assertEqual(store.db.execute("SELECT COUNT(*) FROM turns WHERE status='RUNNING'").fetchone()[0],0)
        finally:host.close();store.close()

    def test_native_credentials_only_enter_http_child_stdin(self):
        class Process:
            returncode=0
            payload=None
            def communicate(self,payload=None,**kwargs):
                if payload:self.payload=payload
                return canonical({'status':'SUCCEEDED','text':'ok','usage':{}}).encode(),b''
            def poll(self):return 0
        process=Process();client=NativeModel(resolve(fixture()),lambda *_:{'api_key':'secret-sentinel'},self.root/'temp')
        with patch('subprocess.Popen',return_value=process) as start:
            self.assertEqual(client.complete([{'role':'user','content':'test'}])['text'],'ok')
        self.assertNotIn('secret-sentinel',str(start.call_args))
        self.assertIn(b'secret-sentinel',process.payload)
        self.assertEqual(list((self.root/'temp').iterdir()),[])

    def test_migration_uses_effective_database_and_preserves_destination_edits(self):
        source = self.root/'legacy'; destination = self.root/'new'
        (source/'user-data/data').mkdir(parents=True); (source/'user-data/private').mkdir()
        (source/'config/model-profiles').mkdir(parents=True); destination.mkdir()
        # A stale seed must not replace the owner's effective database selection.
        write_json(source/'config/model-profiles/providers.json', {'schema_version': 999})
        catalog = fixture(); catalog['providers']['openai']['credential_id'] = 'key-test'
        with closing(sqlite3.connect(source/'user-data/data/model-admin.db')) as db, db:
            db.execute('CREATE TABLE settings(id INTEGER PRIMARY KEY,revision INTEGER,config TEXT)')
            db.execute('INSERT INTO settings VALUES(1,22,?)', (canonical(catalog),))
        credential = {'_managed': {'key-test': {'connection': 'openai', 'credential': {'api_key': 'migration-sentinel'}}}}
        encrypted = {'schema_version': 1, 'format': 'windows-dpapi-current-user',
                     'payload': base64.b64encode(crypt(canonical(credential).encode())).decode()}
        write_json(source/'user-data/private/credentials.dpapi', encrypted)
        report = migrate(source, destination)
        self.assertEqual(report['source_revision'], 22)
        self.assertTrue(report['catalog_equal']); self.assertTrue(report['encrypted_vault_equal'])
        self.assertNotIn('migration-sentinel', canonical(report))
        self.assertEqual(migrate(source, destination), report)
        prefs = Preferences(destination)
        try:
            prefs.update(self.command())
            saved = prefs.read()
            with self.assertRaises(CoreError): migrate(source, destination)
            self.assertEqual(prefs.read(), saved)
        finally: prefs.close()


if __name__=='__main__':unittest.main()
