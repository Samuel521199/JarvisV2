"""Actual daily v0.1.8 reader on isolated returned work; no daily writes."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
def main():
 from test_repair_return import RepairReturnTests
 from modules.release_recovery.application import Applications
 from host.work_revisions import cancel
 daily=Applications(Path('E:/Jarvis/runtime/user-data'));state=daily.state();build=state['active']['build']
 package=Path(daily.approved(build,fresh=False)['path']);manifest=json.loads((package/'application.json').read_text(encoding='utf-8'))
 assert all(hashlib.sha256((package/n).read_bytes()).hexdigest()==m['sha256'] for n,m in manifest['files'].items())
 case=RepairReturnTests('test_source_cancel_before_model_preserves_old_tool_and_calls');case.setUp()
 try:
  goal,tid,ident,provider=case.begin_auto(wrong_original=True);result=case.execute(ident,provider)
  assert result['status']=='CLOSED',result
  def read_old():
   code='import sys,json;sys.path.insert(0,'+repr(str(package))+');from host.core import Core;from host.completion import refresh;from sdk.protocol import CoreError\ncore=Core('+repr(str(case.root))+')\ntry:\n v=refresh(core,'+repr(result['child_task'])+')\n try:core._goal_memory_check('+repr(result['child_task'])+')\n except CoreError as e:gate=e.code\n else:gate="current"\n try:core._publication_check('+repr(ident)+',"wrong-package")\n except CoreError as e:review=e.code\n else:review="NOT_BLOCKED"\n print(json.dumps({"condition_score":v["condition_score"],"state":v["state"],"work_gate":gate,"publication_gate":review}))\nfinally:core.close()'
   old=subprocess.run([sys.executable,'-X','utf8','-I','-B','-c',code],cwd=package,capture_output=True,text=True,encoding='utf-8',timeout=45)
   assert old.returncode==0,old.stderr
   return json.loads(old.stdout)
  tables=('grants','actions','work_revisions','work_owners','work_budgets','development_controls')
  before={t:case.core.db.all('SELECT * FROM '+t) for t in tables}
  audit=case.core.db.all("SELECT * FROM events WHERE kind='learning.repair_return'")
  old=read_old();assert old=={'condition_score':100,'state':'VERIFIED','work_gate':'current','publication_gate':'review_required'},old
  assert before=={t:case.core.db.all('SELECT * FROM '+t) for t in tables}
  assert audit==case.core.db.all("SELECT * FROM events WHERE kind='learning.repair_return'")
  cancel(case.core,goal,case.core.works.owner(goal)['revision'])
  cancelled=read_old();assert cancelled['work_gate']=='work_conflict',cancelled
  report={'passed':True,'old_build':build,'before_cancel':old,'after_cancel':cancelled,
   'old_reader_preserves_audit_grants_actions_work':True,'scope':'real old reader and existing work cancellation; no automatic orchestrator in old version',
   'production_adopted':False,'real_model_calls':0}
  (OUT/'legacy-reader-final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report),flush=True)
 finally:case.tearDown()
if __name__=='__main__':main()
