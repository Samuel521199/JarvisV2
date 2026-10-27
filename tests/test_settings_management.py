from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from test_preferences_dialogue import fixture
from test_core import task
from host.core import Core
from host.settings_operations import command, TaskRunner
from modules.preferences.store import Preferences, resolve
from modules.preferences.management import manage
from modules.registry_composer.extensions import Extensions
from modules.dialogue.store import Dialogues
from control.credentials import Credentials
from control.network import NetworkGate
from adapters.models.native import NativeModel
from adapters.models.native_transport import extract
from sdk.protocol import CoreError, canonical
from sdk.pricing import estimate

RATE={'currency':'USD','input':2,'output':8,'cache_read':.2,'cache_write':3,'fee_percent':10,'checked_at':'2026-10-16','source':'test fixture','max_input_tokens':100000}


class SettingsManagementCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='jarvis-settings-v5-');self.root=Path(self.tmp.name);Core.initialize(self.root).close();self.prefs=Preferences(self.root);self.prefs.install(fixture(),{});self.vault=Credentials(self.root)
    def tearDown(self):self.prefs.close();self.tmp.cleanup()
    def model(self,**patches):return {'action':'model','revision':self.prefs.read()['revision'],'connection':'openai','model':'test-model','label':'Test model','enabled':True,'default':True,'parameters':{'reasoning_effort':'medium','max_output_tokens':512},'reasoning_levels':['low','medium','high'],'price':deepcopy(RATE),**patches}

    def test_prices_public_and_revisioned_without_secrets(self):
        cmd=self.model();manage(self.prefs,cmd);public=self.prefs.public();self.assertEqual(next(p for p in public['connections'] if p['id']=='openai')['models'][0]['price'],RATE)
        with self.assertRaises(CoreError):manage(self.prefs,cmd)
        self.assertNotIn('credential_id',canonical(public));self.assertNotIn('api_key',canonical(public))

    def test_invalid_prices_and_reasoning_do_not_commit(self):
        original=self.prefs.read()
        for price in [{**RATE,'input':-1},{**RATE,'input':True},{**RATE,'currency':'???'},{**RATE,'checked_at':'bad'},{**RATE,'valid_until':'2025-01-01'}]:
            with self.assertRaises(CoreError):manage(self.prefs,self.model(price=price))
            self.assertEqual(self.prefs.read(),original)
        with self.assertRaises(CoreError):manage(self.prefs,self.model(reasoning_levels=['low']))
        self.assertEqual(self.prefs.read(),original)

    def test_route_order_model_levels_persist_atomically(self):
        manage(self.prefs,{'action':'routing','revision':1,'enabled':True,'routes':[{'connection':'bailian','model':'test-backup','reasoning':'off'},{'connection':'openai','model':'test-model','reasoning':'high'}]})
        c=self.prefs.read()['catalog'];self.assertEqual(c['fallback_order'],['bailian','openai']);self.assertFalse(resolve(c)['parameters']['enable_thinking']);self.assertEqual(resolve(c,'openai')['parameters']['reasoning_effort'],'high')

    def test_add_and_replace_key_keeps_dpapi_and_binding(self):
        def add(old=''):
            manage(self.prefs,{'action':'add_key','revision':self.prefs.read()['revision'],'connection':'openai','label':'test','secret':'fixture-key-only','replace_key':old},self.vault)
            return self.prefs.read()['catalog']['providers']['openai']['credential_id']
        first=add();second=add(first);self.assertNotEqual(first,second)
        self.assertEqual(self.vault.get('openai',second)['api_key'],'fixture-key-only')
        with self.assertRaises(CoreError):self.vault.get('bailian',second)
        self.assertNotIn(b'fixture-key-only',self.vault.path.read_bytes());self.assertNotIn('fixture-key-only',canonical(self.prefs.public()))
        self.assertFalse(self.prefs.read()['catalog']['providers']['openai']['keys'][first]['enabled'])

    def test_vault_failure_keeps_configuration(self):
        before=self.prefs.read()
        with patch.object(self.vault,'put',side_effect=OSError('test')):
            with self.assertRaises(OSError):manage(self.prefs,{'action':'add_key','revision':1,'connection':'openai','label':'test','secret':'fixture-key-only','replace_key':''},self.vault)
        self.assertEqual(self.prefs.read(),before)

    def test_price_cache_reasoning_and_unknown_accounting(self):
        profile={'adapter':'vertex','price':RATE}
        usage={'prompt_tokens':1000,'completion_tokens':200,'reasoning_tokens':100,'reasoning_in_completion':False,'cache_read_tokens':200,'total_tokens':1300}
        result=estimate(profile,usage,time.time());self.assertAlmostEqual(result['amount'],.004444)
        self.assertIsNone(estimate(None,usage,time.time())['amount'])
        self.assertEqual(estimate(profile,{**usage,'total_tokens':2000},time.time())['reason'],'unreconciled_usage')
        for p,reason in [({**RATE,'cache_read':None},'missing_token_rate'),({**RATE,'valid_until':'2026-10-17'},'price_expired'),({**RATE,'max_input_tokens':500},'outside_price_tier')]:self.assertEqual(estimate({'adapter':'vertex','price':p},usage,1792627200)['reason'],reason)

    def test_attempt_price_frozen_across_edits(self):
        manage(self.prefs,self.model());route=resolve(self.prefs.read()['catalog']);store=Dialogues(self.root)
        try:
            chat=store.create();cmd={'chat_id':chat,'request_id':'price-test','text':'hello','provider':'auto','model':'','reasoning':'default'}
            store.begin(cmd,[route]);attempt=store.start_attempt(cmd['request_id'],route)
            manage(self.prefs,self.model(price={**RATE,'input':99}))
            raw=store.db.execute('SELECT billing_profile FROM attempts WHERE id=?',(attempt,)).fetchone()[0]
            self.assertIn('"input":2',raw);self.assertNotIn('"input":99',raw)
        finally:store.close()

    def test_network_blocks_before_process_and_other_core_tasks_work(self):
        gate=NetworkGate(self.root);gate.update({'revision':0,'blocked':True})
        with self.assertRaises(CoreError):gate.update({'revision':0,'blocked':False})
        client=NativeModel(resolve(fixture()),lambda *_:{'api_key':'test'},self.root/'temp')
        with patch('adapters.models.native.subprocess.Popen') as spawn:
            self.assertEqual(client.complete([{'role':'user','content':'test'}])['code'],'network_disabled');spawn.assert_not_called()
        core=Core(self.root)
        try:
            ident=core.tasks.submit(task('offline-local'));core.run();self.assertEqual(core.tasks.get(ident)['status'],'SUCCEEDED')
        finally:core.close()
        gate.update({'revision':1,'blocked':False});gate.require_online()

    def test_core_schema_v2_upgrade_is_additive(self):
        db=sqlite3.connect(self.root/'state/core.sqlite3');db.execute('ALTER TABLE model_calls DROP COLUMN billing_profile');db.execute('ALTER TABLE model_calls DROP COLUMN model');db.execute('DROP TABLE assistant_operations');db.execute('DROP TABLE chat_goals');db.execute('DROP TABLE goal_context');db.execute('ALTER TABLE goal_plans DROP COLUMN generation');db.execute('DROP TABLE goal_growth');db.execute('DROP TABLE goal_plans');db.execute('DROP TABLE memory_usage');db.execute('DROP TABLE memory_candidates');db.execute('DROP TABLE development_controls');db.execute("DELETE FROM meta WHERE key='memory_epoch'");db.execute('PRAGMA user_version=2');db.commit();db.close()
        core=Core(self.root)
        try:self.assertEqual(core.db.one('PRAGMA user_version')['user_version'],7);self.assertEqual(core.identity.describe()['owner_id'],'owner.local')
        finally:core.close()

    def test_module_commands_use_revision_and_do_not_create_grants(self):
        core=Core(self.root);m=next(m for m in core.status()['modules'] if m['id']=='text-analyzer');core.close()
        cmd={'action':'module_change','id':m['id'],'revision':m['revision'],'operation':'stop','implementation':None}
        result=command(self.root,cmd);self.assertFalse(result['enabled'])
        with self.assertRaises(CoreError):command(self.root,cmd)
        command(self.root,{**cmd,'revision':result['revision'],'operation':'start'})
        with self.assertRaises(CoreError):command(self.root,{'action':'grant_add','id':'x'})

    def test_release_commands_cannot_run_unknown_operation_or_invent_package(self):
        for operation in ['shell','activate','rollback','retire','disable','probe']:
            with self.assertRaises(CoreError):command(self.root,{'action':'release','id':'missing','revision':0,'operation':operation})

    def test_web_submission_does_not_bypass_task_grants(self):
        result=command(self.root,{'action':'task_submit','task':task('ui-submit')})
        self.assertIn('task_id',result)
        unauthorized=task('ui-denied');unauthorized['grant_id']='unavailable'
        with self.assertRaises(CoreError):command(self.root,{'action':'task_submit','task':unauthorized})

    def test_bounded_task_runner_and_cancel(self):
        core=Core(self.root);first=core.tasks.submit(task('cancel'));second=core.tasks.submit(task('run'));core.close()
        command(self.root,{'action':'task_cancel','id':first});runner=TaskRunner(self.root)
        try:
            with self.assertRaises(CoreError):runner.start({'max_tasks':100})
            runner.start({'max_tasks':1});runner.close();self.assertEqual(runner.state()['status'],'finished')
            self.assertEqual(command(self.root,{'action':'task_detail','id':second})['task']['status'],'SUCCEEDED')
            self.assertEqual(command(self.root,{'action':'task_detail','id':first})['task']['status'],'CANCELLED')
        finally:runner.close()

    def test_extension_skill_inspection_change_and_cas(self):
        store=Extensions(self.root)
        try:
            folder=self.root.parent/(self.root.name+'-skill');folder.mkdir();file=folder/'SKILL.md';file.write_text('# fixture\nDo not execute this.',encoding='utf-8')
            try:
                ident=store.command({'action':'save','id':'','revision':0,'kind':'skill','name':'test','config':{'path':str(folder)}})['id']
                inspect={'action':'inspect','id':ident,'revision':1};self.assertFalse(store.command(inspect)['changed']);file.write_text('changed',encoding='utf-8');self.assertTrue(store.command(inspect)['changed'])
                with self.assertRaises(CoreError):store.command({**inspect,'revision':0})
                store.command({'action':'remove','id':ident,'revision':1});self.assertTrue(file.exists());self.assertFalse(store.list())
            finally:file.unlink();folder.rmdir()
        finally:store.close()

    def test_mcp_registration_does_not_start_anything_and_rejects_url_secrets(self):
        store=Extensions(self.root)
        try:
            cfg={'transport':'streamable-http','url':'https://example.test/mcp','command':'','args':[],'credential_ref':'test-ref'}
            with patch('subprocess.Popen') as spawn:
                store.command({'action':'save','id':'','revision':0,'name':'test','kind':'mcp','config':cfg});spawn.assert_not_called()
            self.assertEqual(store.list()[0]['runtime'],'not_connected')
            for url in ['http://example.test/mcp','https://name:secret@example.test/mcp','https://example.test/mcp?key=x']:
                with self.assertRaises(CoreError):store.validate('mcp',{**cfg,'url':url})
        finally:store.close()

    def test_vendor_reasoning_and_cache_usage_are_not_double_counted(self):
        r=extract('vertex',{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'ok'}]}}],'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':2,'thoughtsTokenCount':4,'cachedContentTokenCount':3,'totalTokenCount':16}})
        self.assertEqual(r['usage']['reasoning_tokens'],4);self.assertFalse(r['usage']['reasoning_in_completion']);self.assertEqual(r['usage']['cache_read_tokens'],3)
