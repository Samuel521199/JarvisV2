import http.client
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from apps.workbench.server import Handler
from control.family_identity import FamilyIdentity
from host.core import Core
from host.family import FamilyHost
from modules.context_knowledge.private_memory import PrivateMemory
from modules.preferences.store import Preferences
from sdk.protocol import CoreError, canonical, decode

PASSWORD = 'synthetic-only-password-2026'


@unittest.skipUnless(os.name == 'nt', 'Real Windows DPAPI is required')
class FamilyPrivacyCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-family-test-')
        self.root = Path(self.temp.name)
        Core.initialize(self.root).close()
        prefs = Preferences(self.root)
        prefs.install({'schema_version': 1, 'default_provider': 'openai', 'automatic_fallback': False, 'fallback_order': ['openai'],
                       'providers': {'openai': {'adapter': 'openai', 'label': 'Synthetic only', 'model': 'test-model',
                                              'models': {'test-model': {'parameters': {}, 'reasoning_levels': []}}}}}, {})
        prefs.close()
        self.host = FamilyHost(self.root)
        self.token = self.host.identity.setup(PASSWORD)
        self.owner = self.host.identity.principal(self.token)
        for ident in ('alice', 'bob'):
            self.host.identity.manage(self.owner, {'id': ident, 'name': ident, 'active': True, 'password': PASSWORD})
        self.at = self.host.identity.login('alice', PASSWORD)
        self.bt = self.host.identity.login('bob', PASSWORD)
        self.alice = self.host.identity.principal(self.at)
        self.bob = self.host.identity.principal(self.bt)
        self.memory = PrivateMemory(self.root)

    def tearDown(self):
        self.host.close(); self.memory.close(); self.temp.cleanup()

    def note(self, actor=None, **patches):
        value = {'id': '', 'revision': 0, 'title': '私密记忆', 'text': '加密正文-secret-marker-测试', 'shared': [], 'providers': []}
        value.update(patches)
        return self.memory.save(actor or self.alice, value, self.host.identity.members())

    def change(self, row, actor=None, **patches):
        value = {k: row[k] for k in ('id', 'revision', 'title', 'text', 'shared', 'providers')}
        return self.memory.save(actor or self.alice, value | patches, self.host.identity.members())

    def send(self, chat, **patches):
        value = {'action': 'chat_send', 'id': chat['id'], 'text': '测试消息', 'notes': [], 'provider': 'openai', 'model': 'test-model', 'request_id': 'request-test'} | patches
        return self.host.command(self.alice, self.at, value)

    def wait(self, ident, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            row = self.memory.read(self.alice, ident)
            if row['turns'] and row['turns'][-1]['status'] != 'RUNNING': return row
            time.sleep(.01)
        self.fail('Private response did not reach a terminal state')

    def test_owner_and_member_acl_no_exist_leak_and_readonly_sharing(self):
        row = self.note()
        self.assertEqual(self.memory.read(self.owner, row['id'])['owner'], 'alice')
        for ident in (row['id'], 'private-'+'0'*32):
            with self.assertRaises(CoreError) as error: self.memory.read(self.bob, ident)
            self.assertEqual(error.exception.code, 'family_missing')
        self.assertEqual(self.memory.list(self.bob), [])
        row = self.change(row, shared=['bob'])
        self.assertEqual(self.memory.read(self.bob, row['id'])['text'], row['text'])
        with self.assertRaises(CoreError): self.change(row, self.bob, text='not allowed')
        row = self.change(row, self.owner, text='owner corrected')
        self.assertEqual(row['owner'], 'alice')
        self.change(row, shared=[])
        self.assertEqual(self.memory.list(self.bob), [])

    def test_ciphertext_db_journal_identity_no_plaintext_and_restart(self):
        row = self.note()
        for path in (self.root/'private').glob('*'):
            raw = path.read_bytes()
            for marker in ('secret-marker', '加密正文', PASSWORD, '私密记忆'):
                self.assertNotIn(marker.encode(), raw)
        fresh = FamilyIdentity(self.root)
        self.assertTrue(fresh.enabled)
        self.assertIsNone(fresh.principal(self.at))
        self.assertEqual(fresh.principal(fresh.login('alice', PASSWORD))['id'], 'alice')
        second = PrivateMemory(self.root)
        try: self.assertEqual(second.read(self.owner, row['id'])['text'], row['text'])
        finally: second.close()

    def test_password_reset_disable_logout_and_expiry(self):
        with self.assertRaises(CoreError): self.host.identity.manage(self.alice, {'id':'eve','name':'eve','active':True,'password':PASSWORD})
        self.host.identity.manage(self.owner, {'id':'alice','name':'alice','active':False,'password':''})
        self.assertIsNone(self.host.identity.principal(self.at))
        with self.assertRaises(CoreError): self.host.identity.login('alice',PASSWORD)
        self.host.identity.change_password(self.bob, PASSWORD, PASSWORD+'-new')
        self.assertIsNone(self.host.identity.principal(self.bt))
        with self.assertRaises(CoreError): self.host.identity.login('bob', PASSWORD)
        token=self.host.identity.login('bob',PASSWORD+'-new')
        self.host.identity.sessions[token]['expires']=0
        self.assertIsNone(self.host.identity.principal(token))
        self.host.identity.logout(self.token);self.assertIsNone(self.host.identity.principal(self.token))

    def test_login_rate_limit_and_corrupt_state_fail_closed(self):
        self.host.identity.attempts=[time.monotonic()]*10
        with self.assertRaises(CoreError) as error:self.host.identity.login('alice',PASSWORD)
        self.assertEqual(error.exception.code,'family_rate')
        self.host.identity.path.write_bytes(b'invalid envelope')
        with self.assertRaises(CoreError):FamilyIdentity(self.root)

    def test_cas_tombstone_and_cipher_swap_detection(self):
        row=self.note();new=self.change(row,text='new')
        with self.assertRaises(CoreError):self.change(row,text='stale')
        self.memory.forget(self.owner,row['id'],new['revision'])
        with self.assertRaises(CoreError):self.change(new,text='resurrection')
        a=self.note();b=self.note(title='other')
        db=self.memory.store.db
        with self.memory.store.transaction():db.execute('UPDATE objects SET payload=(SELECT payload FROM objects WHERE id=?) WHERE id=?',(a['id'],b['id']))
        with self.assertRaises(CoreError) as error:self.memory.read(self.owner,b['id'])
        self.assertEqual(error.exception.code,'family_corrupt')

    def test_provider_opt_in_and_untrusted_identity_fields(self):
        row=self.note(shared=['bob'])
        with self.assertRaises(CoreError):self.memory.context(self.bob,[row['id']],'openai')
        row=self.change(row,providers=['openai'])
        self.assertEqual(len(self.memory.context(self.bob,[row['id']],'openai')),1)
        with self.assertRaises(CoreError):self.host.command(self.bob,self.bt,{'action':'read','id':row['id'],'owner':'owner'})
        with self.assertRaises(CoreError):self.memory.context(self.owner,[{'id':row['id']}],'openai')

    def test_chat_encrypted_context_and_idempotence_recall_revoke(self):
        row=self.note(providers=['openai']);chat=self.memory.create_chat(self.alice,'私聊')
        captured=[]
        def complete(_,messages,checkpoint):
            checkpoint();captured.append(messages);return {'status':'SUCCEEDED','text':'参考了私密内容','usage':{'input_tokens':10}}
        with patch('host.family.NativeModel.complete',complete):
            self.send(chat,notes=[row['id']]);result=self.wait(chat['id'])
            self.assertEqual(result['turns'][0]['status'],'SUCCEEDED')
            self.assertTrue(self.send(chat,notes=[row['id']])['existing'])
            self.assertEqual(len(captured),1)
            self.assertIn(row['text'],canonical(captured))
            self.send(chat,request_id='followup');self.wait(chat['id'])
        with self.assertRaises(CoreError):self.memory.read(self.bob,chat['id'])
        self.assertEqual(self.memory.read(self.owner,chat['id'])['owner'],'alice')
        self.change(row,providers=[])
        updated=self.memory.read(self.alice,chat['id'])
        self.assertEqual([x['status'] for x in updated['turns']],['WITHDRAWN','WITHDRAWN'])
        self.assertTrue(all(not x['reply'] and not x['text'] for x in updated['turns']))
        for path in (self.root/'private').glob('*'):
            self.assertNotIn('参考了私密内容'.encode(),path.read_bytes())

    def test_running_chat_revoke_and_member_revoke_block_late_result(self):
        row=self.note(providers=['openai']);chat=self.memory.create_chat(self.alice,'running')
        entered=threading.Event();release=threading.Event()
        def slow(_,messages,checkpoint):
            entered.set();release.wait(4);checkpoint();return {'status':'SUCCEEDED','text':'late secret'}
        with patch('host.family.NativeModel.complete',slow):
            self.send(chat,notes=[row['id']]);self.assertTrue(entered.wait(2))
            started=time.monotonic();self.memory.list(self.owner);self.assertLess(time.monotonic()-started,1)
            self.change(row,providers=[]);release.set();result=self.wait(chat['id'])
            self.assertEqual(result['turns'][0]['status'],'WITHDRAWN')
        chat=self.memory.create_chat(self.alice,'member revoke');entered.clear();release.clear()
        with patch('host.family.NativeModel.complete',slow):
            self.send(chat,request_id='second');self.assertTrue(entered.wait(2))
            self.host.identity.manage(self.owner,{'id':'alice','name':'alice','active':False,'password':''})
            release.set();result=self.wait(chat['id'])
            self.assertEqual(result['turns'][0]['status'],'UNKNOWN');self.assertEqual(result['turns'][0]['reply'],'')

    def test_recovery_marks_unknown_and_does_not_replay(self):
        chat=self.memory.create_chat(self.alice,'interrupted')
        with self.memory.store.transaction():
            chat['turns']=[{'id':'crash','status':'RUNNING','text':'pending','reply':''}];self.memory.store.put(chat,chat['revision'])
        other=FamilyHost(self.root)
        try:self.assertEqual(self.memory.read(self.alice,chat['id'])['turns'][0]['status'],'UNKNOWN')
        finally:other.close()

    def test_two_private_chats_capacity_cancel_and_forget_during_flight(self):
        chats=[self.memory.create_chat(self.alice,'parallel '+str(i)) for i in range(3)]
        entered=threading.Event();release=threading.Event();count=[]
        def slow(_,messages,checkpoint):
            count.append(True)
            if len(count)==2:entered.set()
            release.wait(4);checkpoint();return {'status':'SUCCEEDED','text':'late'}
        with patch('host.family.NativeModel.complete',slow):
            self.send(chats[0]);self.send(chats[1])
            self.assertTrue(entered.wait(2));self.assertEqual(len(self.host.active),2)
            with self.assertRaises(CoreError) as error:self.send(chats[2])
            self.assertEqual(error.exception.code,'chat_capacity')
            self.host.command(self.alice,self.at,{'action':'chat_cancel','id':chats[0]['id'],'request_id':'request-test'})
            current=self.memory.read(self.alice,chats[1]['id']);self.memory.forget(self.alice,current['id'],current['revision'])
            release.set();self.assertEqual(self.wait(chats[0]['id'])['turns'][0]['status'],'CANCELLED')
            deadline=time.monotonic()+2
            while self.host.active and time.monotonic()<deadline:time.sleep(.01)
            self.assertFalse(self.host.active)
            with self.assertRaises(CoreError):self.memory.read(self.owner,chats[1]['id'])

    def test_owner_setup_is_opt_in_with_password_validation(self):
        with tempfile.TemporaryDirectory(prefix='jarvis-family-optin-') as root:
            Core.initialize(root).close()
            service=FamilyHost(root)
            try:
                self.assertFalse(service.identity.enabled)
                self.assertFalse((Path(root)/'private/family-identity.dpapi').exists())
                with self.assertRaises(CoreError):service.identity.setup('too short')
                self.assertFalse(service.identity.enabled)
                token=service.identity.setup(PASSWORD)
                self.assertEqual(service.identity.principal(token)['role'],'owner')
                with self.assertRaises(CoreError):service.identity.setup(PASSWORD)
            finally:service.close()

    def test_http_every_legacy_route_is_owner_only_and_csrf_remains(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='synthetic-nonce';server.family=self.host
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        cookie='jarvis_family_'+str(server.server_port)+'='
        origin='http://127.0.0.1:'+str(server.server_port)
        def request(method,path,value=None,token='',cross=False):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers={'Origin':'http://attacker.invalid' if cross else origin,'Content-Type':'application/json','X-Jarvis-Token':server.nonce}
            if token:headers['Cookie']=cookie+token
            connection.request(method,path,None if value is None else canonical(value),headers)
            response=connection.getresponse();raw=response.read();result=(response.status,raw,dict(response.getheaders()));connection.close();return result
        try:
            self.assertEqual(request('GET','/api/session')[0],401)
            self.assertEqual(request('GET','/')[0],302)
            self.assertEqual(request('GET','/',token=self.at)[2]['Location'],'/family')
            self.assertEqual(request('GET','/api/session',token=self.at)[0],200)
            self.assertEqual(decode(request('GET','/api/session',token=self.at)[1])['data_root'],'')
            paths=['/api/snapshot','/api/chats','/api/projects','/api/usage','/api/resources','/api/health','/api/studio3d/files/fake/model.glb','/api/anatomy/artifacts/fake','/api/local-models','/api/network','/api/tools','/api/developments','/api/extensions','/api/image-studio','/api/image-studio/jobs','/api/image-studio/files/fake/image.png','/api/image-studio/billing']
            paths.append('/api/mail')
            for path in paths:self.assertEqual(request('GET',path,token=self.at)[0],403,path)
            self.assertEqual(request('POST','/api/mail',{'action':'detail','id':'private-mail-job'},self.at)[0],403)
            for path in ['/api/chat/send','/api/knowledge','/api/memory','/api/memory-transfer','/api/tools/run','/api/settings','/api/family/setup','/api/network','/api/project/write','/api/assistant/action','/api/image-studio/jobs','/api/image-studio/cancel','/api/image-studio/references','/api/image-studio/reference','/api/image-studio/settings','/api/image-studio/preview','/api/image-studio/annotation']:
                self.assertEqual(request('POST',path,{},self.at)[0],403,path)
            self.assertEqual(request('POST','/api/family',{'action':'members'},self.at,cross=True)[0],403)
            login=request('POST','/api/family/login',{'id':'alice','password':PASSWORD})
            self.assertEqual(login[0],200);self.assertIn('HttpOnly',login[2]['Set-Cookie']);self.assertIn('SameSite=Strict',login[2]['Set-Cookie'])
            self.assertNotIn(PASSWORD,login[1].decode())
            self.assertEqual(request('GET','/api/projects',token=self.token)[0],200)
            self.assertEqual(request('POST','/api/family',{'action':'members'},self.at)[0],200)
            from apps.workbench.launch import running
            self.assertTrue(running(server.server_port,self.root.resolve()))
        finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
