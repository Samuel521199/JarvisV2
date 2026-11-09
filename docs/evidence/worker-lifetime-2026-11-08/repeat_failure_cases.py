"""Repeat the four real-process candidate failure variants ten times."""
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]

if __name__ == '__main__':
    name = 'test_worker_process.WorkerProcess.test_candidate_adapter_timeout_cancel_and_output_limit_reap_tree'
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for _ in range(10))
    started = time.monotonic()
    with (HERE/'stress.log').open('w', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = {'repetitions':10, 'variants_per_test':['timeout','cancel','output_limit','output_limit_fast_exit'],
              'tests':result.testsRun, 'failures':len(result.failures), 'errors':len(result.errors),
              'skipped':len(result.skipped), 'seconds':round(time.monotonic()-started, 3),
              'source_sha256':hashlib.sha256((ROOT/'control/worker/process.py').read_bytes()).hexdigest()}
    (HERE/'stress.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))
    raise SystemExit(not result.wasSuccessful())
