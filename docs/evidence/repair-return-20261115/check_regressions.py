"""Deterministic regression evidence; no live roots or model requests."""
from pathlib import Path
import hashlib,json,os,sys,time,unittest
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
PATTERNS=['test_repair_return.py','test_work_revisions.py','test_work_budgets.py','test_work_recovery.py','test_quote_rework.py','test_lesson_repair.py','test_development*.py','test_goal_growth.py','test_lesson_validation.py','test_concurrency.py','test_application_runtime.py','test_task_lessons.py','test_completion*.py','test_goal_advice*.py',
 'test_goal_plans.py','test_advice_purpose.py','test_advice_intent.py',
 'test_knowledge_cleanup.py','test_conditional_advice.py','test_workbench.py']


def inventory():
 return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
  for name in ('adapters','apps','control','host','modules','sdk','config','tests')
  for p in (ROOT/name).rglob('*') if p.is_file() and p.suffix in ('.py','.json','.js','.css','.html')}

def main():
 before=inventory();started=time.monotonic();suite=unittest.TestSuite()
 for pattern in PATTERNS:suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=pattern))
 with (OUT/'regressions-r2.txt').open('x',encoding='utf-8') as stream:
  result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
 unchanged=before==inventory()
 report={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
  'source_unchanged':unchanged,'seconds':time.monotonic()-started,'patterns':PATTERNS,
  'scope':'deterministic development integration; no model quality trial or production adoption','passed':result.wasSuccessful() and unchanged}
 (OUT/'regressions-r2.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report),flush=True)
 if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
