"""Actual old application reads the isolated ledger; candidate capture costs no calls."""
from pathlib import Path
import hashlib,json,os,statistics,subprocess,sys,time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 from modules.release_recovery.application import Applications
 from host.completion import refresh
 from test_task_lessons import TaskLessonTests
 from modules.context_knowledge.task_lessons import EVENT
 daily=Applications(Path('E:/Jarvis/runtime/user-data'));state=daily.state();build=state['active']['build']
 package=Path(daily.approved(build,fresh=False)['path']);manifest=json.loads((package/'application.json').read_text(encoding='utf-8'))
 for name,meta in manifest['files'].items():assert sha(package/name)==meta['sha256']
 case=TaskLessonTests('test_existing_pump_collects_candidate_once_without_promoting_or_copying_content');case.setUp()
 try:
  _,tid=case.finish();initial=refresh(case.core,tid)['learning_candidate'];events=case.events(tid)
  calls=case.core.db.all('SELECT * FROM model_calls');grants=case.core.db.all('SELECT * FROM grants')
  code='import sys,json;sys.path.insert(0,'+repr(str(package))+');from host.core import Core;from host.completion import refresh\ncore=Core('+repr(str(case.root))+')\ntry:\n value=refresh(core,'+repr(tid)+')\n print(json.dumps({"state":value["state"],"has_learning_candidate":"learning_candidate" in value}))\nfinally:core.close()'
  old=subprocess.run([sys.executable,'-X','utf8','-I','-B','-c',code],cwd=package,capture_output=True,text=True,encoding='utf-8',timeout=45)
  assert old.returncode==0,old.stderr
  old_value=json.loads(old.stdout);assert old_value=={'state':'VERIFIED','has_learning_candidate':False},old_value
  assert case.events(tid)==events
  returned=refresh(case.core,tid)['learning_candidate'];assert returned==initial
  samples={'capture_disabled_ms':[],'capture_enabled_ms':[]}
  for _ in range(20):
   with patch('host.completion.learning_candidate',return_value=None):
    start=time.perf_counter();refresh(case.core,tid);samples['capture_disabled_ms'].append((time.perf_counter()-start)*1000)
   start=time.perf_counter();refresh(case.core,tid);samples['capture_enabled_ms'].append((time.perf_counter()-start)*1000)
  assert case.events(tid)==events
  assert calls==case.core.db.all('SELECT * FROM model_calls');assert grants==case.core.db.all('SELECT * FROM grants')
  timing={k:{'count':len(v),'median_ms':statistics.median(v),'max_ms':max(v)} for k,v in samples.items()}
  result={'passed':True,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
   'working_runtime_sha256':{name:sha(ROOT/name) for name in ('host/completion.py','modules/context_knowledge/task_lessons.py','apps/workbench/ui.js')},
   'scope':'isolated native pure-text task with stub planning; actual old reader and same-process refresh timing, not real model or long-term learning benefit',
   'old_application_build':build,'old_application_read':old_value,'old_read_preserves_candidate_audit':True,
   'new_read_revalidates_same_candidate':True,'extra_model_calls':0,'grants_unchanged':True,'candidate_events_after_repeated_refresh':len(events),
   'timing':timing,'raw_timing':samples,'production_data_used':False,'production_adopted':False}
  (OUT/'ledger-recovery.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
  print(json.dumps({k:v for k,v in result.items() if k not in ('raw_timing','working_runtime_sha256')}),flush=True)
 finally:case.tearDown()

if __name__=='__main__':main()
