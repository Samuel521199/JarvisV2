import json
from pathlib import Path
import tempfile
import unittest

from host.application_release import ROOT, validator


class ApplicationCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-release-policy-')
        self.base = Path(self.temp.name).resolve()
        self.package = self.base / 'package'
        self.data = self.base / 'data'
        (self.package / 'apps/workbench').mkdir(parents=True)
        (self.data / 'deployment').mkdir(parents=True)
        for name in ['modules/local_models/runtime.json', 'modules/skills/anatomy/runtime-boundary.json',
                     'modules/skills/studio3d/runtime.json']:
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
        (self.package / 'apps/workbench/server.py').write_text('# synthetic source', encoding='utf-8')

    def tearDown(self):
        self.assertEqual(self.base.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.base.name.startswith('jarvis-release-policy-'))
        self.temp.cleanup()

    def test_unreviewed_source_is_not_executed_even_if_static_gate_passes(self):
        (self.package / 'apps/workbench/server.py').write_text(
            'from pathlib import Path\n(Path(__file__).parents[2]/"executed").write_text("unsafe")\n', encoding='utf-8')
        report = validator(self.data)(self.package)
        self.assertTrue(report['architecture_passed'])
        self.assertFalse(report['passed'])
        self.assertFalse((self.package / 'executed').exists())

    def test_candidates_cannot_supply_their_own_passing_checker(self):
        (self.package / 'tools').mkdir()
        (self.package / 'tools/check_architecture.py').write_text('print("passed")', encoding='utf-8')
        (self.package / 'apps/workbench/server.py').write_text('import definitely_unapproved_library\n', encoding='utf-8')
        report = validator(self.data, reviewed_source=True)(self.package)
        self.assertFalse(report['passed'])
        self.assertTrue(report['architecture_error_count'])

    def test_candidates_cannot_enlarge_the_cycle_policy_baseline(self):
        (self.package / 'host').mkdir()
        (self.package / 'host/candidate_a.py').write_text('from host import candidate_b\n', encoding='utf-8')
        (self.package / 'host/candidate_b.py').write_text('from host import candidate_a\n', encoding='utf-8')
        (self.package / 'tools').mkdir()
        (self.package / 'tools/architecture-baseline.json').write_text(json.dumps(
            {'host_import_cycles': [['host.candidate_a', 'host.candidate_b']]}), encoding='utf-8')
        report = validator(self.data)(self.package)
        self.assertFalse(report['architecture_passed'])
        self.assertTrue(any('cycle' in error for error in report['architecture_sample']))
