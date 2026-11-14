"""One consistent budget-ledger backup; does not restore or authorize anything."""
from pathlib import Path
import sys,json,sqlite3,hashlib,time
ROOT=Path('E:/Jarvis/dev');sys.path.insert(0,str(ROOT))
from adapters.development_bridge import exchange
base=ROOT/'docs/evidence/advice-pair-20261114';dest=Path('D:/Jarvis-Recovery/budgets/2026-11-15-r1').resolve()
assert dest.is_relative_to(Path('D:/Jarvis-Recovery/budgets').resolve());dest.mkdir(parents=True,exist_ok=False)
source=Path('E:/Jarvis/runtime/user-data/development/bridge.sqlite3');target=dest/'bridge.sqlite3'
src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);dst=sqlite3.connect(target)
try:src.backup(dst);assert dst.execute('pragma integrity_check').fetchone()[0]=='ok'
finally:src.close();dst.close()
c=sqlite3.connect(target.as_uri()+'?mode=ro',uri=True);now=time.time();total=c.execute('select count(*) from calls').fetchone()[0];current=c.execute('select count(*) from calls where created>?',(now-86400,)).fetchone()[0]
expected=json.loads((base/'bridge-correlation.json').read_text())['matches'];study={r['bridge_call_id']:c.execute('select hash,status from calls where id=?',(r['bridge_call_id'],)).fetchone()==(r['request_body_sha256'],'SUCCEEDED') for r in expected};assert all(study.values())
statuses=dict(c.execute('select status,count(*) from calls group by status'));c.close()
status=exchange(ROOT/'user-data','/status');assert status['daily_call_limit']==64
sha=hashlib.sha256(target.read_bytes()).hexdigest()
report={'scope':'latest local usage/cached-receipt ledger increment only; no recovery, grant renewal or anti-rollback guarantee','destination':str(dest),'snapshot_at':now,'file':'bridge.sqlite3','bytes':target.stat().st_size,'sha256':sha,'sqlite_integrity_ok':True,'all_rows':total,'rows_in_24h_at_snapshot':current,'status_counts':statuses,'all_six_study_receipts_in_backup':all(study.values()),'policy_daily_limit':64,'restore_requires_current_authority_and_gap_review':True,'unknown_or_missing_usage_must_not_be_zeroed':True,'passed':True}
(dest/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(base/'budget-disaster-copy.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');assert hashlib.sha256(target.read_bytes()).hexdigest()==sha
print(json.dumps({'passed':True,'destination':str(dest),'rows_in_24h':current,'all_six_study_receipts':all(study.values())},ensure_ascii=False))
