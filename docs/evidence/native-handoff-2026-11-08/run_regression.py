"""Supplementary application-policy and shutdown regressions."""
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]

if __name__=='__main__':
    patterns=['test_application_release.py','test_application_checks.py',
              'test_architecture_boundaries.py','test_runtime_shutdown.py']
    suite=unittest.TestSuite(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=p) for p in patterns)
    started=time.monotonic()
    with (HERE/'regression.log').open('w',encoding='utf-8') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report={'patterns':patterns,'tests':result.testsRun,'failures':len(result.failures),
            'errors':len(result.errors),'skipped':len(result.skipped),'seconds':round(time.monotonic()-started,3)}
    (HERE/'regression.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report));raise SystemExit(not result.wasSuccessful())
