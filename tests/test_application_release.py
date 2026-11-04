import copy
import json
import os
from pathlib import Path
import tempfile
import socket
import unittest
from unittest.mock import patch
import zipfile

from control.application_runtime import accepting, coordination, publish
from control.recovery.gate import StopGate
from modules.release_recovery.application import Applications, build, relative, inspect_package
from sdk.protocol import CoreError, canonical


class ProcessDouble:
    def __init__(self):
        self.live = None
        self.failed = set()
        self.drain_blocked = False
        self.exit_blocked = False
        self.events = []
        self.stop_during_health = None

    def start(self, record, selected, epoch):
        if self.live is not None: raise AssertionError('overlapping application writers')
        self.live = (selected['build'], epoch)
        self.events.append(('start', *self.live))

    def health(self, selected, epoch):
        assert self.live == (selected['build'], epoch)
        if selected['build'] in self.failed:
            if self.stop_during_health: self.stop_during_health()
            raise RuntimeError('synthetic unhealthy version')

    def activate(self, selected, epoch):
        assert self.live == (selected['build'], epoch)
        self.events.append(('activate', *self.live))

    def drain(self, selected, epoch):
        if self.drain_blocked: raise RuntimeError('synthetic work still running')
        if self.live is not None: assert self.live == (selected['build'], epoch)

    def stop(self, selected, epoch):
        if self.exit_blocked: raise RuntimeError('synthetic exit unconfirmed')
        if self.live is not None:
            assert self.live == (selected['build'], epoch)
            self.events.append(('stop', *self.live))
            self.live = None

    def running(self, selected, epoch):
        return self.live == (selected['build'], epoch)


@unittest.skipUnless(os.name == 'nt', 'Local approvals currently require Windows DPAPI')
class ApplicationReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-application-test-')
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'data'
        for name in ['state', 'private']:
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.app = Applications(self.root)
        self.driver = ProcessDouble()

    def tearDown(self):
        self.assertEqual(self.base.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.base.name.startswith('jarvis-application-test-'))
        self.temp.cleanup()

    def candidate(self, version, approved=True):
        source = self.base / version
        (source / 'apps/workbench').mkdir(parents=True)
        (source / 'VERSION').write_text(version, encoding='utf-8')
        (source / 'apps/workbench/server.py').write_text('# synthetic ' + version, encoding='utf-8')
        archive = self.base / (version + '.zip')
        ident = build(source, ['VERSION', 'apps/workbench/server.py'], archive, version)
        self.app.stage(archive)
        if approved:
            self.app.validate(ident, lambda _: {'passed': True, 'scope': 'synthetic protocol fixture only'})
        return ident

    def test_unvalidated_candidate_cannot_launch(self):
        ident = self.candidate('unapproved', False)
        with self.assertRaises(CoreError): self.app.adopt(ident, self.driver)
        self.assertIsNone(self.driver.live)

    def test_failed_validation_cannot_launch(self):
        ident = self.candidate('bad-check', False)
        self.app.validate(ident, lambda _: {'passed': False})
        with self.assertRaises(CoreError): self.app.adopt(ident, self.driver)

    def test_a_to_b_and_explicit_rollback_preserve_corrected_data(self):
        first, second = self.candidate('one'), self.candidate('two')
        self.app.adopt(first, self.driver)
        facts = self.root / 'state/owner-facts.json'
        facts.write_text('{"correction":2,"revoked":true}', encoding='utf-8')
        before = facts.read_bytes()
        state = self.app.adopt(second, self.driver)
        self.assertEqual((state['active']['build'], state['active']['slot']), (second, 'B'))
        restored = self.app.rollback(self.driver)
        self.assertEqual(restored['active']['build'], first)
        self.assertEqual(restored['epoch'], 3)
        self.assertEqual(facts.read_bytes(), before)

    def test_unhealthy_candidate_restores_baseline_at_new_epoch(self):
        first, second = self.candidate('good'), self.candidate('unhealthy')
        self.app.adopt(first, self.driver)
        self.driver.failed.add(second)
        state = self.app.adopt(second, self.driver)
        self.assertEqual(state['active']['build'], first)
        self.assertEqual(state['epoch'], 3)
        self.assertEqual(state['error'], 'candidate_unhealthy')
        self.assertIsNone(self.app.record(second)['approval'])
        self.assertTrue(accepting(self.root))

    def test_old_baseline_receipt_does_not_expire_for_automatic_restore(self):
        with patch('time.time', return_value=100):
            first = self.candidate('older')
            self.app.adopt(first, self.driver)
        second = self.candidate('newer')
        self.driver.failed.add(second)
        self.assertEqual(self.app.adopt(second, self.driver)['active']['build'], first)

    def test_new_adoption_requires_fresh_evidence(self):
        with patch('time.time', return_value=100): first = self.candidate('stale')
        with self.assertRaises(CoreError): self.app.adopt(first, self.driver)
        self.assertIsNone(self.driver.live)

    def test_drain_failure_never_starts_another_writer_and_can_recover(self):
        first, second = self.candidate('busy-one'), self.candidate('busy-two')
        self.app.adopt(first, self.driver)
        self.driver.drain_blocked = True
        with self.assertRaises(CoreError): self.app.adopt(second, self.driver)
        self.assertEqual(self.driver.live, (first, 1))
        self.assertFalse(accepting(self.root))
        self.driver.drain_blocked = False
        self.assertEqual(self.app.recover(self.driver)['active']['build'], first)
        self.assertEqual(self.driver.live, (first, 2))

    def test_unconfirmed_candidate_exit_blocks_baseline_restart(self):
        first, second = self.candidate('exit-one'), self.candidate('exit-two')
        self.app.adopt(first, self.driver)
        original_stop = self.driver.stop
        def stop(selected, epoch):
            if selected['build'] == second: raise RuntimeError('exit not confirmed')
            original_stop(selected, epoch)
        self.driver.stop = stop
        self.driver.failed.add(second)
        with self.assertRaises(CoreError): self.app.adopt(second, self.driver)
        self.assertEqual(self.driver.live, (second, 2))
        self.assertEqual(self.app.state()['phase'], 'blocked')
        self.assertEqual(coordination(self.root)['build'], second)
        self.driver.stop = original_stop
        self.assertEqual(self.app.recover(self.driver)['active']['build'], first)

    def test_latch_during_failed_start_prevents_restart(self):
        first, second = self.candidate('stop-one'), self.candidate('stop-two')
        self.app.adopt(first, self.driver)
        self.driver.failed.add(second)
        self.driver.stop_during_health = lambda: StopGate(self.root).stop(latch=True)
        with self.assertRaises(CoreError): self.app.adopt(second, self.driver)
        self.assertEqual(StopGate(self.root).state(), 'latched')
        self.assertIsNone(self.driver.live)

    def test_mutation_after_validation_is_rejected(self):
        ident = self.candidate('tampered')
        folder = Path(self.app.record(ident)['path'])
        (folder / 'apps/workbench/server.py').write_text('# changed', encoding='utf-8')
        with self.assertRaises(CoreError): self.app.adopt(ident, self.driver)

    def test_validation_cannot_change_candidate_and_manifest_together(self):
        ident = self.candidate('changed-in-check', False)
        def mutate(folder):
            manifest = json.loads((folder / 'application.json').read_text())
            manifest['version'] = 'forged'
            (folder / 'application.json').write_text(canonical(manifest), encoding='utf-8')
            return {'passed': True}
        with self.assertRaises(CoreError): self.app.validate(ident, mutate)

    def test_forged_approval_report_is_rejected(self):
        ident = self.candidate('report-tamper')
        record = self.app.record(ident)
        record['approval']['receipt']['report']['scope'] = 'forged'
        with self.app.db() as db:
            db.execute('UPDATE packages SET body=? WHERE build=?', (canonical(record), ident))
        with self.assertRaises(CoreError): self.app.adopt(ident, self.driver)

    def test_invalid_archive_paths_and_duplicates_leave_no_staging_debris(self):
        for index, names in enumerate([['../escape'], ['C:/escape'], ['apps/a.py', 'apps/a.py']]):
            archive = self.base / ('bad-' + str(index) + '.zip')
            with zipfile.ZipFile(archive, 'w') as stream:
                for name in names: stream.writestr(name, 'synthetic')
            with self.assertRaises(CoreError): self.app.stage(archive)
        self.assertEqual(list((self.root / 'deployment/staging').iterdir()), [])
        self.assertFalse((self.root / 'escape').exists())

    def test_private_and_traversal_paths_are_rejected(self):
        for name in ['user-data/a', 'apps/../a', 'apps/a:secret', '/apps/a', 'apps\\a', 'apps/a.']:
            with self.assertRaises(CoreError): relative(name)

    def test_unsupported_data_schema_is_rejected(self):
        ident = self.candidate('schema-fixture', False)
        folder = Path(self.app.record(ident)['path'])
        value = json.loads((folder / 'application.json').read_text())
        value['data_schema'] = 8
        (folder / 'application.json').write_text(canonical(value), encoding='utf-8')
        with self.assertRaises(CoreError): inspect_package(folder)

    def test_duplicate_stage_is_idempotent_and_leaves_no_staging_copy(self):
        ident = self.candidate('duplicate')
        self.app.stage(self.base / 'duplicate.zip')
        self.assertTrue(self.app.record(ident)['approval'])
        self.assertEqual(list((self.root / 'deployment/staging').iterdir()), [])

    def test_restart_of_controller_retains_state_and_epochs(self):
        ident = self.candidate('persist')
        self.app.adopt(ident, self.driver)
        self.assertEqual(Applications(self.root).state(), self.app.state())
        self.assertEqual(coordination(self.root)['epoch'], 1)

    def test_missing_control_journal_does_not_reset_a_managed_generation(self):
        publish(self.root, 'a' * 64, 5, 'active')
        (self.root / 'deployment/control.sqlite3').unlink()
        with self.assertRaises(CoreError): Applications(self.root)
        self.assertEqual(coordination(self.root)['epoch'], 5)

    def test_controller_repairs_a_stale_coordination_snapshot_from_its_journal(self):
        ident = self.candidate('snapshot')
        self.app.adopt(ident, self.driver)
        publish(self.root, ident, 1, 'starting')
        self.app.recover(self.driver)
        self.assertEqual(coordination(self.root)['phase'], 'active')

    def test_stop_closes_admission_without_rewinding_business_files(self):
        first = self.candidate('stop')
        self.app.adopt(first, self.driver)
        self.app.stop(self.driver)
        self.assertIsNone(self.driver.live)
        self.assertEqual(self.app.state()['phase'], 'stopped')
        self.assertFalse(accepting(self.root))
        state = self.app.start(self.driver)
        self.assertEqual(state['active']['build'], first)
        self.assertEqual(state['epoch'], 2)

    def test_explicit_restart_requires_old_host_exit_and_honours_stop(self):
        first = self.candidate('resume-after-exit')
        self.app.adopt(first, self.driver)
        self.driver.live = None  # fixture models an already exited old process
        self.assertEqual(self.app.start(self.driver)['epoch'], 2)
        StopGate(self.root).stop(latch=True)
        with self.assertRaises(CoreError): self.app.start(self.driver)

    def test_interrupted_candidate_start_is_recovered_with_monotonic_epoch(self):
        first, second = self.candidate('crash-a'), self.candidate('crash-b')
        self.app.adopt(first, self.driver)
        original = self.driver.health
        self.driver.health = lambda selected, epoch: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt): self.app.adopt(second, self.driver)
        self.driver.health = original
        self.assertEqual(self.app.recover(self.driver)['active']['build'], first)
        self.assertEqual(self.driver.live, (first, 3))

    def test_stale_baseline_generation_cannot_replace_active_version(self):
        first, second = self.candidate('epoch-a'), self.candidate('epoch-b')
        self.app.adopt(first, self.driver)
        with self.assertRaises(CoreError): self.app.adopt(second, self.driver, expected_epoch=0)
        self.assertEqual(self.driver.live, (first, 1))

    def test_retirement_is_reversible_and_protects_active_and_previous(self):
        first, second, third = self.candidate('retire-a'), self.candidate('retire-b'), self.candidate('retire-c')
        self.app.adopt(first, self.driver); self.app.adopt(second, self.driver)
        for ident in [first, second]:
            with self.assertRaises(CoreError): self.app.retire(ident)
        old = self.app.retire(third)
        self.assertTrue(old['retired'])
        self.assertTrue(Path(old['path']).is_dir())
        with self.assertRaises(CoreError): self.app.approved(third)
        restored = self.app.retire(third, restore=True)
        self.assertFalse(restored['retired'])
        self.assertEqual(self.app.approved(third)['build'], third)

    def test_real_process_handoff_failed_health_and_code_rollback(self):
        from adapters.application_host import WorkbenchProcess
        from host.core import Core
        Core.initialize(self.root).close()
        project = Path(__file__).resolve().parents[1]
        versions = []
        names = ['control/application_runtime.py', 'control/credentials.py', 'control/atomic.py',
                 'control/paths.py', 'control/recovery/gate.py', 'sdk/protocol.py']
        for version in ['fixture-v1', 'fixture-v2', 'fixture-bad-v3']:
            source = self.base / version
            (source / 'apps/workbench').mkdir(parents=True)
            (source / 'VERSION').write_text(version, encoding='utf-8')
            (source / 'apps/workbench/server.py').write_bytes((project / 'tests/fixtures/application_host.py').read_bytes())
            for name in names:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((project / name).read_bytes())
            archive = self.base / (version + '.zip')
            ident = build(source, [*names, 'VERSION', 'apps/workbench/server.py'], archive, version)
            self.app.stage(archive)
            self.app.validate(ident, lambda _: {'passed': True, 'scope': 'synthetic process fixture, not a product release'})
            versions.append(ident)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        driver = WorkbenchProcess(self.root, port, timeout=2)
        facts = self.root / 'state/retained-facts.json'
        facts.write_text('{"revision":3,"permission_revoked":true}', encoding='utf-8')
        original = facts.read_bytes()
        try:
            self.assertEqual(self.app.adopt(versions[0], driver)['active']['slot'], 'A')
            self.assertEqual(self.app.adopt(versions[1], driver)['active']['slot'], 'B')
            restored = self.app.adopt(versions[2], driver)
            self.assertEqual(restored['active']['build'], versions[1])
            self.assertEqual(restored['epoch'], 4)
            rolled = self.app.rollback(driver)
            self.assertEqual(rolled['active']['build'], versions[0])
            self.assertEqual(rolled['epoch'], 5)
            self.assertEqual(facts.read_bytes(), original)
            self.app.stop(driver)
            self.assertEqual(self.app.start(driver)['epoch'], 6)
            self.app.stop(driver)
        finally:
            for process in driver.processes.values():
                if process.poll() is None: process.terminate()
                process.wait(timeout=5)
