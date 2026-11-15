"""Read-only task-trial accounting from original ledgers; no scores or grants written.

Select goal_ids, turn_ids and separately attributable setup_run_ids in a JSON
manifest. Include failed/unknown calls and all planning generations. Dialogue
attempts are counted instead of turn totals; proxy mirrors are never added.
"""
import argparse,json,re,sqlite3,time
from pathlib import Path


def token_summary(calls):
    totals={key:0 for key in ('prompt_tokens','completion_tokens','reasoning_tokens','total_tokens')}
    missing={key:[] for key in totals}
    seen=set()
    for call in calls:
        ident=(call['ledger'],call['id'])
        if ident in seen:raise ValueError('Duplicate call receipt')
        seen.add(ident);usage=call.get('usage') or {}
        if not isinstance(usage,dict):raise ValueError('Malformed usage receipt')
        for key in totals:
            value=usage.get(key)
            if type(value) is int and value>=0:totals[key]+=value
            else:missing[key].append(list(ident))
    return {'calls':len(calls),'reported_tokens':totals,'missing_receipts_by_metric':missing,
            'total_tokens_complete':not missing['total_tokens'],'total_tokens':totals['total_tokens'] if not missing['total_tokens'] else None,
            'reasoning_added_to_total':False,'zero_calls':not calls}


def connection(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');return db


def observe(root,selection):
    if selection.get('schema')!=1:raise ValueError('Unknown trial selection')
    selected=set(selection.get('goal_ids',[]));turns=set(selection.get('turn_ids',[]));setup=set(selection.get('setup_run_ids',[]))
    if any(not isinstance(v,str) or not v for v in selected|turns|setup):raise ValueError('Invalid ledger ID')
    db=connection(Path(root)/'state/core.sqlite3')
    try:
        goals={r['id']:dict(r) for r in db.execute('SELECT id,status,task_id,error FROM goal_plans')}
        if selected-set(goals):raise ValueError('Unknown selected goal')
        revisions=[dict(r) for r in db.execute('SELECT goal_id,parent_goal FROM work_revisions')]
        events=[json.loads(r[0]) for r in db.execute("SELECT data FROM events WHERE kind IN ('learning.repair_return','learning.repair_created') ORDER BY seq")]
        runs=set();changed=True
        while changed:
            old=(len(selected),len(runs));task_ids={goals[i]['task_id'] for i in selected if goals[i]['task_id']}
            selected.update(r['goal_id'] for r in revisions if r['parent_goal'] in selected)
            for event in events:
                if event.get('source_task') in task_ids:
                    if event.get('development_id'):runs.add(event['development_id'])
                    if event.get('child_goal'):selected.add(event['child_goal'])
            if selected-set(goals):raise ValueError('Broken linked goal; do not report a complete trial')
            changed=old!=(len(selected),len(runs))
        for row in db.execute('SELECT goal_id,development_id FROM goal_growth'):
            if row['goal_id'] in selected and row['development_id']:runs.add(row['development_id'])
        if setup and setup-{r[0] for r in db.execute('SELECT id FROM development_runs')}:raise ValueError('Unknown setup development')
        calls=[];shared=[]
        for row in db.execute('SELECT id,run_id,phase,status,error,usage FROM model_calls ORDER BY created,id'):
            value=dict(row);run=value['run_id']
            owner=next((g for g in selected if re.fullmatch(re.escape(g)+r'(?:-draft|(?:-return)?(?:-g\d+)?)',run)),None)
            if not owner and run not in runs|setup:continue
            value.update(ledger='core.model_calls',usage=json.loads(value['usage']) if value['usage'] else None)
            (shared if run in setup and run not in runs and not owner else calls).append(value)
        scores=[]
        for ident in sorted(selected):
            row=goals[ident];record=db.execute('SELECT body,checked FROM task_completion WHERE task_id=?',(row['task_id'],)).fetchone() if row['task_id'] else None
            value=json.loads(record['body']) if record else {}
            scores.append({**row,'condition_score':value.get('condition_score'),'completion_state':value.get('state'),'checked':record['checked'] if record else None,
                           'scope':'stored completion snapshot; not a fresh source revalidation or a proficiency/health score'})
    finally:db.close()
    if turns:
        db=connection(Path(root)/'state/dialogue.sqlite3')
        try:
            if turns-{r[0] for r in db.execute('SELECT id FROM turns')}:raise ValueError('Unknown selected dialogue turn')
            for row in db.execute('SELECT id,turn_id,status,error,usage FROM attempts ORDER BY id'):
                if row['turn_id'] in turns:
                    value=dict(row);value.update(ledger='dialogue.attempts',usage=json.loads(value['usage']) if value['usage'] else None);calls.append(value)
        finally:db.close()
    return {'schema':1,'observed_at':time.time(),'goal_ids':sorted(selected),'turn_ids':sorted(turns),'scores':scores,
            'work_calls':calls,'work_tokens':token_summary(calls),'shared_setup_calls':shared,'shared_setup_tokens':token_summary(shared),
            'interventions':selection.get('interventions'),'interventions_source':'explicit operator record; not inferred from API request count',
            'monetary_cost':None,'monetary_cost_reason':'token receipts are not invoices','codex_and_web_tokens_included':False,
            'proxy_mirrors_counted':False,'writes_or_dispatches':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data-root',type=Path,required=True);parser.add_argument('--selection',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=observe(args.data_root,json.loads(args.selection.read_text(encoding='utf-8')))
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'output':str(args.output),'work':result['work_tokens'],'setup':result['shared_setup_tokens']},ensure_ascii=False))

if __name__=='__main__':main()
