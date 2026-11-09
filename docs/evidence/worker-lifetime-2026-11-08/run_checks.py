"""Reproduce the scoped lifetime regression from the current checkout."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
PATTERNS = ['test_worker_process.py', 'test_codex_candidate.py', 'test_worker.py',
            'test_studio3d.py', 'test_studio3d_learning.py', 'test_anatomy_engineering.py',
            'test_native_manifest.py', 'test_architecture_boundaries.py',
            'test_application_runtime.py', 'test_companion_workflows.py']
SOURCES = ['control/worker/process.py', 'adapters/models/codex_cli.py',
           'host/studio3d.py', 'host/studio3d_learning.py', 'host/anatomy_engineering.py',
           'tests/test_worker_process.py', 'tests/test_codex_candidate.py']

if __name__ == '__main__':
    suite = unittest.TestSuite()
    for pattern in PATTERNS:
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern))
    started = time.monotonic()
    with (HERE/'tests.log').open('w', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = {'date':'2026-11-08', 'scope':'development checkout; not deployed',
              'baseline_head':subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'platform':platform.platform(), 'python':platform.python_version(),
              'patterns':PATTERNS, 'tests':result.testsRun,
              'failures':len(result.failures), 'errors':len(result.errors),
              'skipped':[{'test':str(test), 'reason':reason} for test, reason in result.skipped],
              'seconds':round(time.monotonic()-started, 3),
              'sources_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES},
              'tests_log_sha256':hashlib.sha256((HERE/'tests.log').read_bytes()).hexdigest()}
    (HERE/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(not result.wasSuccessful())
