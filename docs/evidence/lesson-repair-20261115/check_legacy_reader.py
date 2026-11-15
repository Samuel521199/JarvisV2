"""Old application reads standard repair development, preserving review/receipts."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')

def main():
 from test_lesson_repair import LessonRepairTests
 from modules.release_recovery.application import Applications
 from host.completion import refresh
 daily=Applications(Path('E:/Jarvis/runtime/user-data'));state=daily.state();build=state['active']['build']
 package=Path(daily.approved(build,fresh=False)['path']);manifest=json.loads((package/'application.json').read_text(encoding='utf-8'))
 for name,meta in manifest['files'].items():assert hashlib.sha256((package/name).read_bytes()).hexdigest()==meta['sha256']
 case=LessonRepairTests('test_missing_review_control_cannot_publish_repair_grant');case.setUp()
 try:
  _,tid=case.failed();draft=case.prepare_repair(tid);ident=case.begin_repair(tid,draft)['id']
  original=refresh(case.core,tid)['learning_candidate'];events=case.core.db.all("SELECT * FROM events WHERE kind LIKE 'learning.%'")
  tables={t:case.core.db.all('SELECT * FROM '+t) for t in ('grants','development_runs','development_controls','model_calls','facts','actions')}
  code='import sys,json;sys.path.insert(0,'+repr(str(package))+');from host.core import Core;from host.completion import refresh;from sdk.protocol import CoreError\ncore=Core('+repr(str(case.root))+')\ntry:\n v=refresh(core,'+repr(tid)+');r=core.development.get('+repr(ident)+')\n try:core._publication_check('+repr(ident)+',"unreviewed")\n except CoreError as e:gate=e.code\n else:gate="NOT_BLOCKED"\n print(json.dumps({"completion":v["state"],"repair_status":r["status"],"review_gate":gate}))\nfinally:core.close()'
  old=subprocess.run([sys.executable,'-X','utf8','-I','-B','-c',code],cwd=package,capture_output=True,text=True,encoding='utf-8',timeout=45)
  assert old.returncode==0,old.stderr
  result=json.loads(old.stdout);assert result=={'completion':'VERIFIED','repair_status':'READY','review_gate':'review_required'}
  assert original==refresh(case.core,tid)['learning_candidate']
  assert events==case.core.db.all("SELECT * FROM events WHERE kind LIKE 'learning.%'")
  for table,rows in tables.items():assert rows==case.core.db.all('SELECT * FROM '+table)
  assert case.begin_repair(tid,draft)=={'id':ident,'existing':True}
  report={'passed':True,'old_build':build,'old_result':result,'audit_and_grants_preserved':True,'new_reader_same_projection':True,'duplicate_does_not_create_new_run':True,
   'scope':'actual old reader on isolated standard development rows; no daily switch or full self-healing claim','real_model_calls':0,'production_adopted':False}
  (OUT/'legacy-reader.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report),flush=True)
 finally:case.tearDown()

if __name__=='__main__':main()
