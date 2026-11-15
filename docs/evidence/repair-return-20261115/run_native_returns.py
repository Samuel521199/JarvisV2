"""Real native model repair, automatic publication and original-work revalidation.

Fixtures are operator-authored synthetic business tasks, not independent user work.
"""
from pathlib import Path
import hashlib,json,os,shutil,sys,time,traceback
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent/'native-r2'
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ.update(TEMP='E:/Jarvis/validation/temp',TMP='E:/Jarvis/validation/temp')
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
 from adapters.development_bridge import exchange
 from host.settings_operations import command
 from host.completion import refresh
 from host.repair_return import run
 from test_lesson_repair import LessonRepairTests
 from sdk.protocol import decode
 OUT.mkdir(exist_ok=False);dev=ROOT/'user-data'
 before=exchange(dev,'/status');catalog=exchange(dev,'/catalog')['catalog']
 assert before['daily_call_limit']==64 and 64-before['calls_in_24h']>=12
 provider=catalog['default_provider'];assert provider in before['allowed_providers']
 catalog.update(automatic_fallback=False,fallback_order=[provider])
 route={'provider':provider,'model':catalog['providers'][provider]['model'],'reasoning':'default'}
 files=('host/core.py','host/repair_return.py','host/lesson_repair.py','host/completion.py','modules/task_resource/repair_returns.py')
 frozen={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in files}
 write(OUT/'protocol.json',{'scope':'authored synthetic business failures; real model code and real restricted execution, not independent customer tasks',
  'domains':['notes','practice','quote'],'proxy_before':before,'route':route,'source_sha256':frozen,
  'prediction':'Each original task retains score 0; one linked corrected task reaches 100 on the identical declared conditions. No net token savings or general intelligence gain predicted.',
  'max_model_calls_per_run':4,'fallback':False,'retry_unknown':False,'daily_adoption':False})
 rows=[]
 for domain in ('notes','practice','quote'):
  folder=OUT/domain;folder.mkdir();case=LessonRepairTests('test_missing_review_control_cannot_publish_repair_grant')
  with patch('test_goal_plans.fixture',return_value=catalog):case.setUp()
  credential=case.root/'private/development-bridge.dpapi'
  try:
   assert case.root.resolve().is_relative_to(Path('E:/Jarvis/validation/temp'))
   goal,tid=case.candidate(domain,wrong_original=True);original=case.core.tasks.get(tid)
   assessment=refresh(case.core,tid);assert assessment['condition_score']==0
   for name in ('config/development.json','private/development-bridge.dpapi'):
    target=case.root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dev/name,target)
   draft=command(case.root,{'action':'lesson_repair_prepare','id':tid})
   ident=command(case.root,{'action':'lesson_repair_begin_auto','id':tid,'key':draft['key'],'fingerprint':draft['fingerprint'],
    'reviewed':True,'routes':{'plan':[route],'code':[route]}})['id']
   write(folder/'freeze.json',{'spec':case.core.development.get(ident)['spec'],'original_condition_score':0,
    'acceptance':assessment['acceptance'],'source_task':tid,'source_goal':goal,'original_input_sent_to_model':False})
   current=exchange(dev,'/status');assert current['daily_call_limit']==64 and 64-current['calls_in_24h']>=4
   started=time.monotonic();result=run(case.root,ident)
   development=case.core.development.get(ident)
   calls=case.core.db.all('SELECT phase,status,error,model,usage FROM model_calls WHERE run_id=? ORDER BY created',(ident,))
   after=refresh(case.core,tid);package=case.core.packages.get(development['release_id']) if development['release_id'] else None
   bindings=all(case.core.registry.binding(cap)==binding for cap,binding in original['bindings'].items())
   row={'domain':domain,'passed':result['status']=='CLOSED' and result['actual']['condition_score']==100 and after['condition_score']==0 and bindings,
    'seconds':time.monotonic()-started,'return':result,'calls':calls,
    'total_tokens':sum((decode(c['usage']) if c['usage'] else {}).get('total_tokens',0) or 0 for c in calls),
    'candidate':decode(development['candidate']) if development['candidate'] else None,
    'package_report':decode(package['report']) if package and package['report'] else None,
    'original_score_preserved':after['condition_score']==0,'original_tool_bindings_unchanged':bindings,
    'same_work':case.core.works.owner(goal)['current_goal']==result.get('child_goal'),
    'production_adopted':False,'independent_user_quality_claimed':False}
   write(folder/'result.json',row);rows.append({k:row[k] for k in ('domain','passed','seconds','total_tokens','same_work','original_score_preserved','original_tool_bindings_unchanged')})
   print(json.dumps(rows[-1]),flush=True)
  except Exception:
   (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');rows.append({'domain':domain,'passed':False,'harness_error':True})
   print(json.dumps(rows[-1]),flush=True)
  finally:
   if credential.exists():credential.unlink()
   case.tearDown();write(folder/'cleanup.json',{'temporary_root_removed':not case.root.exists(),'temporary_credential_removed':not credential.exists()})
 summary={'rows':rows,'passed':all(r['passed'] for r in rows),'proxy_after':exchange(dev,'/status'),
  'source_unchanged':all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in frozen.items()),'production_adopted':False}
 write(OUT/'summary.json',summary);print(json.dumps(summary),flush=True)
 if not summary['passed'] or not summary['source_unchanged']:raise SystemExit(1)
if __name__=='__main__':main()
