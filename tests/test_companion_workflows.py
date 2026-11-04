"""Real owner HTTP/read-receipt flows, synthetic records, no model/mail calls."""
from concurrent.futures import Future
from http.server import ThreadingHTTPServer
import http.client
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from apps.workbench.server import Handler
from control.local_access import LocalAccess, cookie_name
from control.runtime_activity import RequestActivity
from host.core import Core
from host.runtime_participants import snapshot as participants
from host.work_status import snapshot, decorate_chat, acknowledge
from modules.continuity.attention import Attention, identity
from modules.dialogue.store import Dialogues
from sdk.protocol import CoreError


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-companion-')
        self.root = Path(self.temp.name)
        Core.initialize(self.root).close()

    def tearDown(self):
        self.temp.cleanup()

    def reply(self, request='synthetic-reply'):
        store = Dialogues(self.root)
        try:
            chat = store.create()
            store.begin({'chat_id': chat, 'request_id': request, 'text': 'synthetic question',
                         'provider': 'fixture', 'model': 'fixture', 'reasoning': 'default'}, [])
            store.finish(request, {'status': 'SUCCEEDED', 'text': 'synthetic answer'})
            return store.read(chat)
        finally: store.close()

    def test_chat_and_work_share_durable_read_receipt_and_version(self):
        chat = self.reply()
        state = snapshot(self.root, SimpleNamespace())
        item = next(i for i in state['items'] if i['source'] == 'dialogue')
        decorated = decorate_chat(self.root, chat)['turns'][0]
        self.assertEqual(item['attention'], decorated['attention'])
        self.assertTrue(item['attention']['unread'])
        result = acknowledge(self.root, SimpleNamespace(), {'action': 'viewed', **{
            k: item['attention'][k] for k in ('key', 'version')}})
        self.assertFalse(result['unread'])
        self.assertFalse(snapshot(self.root, SimpleNamespace())['items'][0]['attention']['unread'])
        # Corrected/withdrawn answer must become unread again; an old ack cannot hide it.
        store = Dialogues(self.root)
        try: store.db.execute("UPDATE turns SET reply='corrected synthetic answer' WHERE id=?", (item['id'],))
        finally: store.close()
        with self.assertRaises(CoreError) as error:
            acknowledge(self.root, SimpleNamespace(), {'action': 'viewed', 'key': item['attention']['key'], 'version': item['attention']['version']})
        self.assertEqual(error.exception.code, 'attention_stale')
        self.assertEqual(snapshot(self.root, SimpleNamespace())['unread_count'], 1)

    def test_read_receipt_cannot_change_actor_or_pending_work(self):
        pending = {'id': 'task', 'source': 'tasks', 'state': 'running'}
        store = Attention(self.root)
        try:
            with self.assertRaises(CoreError): store.acknowledge(pending, identity(pending)[1])
        finally: store.close()
        with self.assertRaises(CoreError):
            acknowledge(self.root, SimpleNamespace(), {'action': 'viewed', 'key': 'x', 'version': 'a'*64, 'actor': 'someone'})

    def test_handoff_waits_for_mail_auth_private_chat_models_and_native_jobs(self):
        from host import studio3d, studio3d_learning, image_generation, knowledge, knowledge_extraction
        future = Future()
        lock = threading.RLock()
        server = SimpleNamespace(mailbox=SimpleNamespace(lock=lock, active=set(), auth={'future':future}),
            family=SimpleNamespace(lock=lock, active={('private', 'request'):future}),
            local_models=SimpleNamespace(lock=lock, future=None, recall_future=future),
            request_activity=RequestActivity())
        key = str(self.root.resolve())
        with patch.dict(studio3d.ACTIVE, {(key, 'render'):object()}), patch.object(studio3d_learning,'ACTIVE',{(key,'learning')}), patch.dict(image_generation.ACTIVE, {(key, 'image'):object()}), patch.dict(knowledge.JOBS, {key:{'state':'running'}}), patch.dict(knowledge_extraction.ACTIVE, {key:future}):
            state = participants(self.root, server)
            self.assertFalse(state['drained'])
            self.assertEqual({r['id'] for r in state['participants'] if r['state']=='busy'},
                {'mailbox','family','local_models','studio3d','studio3d_learning','images','knowledge','knowledge_extraction'})
            # Another data root must not inherit this native work.
            Core.initialize(self.root/'other').close()
            self.assertTrue(participants(self.root/'other', SimpleNamespace())['drained'])
        future.set_result(None);server.family.active.clear()
        self.assertTrue(participants(self.root, server)['drained'])
        with server.request_activity.track(): self.assertFalse(participants(self.root, server)['drained'])
        self.assertTrue(participants(self.root, server)['drained'])

    def test_unknown_participant_blocks_shutdown_without_exposing_content(self):
        broken = SimpleNamespace(state=lambda: (_ for _ in ()).throw(RuntimeError('private data')))
        state = participants(self.root, SimpleNamespace(dialogues=broken))
        self.assertFalse(state['drained']);self.assertNotIn('private data', str(state))

    def test_runtime_drain_endpoint_uses_shared_participants(self):
        from apps.workbench import runtime_http
        from control.application_runtime import publish
        build = 'b'*64
        publish(self.root,build,1,'draining')
        future=Future();answers=[]
        server=SimpleNamespace(data_root=self.root,application_build=build,application_epoch=1,
            mailbox=SimpleNamespace(lock=threading.RLock(),active=set(),auth={'future':future}))
        handler=SimpleNamespace(server=server,json=answers.append)
        with patch.object(runtime_http,'owner_control',return_value=True):
            self.assertTrue(runtime_http.post(handler,'/api/runtime/drain',{'build':build,'epoch':1}))
            self.assertFalse(answers[-1]['drained'])
            future.set_result(None)
            runtime_http.post(handler,'/api/runtime/drain',{'build':build,'epoch':1})
            self.assertTrue(answers[-1]['drained'])

    def test_same_api_owner_access_nonce_and_dedicated_frame_policy(self):
        chat = self.reply()
        server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
        server.data_root = self.root;server.nonce = 'synthetic-nonce';server.request_activity=RequestActivity()
        server.access=LocalAccess(self.root,key='synthetic-key-'+('a'*32))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        token=server.access.unlock('synthetic-key-'+('a'*32));cookie=cookie_name(server.server_port)+'='+token
        def request(path,body=None,headers=None):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            conn.request('POST' if body is not None else 'GET',path,
                body=json.dumps(body) if body is not None else None,
                headers={'Cookie':cookie,'Origin':origin,'Content-Type':'application/json',
                         'X-Jarvis-Token':server.nonce,**(headers or {})})
            response=conn.getresponse();payload=response.read();result=(response.status,dict(response.getheaders()),payload);conn.close();return result
        try:
            page=request('/conversation');self.assertEqual(page[0],200)
            self.assertIn("frame-ancestors 'self'",page[1]['Content-Security-Policy'])
            self.assertEqual(page[2],request('/')[2])
            for path in ('/','/companion','/settings'):
                self.assertIn("frame-ancestors 'none'",request(path)[1]['Content-Security-Policy'])
            self.assertEqual(request('/api/work-status',headers={'Cookie':''})[0],401)
            item=json.loads(request('/api/work-status')[2])['items'][0]
            receipt={'action':'viewed','key':item['attention']['key'],'version':item['attention']['version']}
            self.assertEqual(request('/api/work-status',receipt,{'X-Jarvis-Token':''})[0],403)
            self.assertEqual(request('/api/work-status',receipt,{'Origin':'https://wrong.invalid'})[0],403)
            self.assertEqual(request('/api/work-status',receipt)[0],200)
            self.assertFalse(json.loads(request('/api/chats/'+chat['id'])[2])['turns'][0]['attention']['unread'])
            # Maintenance rejects new work but keeps a narrowly scoped owner stop usable.
            from control.application_runtime import publish
            from test_core import task
            core=Core(self.root)
            try: ident=core.tasks.submit(task('cancel-during-drain'))
            finally: core.close()
            publish(self.root,'c'*64,1,'draining')
            self.assertEqual(request('/api/operations',{'action':'task_resume','id':ident})[0],400)
            self.assertEqual(request('/api/operations',{'action':'task_cancel','id':ident})[0],200)
            self.assertEqual(server.request_activity.count(),0)
        finally:
            server.shutdown();server.server_close();thread.join()
            server.family.close()


if __name__=='__main__': unittest.main()
