"""Read-only ledger and artifact audit for the frozen single native advice pair."""
from pathlib import Path
import json,sqlite3,hashlib,subprocess,time
ROOT=Path('E:/Jarvis/dev');OUT=ROOT/'docs/evidence/advice-pair-20261114/native-r1';DATA=Path('E:/Jarvis/validation/advice-pair-native-20261114-r1/data');HARNESS=OUT.parent/'run_pair.py'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    f=read(OUT/'freeze.json');assert f['execution']=='real-native-model'
    c=sqlite3.connect((DATA/'state/core.sqlite3').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    metrics={};checks={};plans=[]
    for label in ['without-advice','with-advice']:
        r=read(OUT/(label+'.json'));capture=read(OUT/(label+'-dispatch.json'))
        calls=[dict(row) for row in c.execute('SELECT * FROM model_calls WHERE run_id=?',(r['goal_id'],))]
        plan=dict(c.execute('SELECT * FROM goal_plans WHERE id=?',(r['goal_id'],)).fetchone());plans.append(plan)
        context=dict(c.execute('SELECT * FROM goal_context WHERE goal_id=?',(r['goal_id'],)).fetchone())
        task=dict(c.execute('SELECT * FROM tasks WHERE id=?',(r['task_id'],)).fetchone());usage=json.loads(calls[0]['usage'])
        assert usage['reasoning_in_completion'] is False
        total=usage['prompt_tokens']+usage['completion_tokens']+usage['reasoning_tokens'];assert total==usage['total_tokens']
        artifact_checks=[]
        for a in r['saved_artifact_receipts']:
            path=(DATA/a['relative_path']).resolve();assert path.is_relative_to((DATA/'artifacts').resolve())
            payload=path.read_bytes();artifact_checks.append(sha(path)==a['sha256'] and len(payload)==a['bytes'] and json.loads(json.loads(payload)['text'])==f['case']['expected'])
        checks[label]={'single_successful_call':len(calls)==1 and calls[0]['status']=='SUCCEEDED','prompt_digest_matches_actual_ledger':calls[0]['input_digest']==capture['input_digest'],
          'called_after_freeze':calls[0]['created']>=f['frozen_at'],'current_plan_matches_recorded_proposal':json.loads(plan['proposal'])==r['proposal'],
          'task_link_matches':plan['task_id']==task['id']==r['task_id'],'actual_task_succeeded':task['status']=='SUCCEEDED','physical_saved_artifacts_match_gold':bool(artifact_checks) and all(artifact_checks),
          'same_current_ordinary_background':json.loads(context['view'])['facts']==f['contexts'][label]['view']['facts']}
        exposure=r.get('planning_advice',{}).get('message_exposure') if r.get('planning_advice') else None
        if exposure is not None:
            expected_full=read(OUT/'with-advice-dispatch.json')['message_bytes'];expected_base=read(OUT/'without-advice-dispatch.json')['message_bytes']
            checks[label]['new_diagnostic_matches_both_actual_messages']=exposure=={'unit':'message_json_utf8_bytes','full_bytes':expected_full,'without_advice_bytes':expected_base,'added_bytes':expected_full-expected_base}
        metrics[label]={'declared_condition_score':r['completion']['condition_score'],'strict_task_passed':r['passed'],'prompt_tokens':usage['prompt_tokens'],'completion_tokens':usage['completion_tokens'],'reasoning_tokens':usage['reasoning_tokens'],'total_tokens':total,'planning_seconds':r['planning_seconds'],'message_bytes':capture['message_bytes'],'task_cost_units':task['spent'],'model_calls':len(calls),'monetary_cost':None}
    c.close();a=metrics['without-advice'];b=metrics['with-advice']
    requests=[json.loads(p['request']) for p in plans]
    for request in requests:request.pop('request_id')
    shared={'same_goal_input_and_model_request':requests[0]==requests[1],'same_catalog':plans[0]['catalog']==plans[1]['catalog'],'same_routes':plans[0]['routes']==plans[1]['routes'],
      'same_ordinary_background':f['contexts']['without-advice']['view']['facts']==f['contexts']['with-advice']['view']['facts'],
      'same_memory_setting':f['contexts']['without-advice']['enabled']==f['contexts']['with-advice']['enabled']==1,
      'recorded_prompt_diff_is_only_conditional_advice':read(OUT/'summary.json')['only_treatment_changed'],'temporary_credential_absent':not (DATA/'private/development-bridge.dpapi').exists(),
      'frozen_files_match_recorded_commit':all(hashlib.sha256(subprocess.check_output(['git','show',f['source_commit']+':'+name],cwd=ROOT)).hexdigest()==value for name,value in f['source_sha256'].items()),'harness_matches_freeze':sha(HARNESS)==f['harness_sha256']}
    result={'audit_created_at':time.time(),'audit_mode':'recorded source commit and persisted native ledgers; not a new model run','scope':'one operator-authored synthetic '+f['case']['domain']+' pair, same ordinary source background in both groups; not memory-off vs memory-on','sample_pairs':1,'source_commit':f['source_commit'],'metrics':metrics,
      'observed_deltas':{'declared_condition_score':b['declared_condition_score']-a['declared_condition_score'],'prompt_tokens':b['prompt_tokens']-a['prompt_tokens'],'prompt_tokens_percent':(b['prompt_tokens']/a['prompt_tokens']-1)*100,'total_tokens':b['total_tokens']-a['total_tokens'],'total_tokens_percent':(b['total_tokens']/a['total_tokens']-1)*100,'planning_seconds':b['planning_seconds']-a['planning_seconds'],'planning_seconds_percent':(b['planning_seconds']/a['planning_seconds']-1)*100},
      'checks':checks,'shared_checks':shared,'ordinary_background_items_each':len(f['contexts']['with-advice']['view']['facts']),
      'offered_method_count':len(read(OUT/'with-advice.json')['planning_advice']['offered']),
      'interpretation':{'quality_gain':'not observed on this one declared-condition task','token_gain':'negative; treatment used more tokens on this pair','latency_gain':'one observed faster treatment; no stable benefit claimed','causal_generalization':None,'longitudinal_benefit':None,'automatic_promotion_allowed':False,'production_default_expansion_allowed':False},
      'not_measured':f['not_measured'],'passed_audit':all(shared.values()) and all(all(row.values()) for row in checks.values())}
    (OUT/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed_audit':result['passed_audit'],'metrics':metrics,'observed_deltas':result['observed_deltas']},ensure_ascii=False));assert result['passed_audit']
if __name__=='__main__':main()
