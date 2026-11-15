"""Real proxy-coded repairs on synthetic fixtures; never adopts daily or a tool."""
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
 from test_lesson_repair import LessonRepairTests
 from sdk.protocol import decode
 OUT.mkdir(exist_ok=False)
 dev=ROOT/'user-data';before=exchange(dev,'/status');catalog=exchange(dev,'/catalog')['catalog']
 assert before['daily_call_limit']==64 and before['daily_call_limit']-before['calls_in_24h']>=12
 provider=catalog['default_provider'];assert provider in before['allowed_providers']
 catalog.update(automatic_fallback=False,fallback_order=[provider])
 route={'provider':provider,'model':catalog['providers'][provider]['model'],'reasoning':'default'}
 frozen={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('host/core.py','host/lesson_repair.py','host/completion.py','modules/task_resource/lesson_repairs.py')}
 write(OUT/'protocol.json',{'scope':'operator-authored synthetic failure fixtures, real native model plan/code, restricted Worker; not independent user work or long-term learning',
  'domains':['notes','practice','quote'],'proxy_before':before,'route':route,'max_calls_per_run':4,'max_candidate_attempts':2,
  'fallback':False,'retry_unknown':False,'automatic_tool_publication':False,'source_sha256':frozen,
  'prediction':'Each corrected tool should pass four public and four unseen-by-coder synthetic inputs; failure must remain visible. No token-saving or general-quality gain predicted.'})
 rows=[]
 for domain in ('notes','practice','quote'):
  folder=OUT/domain;folder.mkdir();case=LessonRepairTests('test_three_repairs_pass_hidden_cases_wait_for_review_and_deliver_separately')
  with patch('test_goal_plans.fixture',return_value=catalog):case.setUp()
  credential=case.root/'private/development-bridge.dpapi'
  try:
   assert case.root.resolve().is_relative_to(Path('E:/Jarvis/validation/temp'))
   _,tid=case.failed(domain);old_bindings=case.core.tasks.get(tid)['bindings']
   original=refresh(case.core,tid)['learning_candidate']
   for name in ('config/development.json','private/development-bridge.dpapi'):
    target=case.root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dev/name,target)
   draft=command(case.root,{'action':'lesson_repair_prepare','id':tid})
   ident=command(case.root,{'action':'lesson_repair_begin','id':tid,'key':draft['key'],'fingerprint':draft['fingerprint'],'reviewed':True,'routes':{'plan':[route],'code':[route]}})['id']
   spec=case.core.development.get(ident)['spec']
   write(folder/'freeze.json',{'spec':spec,'original_condition_score':original['condition_score'],'original_trial':original['validation']['trial'],
    'synthetic_only':True,'original_input_sent_to_repair_model':False,'evaluation_inputs_hidden_from_coder':True,'proxy_before':exchange(dev,'/status')})
   assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in frozen.items())
   current=exchange(dev,'/status');assert current['daily_call_limit']==64 and 64-current['calls_in_24h']>=4
   started=time.monotonic();result=case.core.develop(ident,network_enabled=True,retry_unknown=False)
   calls=case.core.db.all('SELECT phase,status,error,model,usage FROM model_calls WHERE run_id=? ORDER BY created',(ident,))
   package=case.core.packages.get(result['release_id']) if result['release_id'] else None
   original_unchanged=all(case.core.registry.binding(cap)==binding for cap,binding in old_bindings.items())
   projection=refresh(case.core,tid)['learning_candidate']
   row={'domain':domain,'passed':result['phase']=='verified' and result['error']=='review_required' and original_unchanged,
    'seconds':time.monotonic()-started,'status':result['status'],'phase':result['phase'],'error':result['error'],
    'candidate_attempt':result['attempt'],'calls':calls,'total_tokens':sum((decode(c['usage']) if c['usage'] else {}).get('total_tokens',0) or 0 for c in calls),
    'original_bindings_unchanged':original_unchanged,'original_failed_trial_preserved':projection['validation']['trial']['result']['status']=='FAILED',
    'repair_link_matches':projection['repair']['id']==ident,'new_tool_published':case.core.packages.slot(spec['capability']) is not None,
    'package_report':decode(package['report']) if package and package['report'] else None,
    'candidate':decode(result['candidate']) if result['candidate'] else None,'production_adopted':False}
   assert not row['new_tool_published'];write(folder/'result.json',row);rows.append(row)
   print(json.dumps({k:row[k] for k in ('domain','passed','status','phase','error','total_tokens','seconds')}),flush=True)
  except Exception:
   (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
   rows.append({'domain':domain,'passed':False,'harness_error':True});print(json.dumps(rows[-1]),flush=True)
  finally:
   if credential.exists():credential.unlink()
   case.tearDown();write(folder/'cleanup.json',{'temporary_root_removed':not case.root.exists(),'temporary_bridge_credential_removed':not credential.exists()})
 summary={'rows':[{k:v for k,v in row.items() if k not in ('candidate','package_report')} for row in rows],
  'all_passed':all(r['passed'] for r in rows),'proxy_after':exchange(dev,'/status'),
  'source_unchanged':all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in frozen.items()),
  'production_adopted':False,'quality_gain_claimed':False,'token_savings_claimed':False}
 write(OUT/'summary.json',summary);print(json.dumps({'all_passed':summary['all_passed'],'source_unchanged':summary['source_unchanged']}),flush=True)
 if not summary['all_passed']:raise SystemExit(1)

if __name__=='__main__':main()
