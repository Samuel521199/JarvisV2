"""Summarize durable public QA receipts without making another model request."""
import argparse
from collections import Counter,defaultdict
import json
from tools.eval_memory_quality import OUT,CACHE


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--variant',default='baseline');args=parser.parse_args()
    import re
    if not re.fullmatch('[a-z0-9-]{1,40}',args.variant):parser.error('Invalid variant')
    base=OUT if args.variant=='baseline' else OUT/args.variant
    cache=CACHE if args.variant=='baseline' else CACHE/args.variant
    frozen=json.loads((base/'frozen.json').read_text(encoding='utf-8'));rows=[];cost=defaultdict(float);missing=0
    for ident in frozen['subset']:
        data=json.loads((cache/(ident+'.input.json')).read_text(encoding='utf-8'))
        allowed={r['id'] for r in data['evidence']}|{r.get('evidence',{}).get('chunk_id') for r in data['evidence']}
        reference=json.loads((cache/(ident+'.reference.json')).read_text(encoding='utf-8'))
        for repeat in range(3):
            pair=[]
            for stage in ('answer','judge'):
                path=base/'answers'/f'{ident}-{repeat}.{stage}.json'
                if not path.exists():missing+=1;pair.append({});continue
                record=json.loads(path.read_text(encoding='utf-8'));pair.append(record)
                estimate=record.get('cost_estimate',{})
                if isinstance(estimate.get('amount'),(int,float)):cost[estimate['currency']]+=estimate['amount']
                else:cost['unknown_calls']+=1
            answer,judge=pair;value=answer.get('output',{});verdict=judge.get('output',{})
            valid=(isinstance(value,dict) and isinstance(value.get('answer'),str) and type(value.get('abstain')) is bool
                   and isinstance(value.get('citations'),list) and all(isinstance(x,str) and x in allowed for x in value['citations'])
                   and (value['abstain'] or bool(value['citations'])))
            rows.append({'id':ident,'repeat':repeat,'type':reference['type'],'no_answer':ident.endswith('_abs'),
                         'correct':verdict.get('correct') is True,'supported':verdict.get('supported') is True,
                         'citation_schema_valid':valid,'answer_status':answer.get('status'),'judge_status':judge.get('status')})
    counts=Counter(r['type'] for r in rows)
    report={'cases':len(frozen['subset']),'repetitions_per_case':3,'responses':len(rows),'missing_receipts':missing,
            'completed_judgments':sum(r['judge_status']=='SUCCEEDED' for r in rows),
            'unknown_judgments':sum(r['judge_status'] in {'UNKNOWN','DISPATCHING'} for r in rows),
            'invalid_judgments':sum(r['judge_status']=='INVALID' for r in rows),
            'judgment_statuses':dict(Counter(r['judge_status'] for r in rows)),
            'correct':sum(r['correct'] for r in rows),'supported_by_model_judge':sum(r['supported'] for r in rows),
            'citation_schema_valid':sum(r['citation_schema_valid'] for r in rows),
            'by_type':{typ:{'responses':n,'correct':sum(r['correct'] for r in rows if r['type']==typ)} for typ,n in counts.items()},
            'no_answer':{'responses':sum(r['no_answer'] for r in rows),'correct':sum(r['correct'] for r in rows if r['no_answer'])},
            'cost_estimate':dict(cost),'rows':rows,'official_score':False,'acceptance_passed':False,
            'limitations':['English public development probe, not source-disjoint holdout',
                           'Automatic separate model judge, not human adjudication',
                           'Repeated generations on 30 questions are not 90 independent questions',
                           'Prices come from configured profiles, not the provider invoice']}
    (base/'answer-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
