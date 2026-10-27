"""Admission of new work must not fail just because this process is executing."""
from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from control.execution import ExecutionCohort, admission, executor_held
from control.recovery.gate import RunLock
from sdk.protocol import CoreError


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / 'state').mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_admission_proceeds_while_own_cohort_executes(self):
        cohort = ExecutionCohort(self.root); recovered = []
        permit = cohort.acquire('task-1', lambda: recovered.append(1))
        try:
            self.assertTrue(executor_held(self.root))
            with self.assertRaises(CoreError) as raised:
                with RunLock(self.root): pass
            self.assertEqual(raised.exception.code, 'busy')  # other processes stay excluded
            started = time.monotonic()
            with admission(self.root) as lock:
                self.assertIsNone(lock)
            self.assertLess(time.monotonic() - started, 0.5)
        finally:
            permit.close()
        self.assertEqual(recovered, [1])
        self.assertFalse(executor_held(self.root))

    def test_admission_takes_and_releases_os_lock_when_idle(self):
        with admission(self.root) as lock:
            self.assertIsNotNone(lock)
            with self.assertRaises(CoreError):
                with RunLock(self.root): pass
        with RunLock(self.root): pass

    def test_foreign_executor_still_blocks_admission_after_bounded_wait(self):
        foreign = RunLock(self.root); foreign.__enter__()
        try:
            started = time.monotonic()
            with self.assertRaises(CoreError) as raised:
                with admission(self.root, wait=0.3): pass
            self.assertEqual(raised.exception.code, 'busy')
            self.assertGreaterEqual(time.monotonic() - started, 0.25)
        finally:
            foreign.__exit__(None, None, None)

    def test_admission_waits_for_short_foreign_hold(self):
        foreign = RunLock(self.root); foreign.__enter__()
        threading.Timer(0.2, lambda: foreign.__exit__(None, None, None)).start()
        with admission(self.root, wait=2.0) as lock:
            self.assertIsNotNone(lock)

    def test_admissions_in_one_process_are_serialized_while_cohort_runs(self):
        cohort = ExecutionCohort(self.root)
        permit = cohort.acquire('task-1', lambda: None)
        inside, overlap = [], []
        def admit():
            with admission(self.root):
                if inside: overlap.append(1)
                inside.append(1); time.sleep(0.05); inside.pop()
        try:
            threads = [threading.Thread(target=admit) for _ in range(4)]
            for t in threads: t.start()
            for t in threads: t.join()
        finally:
            permit.close()
        self.assertEqual(overlap, [])


if __name__ == '__main__':
    unittest.main()
