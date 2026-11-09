"""Re-evaluate the same immutable real model outputs after a host-only fix.

No new model call; this is repair regression, not a fresh unseen language test.
"""
from datetime import datetime
import hashlib,json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT),str(HERE)]
from evaluate import fixture,score,summary


if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=False)
    cases=json.loads((HERE/'cases.json').read_text(encoding='utf-8'));live=json.loads((HERE/'live-result.json').read_text(encoding='utf-8'))
    reference=datetime.fromisoformat(cases['reference_utc'].replace('Z','+00:00')).timestamp()
    byid={c['id']:c for c in cases['cases']};rows=[]
    for outcome in live['outcomes']:
        case=byid[outcome['id']];root=work/case['id'];root.mkdir();chat,target=fixture(root,case,reference)
        try:envelope=json.loads(outcome.get('text') or '') if outcome['status']=='SUCCEEDED' else {}
        except ValueError:envelope={}
        rows.append(score(root,chat,case,envelope,reference))
    totals={}
    for outcome in live['outcomes']:
        for key,value in outcome['usage'].items():
            if type(value) is int:totals[key]=totals.get(key,0)+value
    report={'scope':'same real outputs after host fix; not new model calls or unseen validation',
        'model_calls':0,'live_result_sha256':hashlib.sha256((HERE/'live-result.json').read_bytes()).hexdigest(),
        'source_sha256':hashlib.sha256((ROOT/'modules/task_resource/commitment_intent.py').read_bytes()).hexdigest(),
        'summary':summary(rows,[byid[r['id']] for r in rows]),'rows':rows,'provider_reported_usage_totals':totals}
    (HERE/'live-replay-after.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'summary':report['summary'],'usage':totals}))
