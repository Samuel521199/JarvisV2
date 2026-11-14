"""Actual installed protocol4 reader against an isolated v4 goal, never live DBs."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 daily=Path('E:/Jarvis/runtime/user-data')
 record=json.loads((daily/'deployment/launcher.json').read_text(encoding='utf-8'))
 controller=Path(record['controller']);assert controller.parent==daily/'deployment/controllers'
 assert record['controller_protocol']==4
 index=controller/'controller-files.json';assert sha(index)==record['controller_inventory_sha256']
 entries=json.loads(index.read_text(encoding='utf-8'))
 for name,value in entries.items():
  path=(controller/name).resolve();assert path.is_relative_to(controller) and sha(path)==value
 import test_advice_intent as fixture
 from control.application_compatibility import required
 from host import goal_context
 from sdk.protocol import canonical
 case=fixture.IntentIntegration('test_v4_selects_composed_purpose_without_reinterpreting_v3');case.setUp()
 rows=[]
 try:
  case.method();ident=case.current();context=goal_context.get(case.core,ident)
  for historical in (False,True):
   if historical:
    with case.core.db.transaction() as tx:tx.execute('UPDATE goal_context SET view=?,history=? WHERE goal_id=?',('{}',canonical([context['view']]),ident))
   expected=required(case.root);assert expected['goal_advice_schema']==4
   code='import sys,json;sys.path.insert(0,'+repr(str(controller))+');from control.application_compatibility import required;from sdk.protocol import CoreError\ntry:\n print(json.dumps(required('+repr(str(case.root))+')))\nexcept CoreError as e:\n print(json.dumps({"rejected":True,"code":e.code}))'
   done=subprocess.run([sys.executable,'-X','utf8','-I','-B','-c',code],cwd=controller,capture_output=True,text=True,encoding='utf-8',timeout=45)
   assert done.returncode==0,done.stderr
   value=json.loads(done.stdout);assert value=={'rejected':True,'code':'application_data_compatibility'},value
   rows.append({'historical':historical,'new_reader_required':expected,'actual_installed_reader':value})
 finally:case.tearDown()
 result={'passed':True,'controller_protocol':record['controller_protocol'],'controller_build':record['build'],
  'controller_files_verified':len(entries),'rows':rows,'production_data_used':False,'model_calls':0,
  'scope':'actual installed old controller code refuses isolated current/historical v4 advice; no production promotion or new native recovery claim'}
 (OUT/'actual-reader-boundary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result))

if __name__=='__main__':main()
