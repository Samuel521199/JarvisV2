import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host.core import Core
from host.local_models import LocalModels
from modules.local_models.catalog import builtin
from modules.local_models.assessments import assess, identity, merge_sample, profiles
from test_local_models import FakeWorker


class AssessmentCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-model-assess-')
        self.root = Path(self.temp.name); Core.initialize(self.root).close()
        self.runtime = patch('host.local_models.runtime_status', return_value={'ready': True})
        self.runtime.start(); self.addCleanup(self.runtime.stop)
        self.m = LocalModels(self.root, worker_factory=FakeWorker)

    def tearDown(self):
        self.m.close(); self.temp.cleanup()

    def command(self, action, **kw):
        self.m.command({'action': action, 'revision': self.m.snapshot()['revision'], **kw})
        return self.m.future.result(timeout=10)

    def fixture(self):
        item = copy.deepcopy(builtin()[0]); item['id'] = 'measurement-test'
        folder = self.m.folder(item['id']); folder.mkdir()
        for f in item['files']:
            data = f['name'].encode(); f.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            (folder/f['name']).write_bytes(data)
        self.command('register', manifest=item)
        return item

    def row(self, ident):
        return next(x for x in self.m.snapshot()['models'] if x['id'] == ident)

    def test_all_catalog_models_have_scoped_forecasts_without_fake_speed(self):
        for m in self.m.snapshot()['models']:
            a = m['assessment']
            self.assertGreater(a['expected']['disk']['low'], 0)
            self.assertGreater(a['expected']['ram']['low'], 0)
            self.assertEqual(a['expected']['vram']['high'], 0)
            self.assertIn('CPU', a['profile'])
            self.assertIsNone(a['scores']['speed']); self.assertIsNone(a['scores']['retrieval'])

    def test_calibration_survives_standby_restart_and_uninstall(self):
        item = self.fixture(); ident = item['id']
        self.assertEqual(self.command('start', id=ident)['status'], 'succeeded')
        before = self.row(ident)['assessment']
        self.assertTrue(before['calibrated']); self.assertEqual(before['scores']['validation'], 2)
        self.command('standby', id=ident); self.m.close()
        self.m = LocalModels(self.root, worker_factory=FakeWorker)
        self.assertEqual(self.row(ident)['memory']['rss_bytes'], 0)
        self.assertEqual(self.row(ident)['assessment']['expected'], before['expected'])
        self.command('uninstall', id=ident)
        self.assertEqual(self.row(ident)['disk_bytes'], 0)
        self.assertEqual(self.row(ident)['assessment']['expected'], before['expected'])

    def test_damaged_and_partial_files_do_not_calibrate(self):
        item = self.fixture(); folder = self.m.folder(item['id'])
        (folder/'model.onnx').write_bytes(b'bad')
        self.assertEqual(self.command('verify', id=item['id'])['status'], 'failed')
        a = self.row(item['id'])['assessment']
        self.assertFalse(a['disk_measurement']); self.assertFalse(a['calibrated'])

    def test_new_context_and_new_manifest_do_not_reuse_old_measurements(self):
        item = self.fixture(); self.command('start', id=item['id'])
        self.m.measurement_context = {**self.m.measurement_context, 'id': 'other-runtime'}
        a = self.row(item['id'])['assessment']
        self.assertFalse(a['calibrated']); self.assertEqual(a['other_contexts'], 1)
        original = builtin()[0]; changed = {**original, 'revision': 'f'*40}
        self.assertNotEqual(identity(changed), identity(original))
        self.assertIsNone(assess(changed, {}, {'id': 'x'}, profiles())['languages_count'])

    def test_missing_zero_and_invalid_memory_never_erase_measurements(self):
        a = merge_sample({}, {'rss_bytes': 1024, 'peak_rss_bytes': 2048}, {'batch': 4, 'max_tokens': 32})
        for rss in (None, 0, -1, float('nan')):
            self.assertEqual(merge_sample(a, {'rss_bytes': rss}), a)
        b = merge_sample(a, {'rss_bytes': 512}, {'batch': 1, 'max_tokens': 8})
        self.assertEqual(b['peak_rss_bytes'], 2048); self.assertEqual(b['batch_observed_max'], 4)

    def test_benchmark_keeps_bad_results_persistent_and_restores_standby(self):
        item = self.fixture(); result = self.command('benchmark', id=item['id'])
        self.assertEqual(result['status'], 'succeeded'); self.assertIsNone(self.m.loaded)
        a = self.row(item['id'])['assessment']; b = a['benchmark']
        self.assertEqual(b['sample_count'], 20)
        self.assertEqual(b['hit_at_1'], .1)  # Identical fake vectors: only the two tea queries rank first.
        self.assertEqual(a['scores']['validation'], 3)
        self.assertEqual(a['scores']['retrieval'], 10)
        self.m.close(); self.m = LocalModels(self.root, worker_factory=FakeWorker)
        self.assertEqual(self.row(item['id'])['assessment']['benchmark'], b)
        self.assertNotIn('vectors', json.dumps(self.m.snapshot()))

    def test_benchmark_cancellation_unloads_and_never_marks_completed(self):
        item = self.fixture()
        def cancelled(request, check):
            self.m.cancel.set(); check()
        with patch('host.local_models.run_benchmark', side_effect=cancelled):
            result = self.command('benchmark', id=item['id'])
        self.assertEqual(result['status'], 'cancelled'); self.assertIsNone(self.m.loaded)
        self.assertIsNone(self.row(item['id'])['assessment']['benchmark'])

    def test_schema_one_migrates_without_losing_defaults(self):
        item = self.fixture(); self.command('activate', id=item['id']); self.m.close()
        with closing(sqlite3.connect(self.root/'config/local-models.sqlite3')) as db:
            with db:
                db.execute('DROP TABLE observations'); db.execute('PRAGMA user_version=1')
        self.m = LocalModels(self.root, worker_factory=FakeWorker)
        self.assertEqual(self.m.snapshot()['selected'], item['id']); self.assertIsNone(self.m.loaded)
        with self.m.db() as db: self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)

    def test_suite_change_marks_old_result_stale_without_deleting_it(self):
        item = self.fixture(); self.command('benchmark', id=item['id'])
        before = self.row(item['id'])['assessment']['benchmark']
        from modules.local_models import assessments
        real_read = assessments.read_json
        def changed(path):
            data = real_read(path)
            return {**data, 'id': 'new-suite'} if path.name == 'retrieval-suite.json' else data
        with patch.object(assessments, 'read_json', side_effect=changed):
            a = self.row(item['id'])['assessment']
            self.assertTrue(a['stale_benchmark']); self.assertIsNone(a['scores']['speed'])
            self.assertIsNone(a['scores']['retrieval']); self.assertEqual(a['measured']['benchmark'], before)

    def test_benchmark_preserves_default_and_rejects_active_other_model(self):
        item = self.fixture(); self.command('activate', id=item['id'])
        self.assertEqual(self.command('benchmark', id='e5-multilingual-small-fp32')['error'], 'model_in_use')
        self.assertEqual(self.m.loaded, item['id'])
        self.command('benchmark', id=item['id'])
        self.assertEqual(self.m.loaded, item['id']); self.assertEqual(self.m.snapshot()['selected'], item['id'])


if __name__ == '__main__': unittest.main()
