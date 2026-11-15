"""One-shot, read-only local effect observation; no model calls, scheduler or repair."""
from pathlib import Path
import json,sqlite3,sys,time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.workstation import instance,state
from control.controller_pin import read

def observe():
    root=Path('E:/Jarvis/runtime/user-data');db=sqlite3.connect((root/'state/core.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        rows=db.execute("SELECT seq,data FROM events WHERE kind='learning.repair_return' ORDER BY seq DESC").fetchall()
        seen=set();returns=[]
        for seq,raw in rows:
            v=json.loads(raw);ident=v['development_id']
            if ident in seen:continue
            seen.add(ident);actual=v.get('actual') or {}
            returns.append({'development_id':ident,'status':v['status'],'before_score':v.get('before_score'),
                'after_score':actual.get('condition_score'),'error':v.get('error'),'latest_event_seq':seq})
        trial_counts={status:n for status,n in db.execute("SELECT json_extract(data,'$.status'),count(*) FROM events WHERE kind='learning.validation_finished' AND occurred>=? GROUP BY json_extract(data,'$.status')",(time.time()-86400,))}
        reserved=db.execute("SELECT count(*) FROM events WHERE kind='learning.validation_started' AND occurred>=?",(time.time()-86400,)).fetchone()[0]
        policy=db.execute("SELECT value FROM meta WHERE key='lesson_validation_policy'").fetchone()
        last=db.execute('SELECT COALESCE(max(seq),0) FROM events').fetchone()[0]
        intact=db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:db.close()
    live=instance(18282);application=state(root);controller=read(root)
    return {'observed_at':time.time(),'application':application,'instance':live,'controller_protocol':controller['controller_protocol'],
        'database_integrity_ok':intact,'policy':json.loads(policy[0]) if policy else None,'local_trials_reserved_24h':reserved,
        'local_trials_finished_24h':trial_counts,'latest_repair_returns':returns,'last_event_seq':last,
        'live_build_matches_active':bool(live and live['application_build']==application['active']['build']),
        'scope':'Local operational observation only. No independent-user labels or no-memory control: no causal learning or token-saving claim.',
        'new_model_calls_by_observer':0,'long_term_effect_verified':False}

if __name__=='__main__':
    result=observe();target=Path(sys.argv[1]) if len(sys.argv)>1 else None
    if target:
        with target.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
