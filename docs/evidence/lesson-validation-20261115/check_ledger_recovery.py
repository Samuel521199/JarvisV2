"""Same isolated ledger through the actual old reader; no production writes."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')

def main():
 from host.completion import refresh
 from host.lesson_validation import run
 from modules.context_knowledge.lesson_trials import LessonTrials
 from modules.release_recovery.application import Applications
 from test_lesson_validation import LessonValidationTests
 daily=Applications(Path('E:/Jarvis/runtime/user-data'));state=daily.state();build=state['active']['build']
 package=Path(daily.approved(build,fresh=False)['path'])
 manifest=json.loads((package/'application.json').read_text(encoding='utf-8'))
 for name,meta in manifest['files'].items():assert hashlib.sha256((package/name).read_bytes()).hexdigest()==meta['sha256']
 case=LessonValidationTests('test_existing_background_lane_runs_once_and_foreground_defers');case.setUp()
 try:
  _,tid=case.candidate();case.enable();result=run(case.root,tid);assert result['status']=='PASSED'
  initial=refresh(case.core,tid)['learning_candidate'];trials=LessonTrials(case.core.db)
  events=case.core.db.all("SELECT * FROM events WHERE kind LIKE 'learning.%'")
  before={table:case.core.db.all('SELECT * FROM '+table) for table in ('grants','model_calls','facts','actions')}
  code='import sys,json;sys.path.insert(0,'+repr(str(package))+');from host.core import Core;from host.completion import refresh\ncore=Core('+repr(str(case.root))+')\ntry:\n v=refresh(core,'+repr(tid)+')\n print(json.dumps({"state":v["state"],"has_learning_candidate":"learning_candidate" in v}))\nfinally:core.close()'
  old=subprocess.run([sys.executable,'-X','utf8','-I','-B','-c',code],cwd=package,capture_output=True,text=True,encoding='utf-8',timeout=45)
  assert old.returncode==0,old.stderr
  old_value=json.loads(old.stdout);assert old_value=={'state':'VERIFIED','has_learning_candidate':False}
  assert events==case.core.db.all("SELECT * FROM events WHERE kind LIKE 'learning.%'")
  assert refresh(case.core,tid)['learning_candidate']==initial
  assert run(case.root,tid)['status']=='existing';assert trials.used()==1
  for table,rows in before.items():assert rows==case.core.db.all('SELECT * FROM '+table)
  report={'passed':True,'scope':'isolated pure-text fixture, actual v0.1.8 reader; not production switch, backup rollback or user holdout',
   'old_build':build,'old_reader':old_value,'audit_preserved':True,'policy_preserved':trials.policy(),
   'new_reader_same_candidate':True,'replay_prevented':True,'used_after_old_read':trials.used(),
   'business_tables_unchanged':list(before),'trial':result,'reservation':initial['validation']['trial'],
   'production_adopted':False,'production_data_used':False,
   'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('host/lesson_validation.py','host/completion.py','modules/context_knowledge/lesson_trials.py','modules/task_resource/lesson_checks.py')}}
  (OUT/'ledger-recovery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(json.dumps({k:v for k,v in report.items() if k not in ('trial','reservation','source_sha256')}),flush=True)
 finally:case.tearDown()

if __name__=='__main__':main()
