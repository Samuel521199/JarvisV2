"""Final guard changes and retained failure replay, with unchanged source hashes."""
from pathlib import Path
import importlib.util,json,sys,time,unittest
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
spec=importlib.util.spec_from_file_location('regression_inventory',OUT/'check_regressions.py');inventory=importlib.util.module_from_spec(spec);spec.loader.exec_module(inventory)
def main():
 before=inventory.inventory();started=time.monotonic()
 names=['test_repair_return','test_lesson_repair','test_application_runtime','test_goal_plans',
        'test_work_revisions.WorkRevisions.test_unfinished_and_non_linear_sources_are_rejected']
 suite=unittest.defaultTestLoader.loadTestsFromNames(names)
 with (OUT/'final-guards-r1.txt').open('x',encoding='utf-8') as stream:result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
 unchanged=before==inventory.inventory()
 value={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
  'source_unchanged':unchanged,'names':names,'seconds':time.monotonic()-started,'passed':result.wasSuccessful() and unchanged,
  'scope':'final upgrade, permission, followup, admission and exact-package guards; includes replay of retained initialization failure, no test removed or timeout raised'}
 (OUT/'final-guards-r1.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value),flush=True)
 if not value['passed']:raise SystemExit(1)
if __name__=='__main__':main()
