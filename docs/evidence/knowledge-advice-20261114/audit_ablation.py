"""Recheck frozen results against native read-only fixture databases; no model calls."""
from pathlib import Path
import hashlib,importlib.util,json,sqlite3,sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from sdk.protocol import canonical,decode,digest


def main(folder,work):
    frozen=decode((folder/'frozen.json').read_text(encoding='utf-8'))
    for name,sha in frozen['source_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen relevant code changed')
    script=Path(__file__).with_name('run_ablation.py')
    spec=importlib.util.spec_from_file_location('frozen_ablation',script);trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)
    data=work/'data';native=sqlite3.connect((data/'state/dialogue.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
    native.row_factory=sqlite3.Row;rows=[]
    try:
        for arm in frozen['arms']:
            started=decode((folder/(arm+'.started.json')).read_text(encoding='utf-8'))
            row=decode((folder/(arm+'.result.json')).read_text(encoding='utf-8'))
            if row['freeze_digest']!=digest(frozen) or started['freeze_digest']!=digest(frozen):raise ValueError('Freeze binding differs')
            turn=dict(native.execute('SELECT * FROM turns WHERE id=?',(started['request_id'],)).fetchone())
            request=decode(turn['request']);action=decode(turn['assistant_action'])
            if hashlib.sha256(request['text'].encode()).hexdigest()!=started['prompt_digest']:raise ValueError('Actual model input changed')
            if 'A withdrawn synthetic observation, unavailable to model context.' in request['text']:raise ValueError('Withdrawn body was disclosed')
            if request['memory_enabled'] or not request['assistant_mode']:raise ValueError('Controlled assembly mode differs')
            if turn['status']!=row['status'] or turn['reply']!=row['reply'] or action['kind']!=row['action_kind']:raise ValueError('Native outcome differs')
            assessment=trial.grade(row['reply'],frozen['cases'])
            if assessment!=row['assessment']:raise ValueError('Assessment cannot be reproduced')
            rows.append({'arm':arm,'correct_cases':sum(c['passed'] for c in assessment['rows']),'flow_chat_only':action['kind']=='chat',
                'background_bytes':row['background_bytes'],'prompt_tokens':row['usage']['prompt_tokens'],
                'total_tokens':row['usage']['total_tokens'],'seconds':row['seconds']})
    finally:native.close()
    core=sqlite3.connect((data/'state/core.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
    try:tasks=core.execute('SELECT count(*) FROM tasks').fetchone()[0]
    finally:core.close()
    commitments=0;path=data/'state/commitments.sqlite3'
    if path.exists():
        db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
        try:commitments=db.execute('SELECT count(*) FROM commitments').fetchone()[0]
        finally:db.close()
    selection=decode((folder/'selection.json').read_text(encoding='utf-8'))
    accepted={k:len(v['methods']) for k,v in selection['by_case'].items()}
    if accepted!={'same-conditions':1,'price-basis-reversed':0,'objective-changed':0,'withdrawn-history':0}:raise ValueError('Conditional exposure gate differs')
    by={r['arm']:r for r in rows}
    result={'native_results_verified':True,'grader_reproduced':True,'tasks_created':tasks,'commitments_created':commitments,
        'all_flows_chat_only':all(r['flow_chat_only'] for r in rows),'accepted_advice_by_case':accepted,
        'rows':rows,'provider_calls':5,'reported_total_tokens':sum(r['total_tokens'] for r in rows),
        'ABL-3_vs_ABL-2':{'background_bytes_change':by['ABL-3']['background_bytes']/by['ABL-2']['background_bytes']-1,
            'prompt_tokens_change':by['ABL-3']['prompt_tokens']/by['ABL-2']['prompt_tokens']-1,
            'total_tokens_change':by['ABL-3']['total_tokens']/by['ABL-2']['total_tokens']-1},
        'ABL-4_vs_ABL-3_total_tokens_change':by['ABL-4']['total_tokens']/by['ABL-3']['total_tokens']-1,
        'ABL-3_vs_ABL-0_total_tokens_change':by['ABL-3']['total_tokens']/by['ABL-0']['total_tokens']-1,
        'full_cost':None,'quality_gain_demonstrated':False,'formal_learning_acceptance':False,
        'temporary_bridge_credential_removed':not (data/'private/development-bridge.dpapi').exists(),
        'limits':frozen['limits']}
    result['passed']=not tasks and not commitments and result['all_flows_chat_only'] and result['temporary_bridge_credential_removed']
    with (folder/'audit.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ['native_results_verified','reported_total_tokens','quality_gain_demonstrated','passed']}))


if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
