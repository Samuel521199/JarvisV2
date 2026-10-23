import copy
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host.core import Core
from host import memory, development
from host.dialogue import DialogueHost
from host.settings_operations import command as operation
from modules.context_knowledge.memory import Memory
from modules.dialogue.store import Dialogues
from modules.workspace.store import Workspace
from modules.preferences.store import Preferences
from sdk.protocol import CoreError, canonical, decode
from test_preferences_dialogue import fixture
from test_development import specification, plan, candidate


def fact(key='称呼', value='青鸟', **extra):
    return dict(scope='personal', key=key, value=value, kind='preference', purpose='personal', providers=['openai'], paused=False, expires=None, **extra)


class MemoryUI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-memory-ui-'); self.root = Path(self.temp.name)
        self.core = Core.initialize(self.root); self.memory = Memory(self.core.db)
        prefs = Preferences(self.root); prefs.install(fixture(), {}); prefs.close()
        self.chats = Dialogues(self.root)

    def tearDown(self): self.chats.close(); self.core.close(); self.temp.cleanup()

    def save(self, value, revision=0, candidate=None):
        return memory.command(self.root, {'action': 'save', 'item': value, 'revision': revision, 'candidate': candidate})

    def turn(self, chat, ident, text='你好'):
        self.chats.begin(dict(chat_id=chat,request_id=ident,text=text,provider='openai',model='test-model',reasoning='default'), [])

    def test_domains_destinations_pause_expiry_and_bounded_context(self):
        self.save(fact())
        self.save({**fact('表达'), 'purpose': 'style', 'value': '先给结论'})
        self.memory.save({**fact('项目资料'), 'scope': 'project-A', 'purpose': 'project', 'value': '项目 A 的秘密'}, 0)
        self.memory.save({**fact('项目资料'), 'scope': 'project-B', 'purpose': 'project', 'value': '项目 B 的秘密'}, 0)
        self.assertEqual(len(self.memory.view('personal', 'openai')['facts']), 2)
        project = canonical(self.memory.view('project-A', 'openai'))
        self.assertIn('先给结论', project); self.assertIn('项目 A', project)
        self.assertNotIn('青鸟', project); self.assertNotIn('项目 B', project)
        self.assertEqual(self.memory.view('project-A', 'bailian')['facts'], [])
        self.assertEqual(self.memory.view('personal', 'openai', False)['facts'], [])
        self.save({**fact(), 'paused': True}, 1)
        self.assertNotIn('青鸟', canonical(self.memory.view('personal', 'openai')))
        self.save({**fact(), 'expires': time.time()+10}, 2)
        with patch('modules.context_knowledge.memory.time.time', return_value=time.time()+20):
            self.assertNotIn('青鸟', canonical(self.memory.view('personal', 'openai')))
        for i in range(25): self.save(fact('p'+str(i), 'x'*350))
        view = self.memory.view('personal', 'openai')
        self.assertLessEqual(len(view['facts']), 12); self.assertLess(len(canonical(view).encode()), 5300)

    def test_candidate_approval_is_explicit_and_forget_blocks_source_resurrection(self):
        chat = self.chats.create(); self.turn(chat, 'source', '以后称呼我青鸟')
        proposal = memory.command(self.root, {'action': 'propose', 'turn_id': 'source'})
        self.assertEqual(self.memory.view('personal', 'openai')['facts'], [])
        self.save(fact(), candidate={'id': proposal['id'], 'revision': 1})
        self.assertEqual(len(self.memory.view('personal', 'openai')['facts']), 1)
        memory.command(self.root, {'action': 'forget', 'scope': 'personal', 'key': '称呼', 'revision': 1})
        duplicate = memory.command(self.root, {'action': 'propose', 'turn_id': 'source'})
        self.assertEqual(duplicate['state'], 'WITHDRAWN')
        self.assertEqual(self.memory.candidates('personal'), [])
        self.assertNotIn('青鸟', canonical(self.core.db.all('SELECT * FROM facts')))
        self.assertNotIn('青鸟', canonical(self.core.db.all('SELECT * FROM memory_candidates')))

    def test_stale_edit_removed_source_and_cross_project_fail_closed(self):
        self.save(fact())
        with self.assertRaises(CoreError): self.save(fact(value='错的覆盖'), 0)
        self.assertEqual(self.memory.list('personal')[0]['value'], '青鸟')
        with self.assertRaises(CoreError): self.save({**fact(), 'scope': 'project-missing', 'purpose': 'project'})
        chat=self.chats.create(); self.turn(chat,'source','候选来源'); p=memory.command(self.root,{'action':'propose','turn_id':'source'})
        self.chats.update(chat, {'removed':True})
        with self.assertRaises(CoreError): self.save(fact('新标题'),candidate={'id':p['id'],'revision':1})

    def test_correction_forget_disabled_and_destination_change_exclude_old_history(self):
        chat = self.chats.create(); self.save(fact()); self.turn(chat, 'old')
        view = memory.dialogue_view(self.root, self.chats.read(chat), {'id':'openai'}, True)
        self.chats.context('old', view); self.chats.finish('old', {'status':'SUCCEEDED','text':'你好青鸟','provider':'openai'})
        self.save(fact(value='银杏'), 1); self.turn(chat, 'corrected')
        view = memory.dialogue_view(self.root, self.chats.read(chat), {'id':'openai'}, True)
        content = canonical(self.chats.context('corrected', view))
        self.assertIn('银杏',content); self.assertNotIn('青鸟',content)
        self.chats.finish('corrected', {'status':'SUCCEEDED','text':'你好银杏','provider':'openai'})
        self.turn(chat,'other')
        view=memory.dialogue_view(self.root,self.chats.read(chat),{'id':'bailian'},True)
        self.assertNotIn('银杏',canonical(self.chats.context('other',view)))
        view=memory.dialogue_view(self.root,self.chats.read(chat),{'id':'openai'},False)
        self.assertNotIn('银杏',canonical(self.chats.context('other',view)))

    def test_expired_fact_is_not_resurrected_by_historical_reply(self):
        self.save({**fact(), 'expires':time.time()+10}); chat=self.chats.create(); self.turn(chat,'one')
        self.chats.context('one',memory.dialogue_view(self.root,self.chats.read(chat),{'id':'openai'},True))
        self.chats.finish('one',{'status':'SUCCEEDED','text':'青鸟','provider':'openai'}); self.turn(chat,'two')
        with patch('modules.context_knowledge.memory.time.time',return_value=time.time()+20):
            view=memory.dialogue_view(self.root,self.chats.read(chat),{'id':'openai'},True)
        self.assertNotIn('青鸟',canonical(self.chats.context('two',view)))

    def test_inflight_memory_change_discards_old_response(self):
        self.save(fact()); host=DialogueHost(self.root); started=threading.Event(); proceed=threading.Event()
        class Client:
            def __init__(self,*_): pass
            def available(self): return True
            def complete(self,messages,checkpoint):
                started.set(); proceed.wait(3); checkpoint()
                return {'status':'SUCCEEDED','text':'青鸟'}
        try:
            with patch('host.dialogue.NativeModel', Client):
                ident='change'; host.submit(dict(chat_id=self.chats.create(),request_id=ident,text='你好',provider='openai',model='test-model',reasoning='default'))
                self.assertTrue(started.wait(2)); self.save(fact(value='银杏'),1); proceed.set()
                for _ in range(100):
                    if self.chats.turn(ident)['status'] not in {'READY','RUNNING'}: break
                    time.sleep(.02)
                self.assertEqual(self.chats.turn(ident)['error'],'memory_changed'); self.assertIsNone(self.chats.turn(ident)['reply'])
        finally: proceed.set(); host.close()

    def test_fallback_does_not_send_primary_only_memory_to_backup(self):
        self.save(fact()); host=DialogueHost(self.root); sent=[]
        class Client:
            def __init__(self,config,*_): self.config=config
            def available(self): return True
            def complete(self,messages,checkpoint):
                checkpoint(); sent.append((self.config['id'],canonical(messages)))
                return {'status':'REJECTED','code':'http_429'} if self.config['id']=='openai' else {'status':'SUCCEEDED','text':'普通回答'}
        try:
            with patch('host.dialogue.NativeModel',Client):
                host.submit(dict(chat_id=self.chats.create(),request_id='fallback',text='你好',provider='auto',model='',reasoning='default'))
                for _ in range(100):
                    if self.chats.turn('fallback')['status'] not in {'READY','RUNNING'}: break
                    time.sleep(.02)
            self.assertEqual(self.chats.turn('fallback')['status'],'SUCCEEDED')
            self.assertEqual([r[0] for r in sent],['openai','bailian']); self.assertIn('青鸟',sent[0][1]); self.assertNotIn('青鸟',sent[1][1])
        finally: host.close()


class DevelopmentUI(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jarvis-dev-ui-'); self.root=Path(self.temp.name)
        self.core=Core.initialize(self.root); prefs=Preferences(self.root); prefs.install(fixture(),{}); prefs.close()
        self.request={'action':'create','spec':specification(),'routes':{'plan':[{'provider':'openai','model':'test-model','reasoning':'low'}], 'code':[{'provider':'bailian','model':'test-backup','reasoning':'off'}]}}
        self.request['spec'].pop('grant_id'); self.request['spec']['limits']['max_seconds']=1800

    def tearDown(self): self.core.close(); self.temp.cleanup()

    def test_submission_is_idempotent_bounded_and_has_no_automatic_execution(self):
        result=development.command(self.root,self.request); again=development.command(self.root,self.request)
        self.assertEqual(result['id'],again['id']); self.assertTrue(again['existing'])
        detail=development.command(self.root,{'action':'detail','id':result['id']})
        self.assertEqual(detail['run']['status'],'READY'); self.assertEqual(detail['grant']['spent'],0)
        self.assertEqual(detail['routes']['plan'][0]['parameters']['reasoning_effort'],'low')
        self.assertFalse(detail['routes']['code'][0]['parameters']['enable_thinking'])
        self.assertNotIn('credential_id',canonical(detail)); self.assertIsNone(detail['approved_package'])
        changed=copy.deepcopy(self.request); changed['spec']['goal']='different'
        with self.assertRaises(CoreError): development.command(self.root,changed)
        development.command(self.root,{'action':'revoke','id':result['id']})
        self.assertTrue(development.command(self.root,{'action':'detail','id':result['id']})['grant']['revoked'])

    def test_explicit_rejected_retry_keeps_budget_and_unknown_is_not_reset(self):
        shutil.copytree(ROOT/'user-data/worker-runtime',self.root/'worker-runtime')
        ident=development.command(self.root,self.request)['id']
        class Client:
            def __init__(self,config,*_):self.config=config
            def available(self):return True
            def generate(self,prompt,checkpoint):return {'status':'REJECTED','code':'codex_config'}
        with patch('host.core.NativeModel',Client):self.core.develop(ident,True)
        before=development.command(self.root,{'action':'detail','id':ident})
        result=development.command(self.root,{'action':'retry_rejected','id':ident})
        after=development.command(self.root,{'action':'detail','id':ident})
        self.assertEqual(result['acknowledged'],1);self.assertEqual(before['grant']['spent'],after['grant']['spent'])
        self.assertEqual(len(before['calls']),len(after['calls']));self.assertEqual(after['calls'][0]['status'],'ACKNOWLEDGED')
        with self.assertRaises(CoreError):development.command(self.root,{'action':'retry_rejected','id':ident})
        self.core.db.connection.execute("UPDATE model_calls SET status='UNKNOWN' WHERE run_id=?",(ident,))
        with self.assertRaises(CoreError):development.command(self.root,{'action':'retry_rejected','id':ident})
        self.assertEqual(self.core.db.one('SELECT status FROM model_calls WHERE run_id=?',(ident,))['status'],'UNKNOWN')

    def test_exact_candidate_review_then_real_worker_delivery_and_run_again(self):
        shutil.copytree(ROOT/'user-data/worker-runtime',self.root/'worker-runtime')
        ident=development.command(self.root,self.request)['id']; calls=[]
        class Client:
            def __init__(self,config,*_): self.config=config
            def available(self): return True
            def generate(self,prompt,checkpoint):
                checkpoint(); calls.append((self.config['id'],prompt)); value=plan() if self.config['id']=='openai' else candidate()
                return {'status':'SUCCEEDED','value':value,'usage':{'total_tokens':10}}
        with patch('host.core.NativeModel',Client):
            result=self.core.develop(ident,True)
            self.assertEqual(result['error'],'review_required'); self.assertEqual(result['phase'],'verified')
            self.assertIsNone(self.core.packages.slot('plugin.upper.v1'))
            self.assertEqual([x[0] for x in calls],['openai','bailian']); self.assertNotIn('HÉLLO',canonical(calls))
            with self.assertRaises(CoreError): operation(self.root,{'action':'release','id':result['release_id'],'operation':'activate','revision':0})
            with self.assertRaises(CoreError): development.command(self.root,{'action':'approve','id':ident,'package_id':'wrong'})
            development.command(self.root,{'action':'approve','id':ident,'package_id':result['release_id']})
            result=self.core.develop(ident,True)
            self.assertEqual(result['status'],'SUCCEEDED',result)
            actions=self.core.tasks.actions(result['task_id']); self.assertEqual(decode(actions[0]['result'])['text'],'JARVIS')
            self.assertEqual(self.core.develop(ident,True)['task_id'],result['task_id']); self.assertEqual(len(calls),2)

    def test_scope_and_malformed_route_cannot_create_broad_permission(self):
        self.request['spec']['scope_id']='family'
        with self.assertRaises(CoreError): development.command(self.root,self.request)
        self.request['spec']['scope_id']='personal'; self.request['routes']['plan'][0]['url']='https://evil.test'
        with self.assertRaises(CoreError): development.command(self.root,self.request)
        self.assertEqual(len(self.core.db.all('SELECT id FROM grants')),1)


if __name__=='__main__': unittest.main()
