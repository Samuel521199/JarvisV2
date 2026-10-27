import hashlib
import http.client
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps.workbench.server import Handler
from host.core import Core
from host import workbench
from modules.workspace.store import Workspace
from modules.skills.catalog import Skills
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences
from sdk.protocol import CoreError, canonical, decode


class WorkspaceSkillsCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-workbench-test-')
        self.base = Path(self.temp.name); self.root = self.base / 'runtime'; self.folder = self.base / 'project'
        self.folder.mkdir(); Core.initialize(self.root).close(); self.ws = Workspace(self.root)
        self.project = self.ws.open(str(self.folder)); self.ident = self.project['id']

    def tearDown(self): self.ws.close(); self.temp.cleanup()

    def test_project_metadata_remove_restore_preserves_files(self):
        file = self.folder / 'notes.md'; file.write_text('keep', encoding='utf-8')
        self.ws.update(self.ident, {'name': 'My project', 'description': 'Notes', 'section': 'Work', 'pinned': True, 'removed': True})
        with self.assertRaises(CoreError): self.ws.read(self.ident, 'notes.md')
        self.assertEqual(file.read_text(), 'keep')
        reopened = self.ws.open(str(self.folder)); self.assertEqual(reopened['id'], self.ident)
        self.assertEqual(reopened['name'], 'My project'); self.assertEqual(reopened['pinned'], 1)

    def test_compare_and_swap_rejects_stale_or_missing_file(self):
        first = self.ws.write(self.ident, 'notes.md', 'one', None)
        self.assertEqual(first['revision'], hashlib.sha256(b'one').hexdigest())
        (self.folder / 'notes.md').write_text('external', encoding='utf-8')
        with self.assertRaises(CoreError) as error: self.ws.write(self.ident, 'notes.md', 'overwrite', first['revision'])
        self.assertEqual(error.exception.code, 'conflict'); self.assertEqual((self.folder / 'notes.md').read_text(), 'external')
        with self.assertRaises(CoreError): self.ws.write(self.ident, 'new.md', 'text', first['revision'])
        self.assertFalse((self.folder / 'new.md').exists())
        self.assertFalse(list(self.folder.glob('.jarvis-write-*')))

    def test_traversal_runtime_and_sensitive_paths_rejected(self):
        for path in ['../escape.md', '../runtime/state/core.sqlite3', '/absolute.md', 'file:stream.md', '.env', 'private_key.json', 'nested/credentials.json', '.git/config']:
            with self.subTest(path=path), self.assertRaises(CoreError): self.ws.path(self.ident, path)
        with self.assertRaises(CoreError): self.ws.open(str(self.root))
        with self.assertRaises(CoreError): self.ws.open(str(self.folder.anchor))
        with self.assertRaises(CoreError): self.ws.open('relative')

    def test_own_source_is_readable_but_write_requires_release(self):
        project = self.ws.open(str(ROOT))
        self.assertTrue(self.ws.read(project['id'], 'README.md')['text'])
        with self.assertRaises(CoreError) as error: self.ws.path(project['id'], 'README.md', write=True)
        self.assertEqual(error.exception.code, 'self_write_requires_release')

    def test_reparse_points_cannot_be_followed(self):
        # A link creation privilege is not required to test the runtime's lstat contract.
        import stat
        original = Path.lstat
        class LinkInfo:
            st_mode = stat.S_IFDIR
            st_file_attributes = 0x400
        def linked(path, *args, **kwargs):
            if path.name == 'linked': return LinkInfo()
            return original(path, *args, **kwargs)
        with patch.object(Path, 'lstat', linked), self.assertRaises(CoreError): self.ws.path(self.ident, 'linked/file.md')

    def test_text_boundaries_and_bounded_tree(self):
        (self.folder / 'binary.md').write_bytes(b'a\x00b')
        (self.folder / 'huge.md').write_bytes(b'a' * 262145)
        (self.folder / 'program.exe').write_bytes(b'not run')
        for file in ['binary.md', 'huge.md', 'program.exe']:
            with self.subTest(file=file), self.assertRaises(CoreError): self.ws.read(self.ident, file)
        for i in range(405): (self.folder / (str(i)+'.txt')).touch()
        listing = self.ws.tree(self.ident)
        self.assertEqual(len(listing['entries']), 400); self.assertTrue(listing['truncated'])

    def test_file_creation_does_not_execute_and_export_has_no_commands(self):
        self.ws.mkdir(self.ident, 'scripts')
        text = "raise RuntimeError('must never execute')"
        saved = self.ws.write(self.ident, 'scripts/example.py', text, None)
        self.assertEqual(saved['text'], text)
        exported = decode(self.ws.export(self.ident)['text'])
        self.assertEqual(exported['folders'][0]['path'], str(self.folder)); self.assertNotIn('commands', exported)

    def test_old_chat_schema_upgrade_retains_content(self):
        path = self.root / 'state/dialogue.sqlite3'
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE chats(id TEXT PRIMARY KEY,title TEXT,created REAL,updated REAL)')
            db.execute("INSERT INTO chats VALUES('chat-old','Existing title',1,1)")
            db.commit()
        store = Dialogues(self.root)
        try:
            self.assertEqual(store.read('chat-old')['title'], 'Existing title')
            self.assertEqual(store.read('chat-old')['project_id'], '')
            created = store.create(self.ident); self.assertEqual(store.read(created)['project_id'], self.ident)
        finally: store.close()

    def test_project_chat_archiving_does_not_affect_other_scope(self):
        store = Dialogues(self.root)
        try:
            a = store.create(self.ident); b = store.create()
            workbench.command(self.root, '/api/project/archive', {'id': self.ident, 'archived': True})
            self.assertEqual(store.read(a)['archived'], 1); self.assertEqual(store.read(b)['archived'], 0)
            store.update(a, {'archived': False, 'pinned': True, 'title': 'Project chat'})
            self.assertEqual(store.read(a)['title'], 'Project chat')
        finally: store.close()

    def test_skill_disable_pending_and_matching(self):
        skills = Skills(self.root)
        try:
            self.assertIsNone(skills.select('auto', '你好，今天天气怎么样'))
            self.assertEqual(skills.select('auto', '请做代码审阅')['id'], 'review')
            skills.enable('review', False)
            self.assertIsNone(skills.select('auto', '代码审阅'))
            self.assertEqual(skills.select('gmail','配置 Gmail')['id'],'gmail')
            skills.enable('gmail',False)
            for value in ['review', 'gmail', 'unknown']:
                with self.subTest(value=value), self.assertRaises(CoreError): skills.select(value, 'text')
            with self.assertRaises(CoreError): skills.select('auto', None)
        finally: skills.close()

    def test_skill_and_attachments_frozen_in_request_only(self):
        store = Dialogues(self.root); skills = Skills(self.root)
        try:
            chat = store.create(self.ident)
            request = {'chat_id': chat, 'request_id': 'test-message', 'text': '代码审阅', 'provider': 'auto', 'model': '', 'reasoning': 'default', 'skill': 'review', 'requirements': '简短', 'attachments': [{'name': 'sample.py', 'text': 'print(1)'}]}
            guidance = skills.select('review', request['text']); self.assertTrue(store.begin(request, [], guidance))
            skills.enable('review', False)
            context = store.context(request['request_id']); self.assertIn('本轮文字技能：代码审阅', context[-1]['content'])
            self.assertIn('print(1)', context[-1]['content']); self.assertIn('简短', context[-1]['content'])
            self.assertEqual(context[-1]['role'], 'user')
            self.assertFalse(store.begin(request, [], None))
            other = store.create(); request2 = {**request, 'chat_id': other, 'request_id': 'other', 'attachments': [], 'requirements': '', 'skill': 'none', 'text': 'hello'}
            store.begin(request2, []); self.assertNotIn('print(1)', canonical(store.context('other')))
        finally: skills.close(); store.close()

    def test_http_editor_requires_origin_nonce_and_exact_command(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); server.data_root = self.root; server.nonce = 'test-nonce'
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        origin = 'http://127.0.0.1:' + str(server.server_port)
        def send(value, headers):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            conn.request('POST', '/api/project/write', canonical(value).encode(), {'Content-Type': 'application/json', **headers})
            response = conn.getresponse(); data = response.read(); conn.close(); return response.status, decode(data)
        value = {'id': self.ident, 'path': 'test.md', 'text': 'safe', 'revision': None}
        try:
            self.assertEqual(send(value, {'Origin': origin})[0], 403)
            self.assertEqual(send(value, {'Origin': 'https://other.test', 'X-Jarvis-Token': 'test-nonce'})[0], 403)
            headers = {'Origin': origin, 'X-Jarvis-Token': 'test-nonce'}
            self.assertEqual(send({**value, 'execute': True}, headers)[0], 400)
            self.assertEqual(send(value, headers)[0], 200)
            self.assertEqual(send(value, headers)[0], 409)
        finally: server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_appearance_policy_survives_reopen(self):
        store = Preferences(self.root)
        try: store.save_ui({'theme': 'forest', 'motion_off': True, 'sound': False})
        finally: store.close()
        store = Preferences(self.root)
        try:
            self.assertEqual(store.ui()['theme'], 'forest')
            with self.assertRaises(CoreError): store.save_ui({'theme': 'bad'})
        finally: store.close()


if __name__ == '__main__': unittest.main()
