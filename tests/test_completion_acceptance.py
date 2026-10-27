"""Independent output oracles and real process death, on disposable data only."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_core as base
from host.core import Core
from host.completion import command, refresh
from modules.task_resource.scheduling import Scheduling
from sdk.protocol import decode

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / 'tests/fixtures/completion_acceptance_v1.json').read_text('utf-8'))['cases']


class CompletionAcceptance(unittest.TestCase):
    setUp = base.CoreCase.setUp
    tearDown = base.CoreCase.tearDown

    def source(self):
        ident = self.core.tasks.submit(base.task('source', artifact=True))
        self.core.run_task(ident)
        return ident

    def compare_report(self, ident, expected):
        self.assertEqual(self.core.tasks.get(ident)['status'], 'SUCCEEDED')
        actions = self.core.tasks.actions(ident)
        self.assertEqual(len(actions), 2)
        self.assertTrue(all(a['status'] == 'CONFIRMED' for a in actions))
        self.assertEqual(decode(actions[0]['result']), expected)
        receipt = decode(actions[1]['result'])
        self.assertEqual(json.loads((self.root / receipt['relative_path']).read_text('utf-8')), expected)
        self.assertEqual(refresh(self.core, ident)['state'], 'SATISFIED')

    def crash(self, source, mode):
        payload = {
            'fixture_root': str(self.root),
            'feedback': {'action': 'completion_feedback', 'id': source, 'request_id': 'crash-feedback',
                         'fingerprint': refresh(self.core, source)['fingerprint'], 'kind': 'reject', 'note': 'synthetic counterexample'},
            'reuse': {'action': 'experience_reuse', 'id': source, 'request_id': 'crash-adoption', 'text': 'fresh input'}
        }
        (self.root / 'acceptance-crash-fixture.json').write_text(json.dumps(payload), encoding='utf-8')
        self.core.close()
        try:
            result = subprocess.run([sys.executable, '-m', 'tools.completion_crash_worker', str(self.root), mode],
                                    cwd=ROOT, capture_output=True, text=True, timeout=20,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        finally:
            self.core = Core(self.root)
        self.assertEqual(result.returncode, 91 if mode.endswith('before') else 92, result.stderr)
        self.assertEqual(self.core.db.one('PRAGMA integrity_check'), {'integrity_check': 'ok'})
        return payload

    def test_feedback_crash_before_commit_rolls_back_the_whole_change(self):
        source = self.source()
        before = self.core.tasks.actions(source)
        self.crash(source, 'feedback-before')
        self.assertEqual(self.core.db.all('SELECT * FROM completion_feedback'), [])
        self.assertTrue(refresh(self.core, source)['method_available'])
        self.assertEqual(self.core.tasks.actions(source), before)

    def test_feedback_crash_after_commit_blocks_adoption_after_restart(self):
        source = self.source()
        child = command(self.core, {'action': 'experience_reuse', 'id': source, 'request_id': 'queued', 'text': 'new'})['task_id']
        payload = self.crash(source, 'feedback-after')
        self.assertEqual(len(self.core.db.all('SELECT * FROM completion_feedback')), 1)
        self.assertFalse(refresh(self.core, source)['method_available'])
        self.assertEqual(self.core.run_task(child)['error'], 'experience_changed')
        self.assertEqual(self.core.tasks.actions(child), [])
        command(self.core, payload['feedback'])
        self.assertEqual(len(self.core.db.all('SELECT * FROM completion_feedback')), 1)

    def test_reuse_crash_before_commit_has_no_orphan_task_or_queue(self):
        source = self.source()
        self.crash(source, 'reuse-before')
        self.assertEqual(self.core.db.one('SELECT COUNT(*) AS n FROM tasks')['n'], 1)
        self.assertEqual(self.core.db.all('SELECT * FROM experience_uses'), [])
        self.assertEqual(Scheduling(self.core.db).pending(), [])

    def test_reuse_lost_response_after_commit_retries_without_duplicate_effect(self):
        source = self.source()
        payload = self.crash(source, 'reuse-after')
        self.assertEqual(self.core.db.one('SELECT COUNT(*) AS n FROM tasks')['n'], 2)
        result = command(self.core, payload['reuse'])
        self.assertTrue(result['existing'])
        ident = result['task_id']
        self.assertEqual([r['task_id'] for r in Scheduling(self.core.db).pending()], [ident])
        self.core.run_task(ident)
        actions = self.core.tasks.actions(ident)
        self.assertEqual(len(actions), 2)
        self.assertEqual(command(self.core, payload['reuse'])['task_id'], ident)
        self.core.run_task(ident)
        self.assertEqual(self.core.tasks.actions(ident), actions)


def oracle_case(case):
    def check(self):
        source = self.source()
        body = base.task('direct-' + case['id'], artifact=True)
        body['steps'][0]['arguments']['text'] = case['text']
        direct = self.core.tasks.submit(body)
        reused = command(self.core, {'action': 'experience_reuse', 'id': source,
                                   'request_id': case['id'], 'text': case['text']})['task_id']
        for ident in (direct, reused):
            self.core.run_task(ident)
            self.compare_report(ident, case['expected'])
        self.assertEqual(self.core.db.all('SELECT * FROM model_calls'), [])
    return check


for case in CASES:
    setattr(CompletionAcceptance, 'test_independent_output_' + case['id'], oracle_case(case))


if __name__ == '__main__':
    unittest.main()
