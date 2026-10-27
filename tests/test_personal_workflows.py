"""Personal workflows select on requests and retain feedback without dispatching work."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host.core import Core
from host.dialogue import DialogueHost
from modules.dialogue.store import Dialogues
from modules.preferences.store import resolve
from modules.skills.catalog import Skills
from modules.workspace.sessions import Sessions
from sdk.protocol import CoreError, canonical, decode
from test_preferences_dialogue import fixture


class PersonalWorkflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-personal-')
        self.root = Path(self.temp.name)
        self.core = Core.initialize(self.root)
        self.settings = fixture()
        self.core.preferences.install(self.settings, {})
        self.skills = Skills(self.root)

    def tearDown(self):
        self.skills.close()
        self.core.close()
        self.temp.cleanup()

    def test_explicit_requests_select_each_workflow(self):
        for text, ident in [
            ('开始英语练习：每天15分钟', 'english-coach'),
            ('请练习英语。', 'english-coach'),
            ('Please practice English: technical reading', 'english-coach'),
            ('帮我整理学习日志：读了20分钟', 'journal-review'),
            ('日志复盘：渲染完成，贴图没检查', 'journal-review'),
            ('请做代码审阅', 'review'),
        ]:
            with self.subTest(text=text):
                self.assertEqual(self.skills.select('auto', text)['id'], ident)

    def test_mentions_negations_quotes_and_hypotheses_do_not_activate(self):
        for text in ['不要开始英语练习', '“开始英语练习”是什么意思？',
                     '如果开始英语练习会怎样？', '英语学习功能有什么用？',
                     '不要整理学习日志', '他说“日志复盘”，我只想闲聊',
                     '将来可能做工作复盘', '分析报错：Traceback']:
            with self.subTest(text=text):
                picked = self.skills.select('auto', text)
                self.assertNotIn(picked['id'] if picked else None,
                                 {'english-coach', 'journal-review'})

    def test_explicit_selection_none_and_disable_survive_reopen(self):
        self.assertEqual(self.skills.select('english-coach', 'My answer is B')['id'], 'english-coach')
        self.assertIsNone(self.skills.select('none', '开始英语练习'))
        self.skills.enable('english-coach', False)
        self.skills.close()
        self.skills = Skills(self.root)
        self.assertIsNone(self.skills.select('auto', '开始英语练习'))
        with self.assertRaises(CoreError): self.skills.select('english-coach', 'B')

    def test_feedback_context_and_reply_files_survive_reopen_without_goals(self):
        route = resolve(self.settings, 'openai')
        seen = []
        replies = ['填空：The engine ___ every frame. (run/runs)',
                   'runs 正确：单数主语用第三人称单数。下一题：The wheels ___ fast.']

        class Client:
            def __init__(self, *args): pass
            def available(self): return True
            def complete(self, messages, checkpoint, **kwargs):
                checkpoint(); seen.append(messages)
                return {'status': 'SUCCEEDED', 'text': canonical({
                    'schema': 'jarvis.assistant-turn.v1',
                    'reply': replies[len(seen)-1],
                    'action': {'kind': 'chat', 'goal': '', 'input_text': '', 'target': ''}
                }), 'usage': {'input_tokens': 100, 'output_tokens': 50}}

        host = DialogueHost(self.root)
        store = Dialogues(self.root)
        try:
            chat = store.create()
            for n, text in enumerate(['开始英语练习：先给一道题', '我的答案是 runs']):
                ident = 'personal-turn-' + str(n)
                command = {'chat_id': chat, 'request_id': ident, 'text': text,
                           'provider': 'openai', 'model': route['model'], 'reasoning': 'default',
                           'skill': 'english-coach', 'assistant_mode': True, 'memory_enabled': False}
                store.begin(command, [route], self.skills.select('english-coach', text))
                with patch('host.dialogue.NativeModel', Client): host.run(ident)
                self.assertEqual(store.turn(ident)['status'], 'SUCCEEDED')
            self.assertIn(replies[0], canonical(seen[1]))
            self.assertIn('本轮选中对话工作流', seen[1][-1]['content'])
            self.assertIn('仍保留完整请求走 goal', seen[1][-1]['content'])
            self.assertEqual(self.core.db.all('SELECT * FROM goal_plans'), [])
            self.assertEqual(self.core.db.all('SELECT * FROM tasks'), [])
            store.close(); store = Dialogues(self.root)
            turn = store.turn('personal-turn-1')
            self.assertEqual(turn['reply'], replies[1])
            self.assertEqual(decode(turn['guidance'])['version'], '1.0.0')
            folders = Sessions(self.root)
            try:
                self.assertTrue(folders.files(chat)['files'])
                self.assertFalse(folders.info(chat)['delivery_error'])
            finally: folders.close()
        finally:
            store.close(); host.close()


if __name__ == '__main__': unittest.main()
