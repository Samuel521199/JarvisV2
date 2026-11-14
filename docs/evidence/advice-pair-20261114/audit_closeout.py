"""Bounded read-only phase closeout; no model request or application adoption."""
from pathlib import Path
import json,hashlib,sqlite3,subprocess,time,urllib.request,sys
ROOT=Path('E:/Jarvis/dev');OUT=ROOT/'docs/evidence/advice-pair-20261114';sys.path.insert(0,str(ROOT))
from tools.workstation import instance,state
from control.controller_pin import read
from adapters.development_bridge import exchange

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    recovery=json.loads((OUT/'service-recovery-r1/result.json').read_text());daily=Path('E:/Jarvis/runtime/user-data');live=instance(18282);dev=instance(18283);pin=read(daily);status=exchange(ROOT/'user-data','/status')
    q=json.loads((OUT/'independent-package/result.json').read_text());package=Path(q['isolated_data'])/'deployment/packages'/q['build'];assert q['passed']
    sources={name:(ROOT/name).read_bytes()==(package/name).read_bytes() for name in ['host/planning_advice.py','host/goals.py','apps/workbench/planning-advice.js']};assert all(sources.values())
    with urllib.request.urlopen('http://127.0.0.1:18283/planning-advice.js',timeout=5) as response:asset=response.read()
    checks={'daily_same_boot_since_recovery':live==recovery['after']['daily'],'active_application_still_018_epoch10':state(daily)['active']['version']=='0.1.8' and state(daily)['epoch']==10,'development_online':bool(dev),
      'controller_same':pin==recovery['after']['controller'],'development_asset_current':hashlib.sha256(asset).hexdigest()==sha(ROOT/'apps/workbench/planning-advice.js'),
      'same_approved_proxy':status['build_id']=='30b79127b81e04a57cdc8aae76f607ea38b499b3fa4d92abf0020700e17848bc','daily_limit_still_64':status['daily_call_limit']==64,'production_memory_not_exposed':status['production_memory_exposed'] is False,'no_external_tools_exposed':status['external_tools_exposed'] is False}
    controller_backup=Path('D:/Jarvis-Recovery/controllers/2026-11-14-r3');m=json.loads((controller_backup/'verification.json').read_text());backup={name:sha(controller_backup/name)==meta['sha256'] for name,meta in m['files'].items()};assert all(backup.values())
    budget=json.loads((OUT/'budget-disaster-copy.json').read_text());budget_file=Path(budget['destination'])/budget['file'];assert sha(budget_file)==budget['sha256']
    c=sqlite3.connect(budget_file.as_uri()+'?mode=ro',uri=True);assert c.execute('pragma integrity_check').fetchone()[0]=='ok';c.close()
    result={'scope':'post-recovery point-in-time availability, unchanged candidate files and independent disk readback; not continuous uptime or full business restore','checked_at':time.time(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'checks':checks,'candidate_runtime_sources_match':sources,'controller_backup_hashes':backup,'budget_backup_hash_matches':True,'daily_instance':live,'development_instance':dev,'proxy_status':status,'passed':all(checks.values())}
    (OUT/'final-live-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'passed':result['passed'],'checks':checks},ensure_ascii=False));assert result['passed']
if __name__=='__main__':main()
