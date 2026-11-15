"""Explicit operator-assisted return to the original goal through normal admission."""
import hashlib,json,time
from session import Client,OUT,PRIVATE,route,write

def main():
    assert not (OUT/'english-rejoin-start.json').exists(),'Read recorded progress before resuming any action'
    client=Client();start=json.loads((OUT/'delivery-tool-start.json').read_text());dev=start['development_id']
    detail=client.call('/api/development',{'action':'detail','id':dev},log=False)
    assert (detail['run']['status'],detail['run']['phase'],detail['run']['error'])==('WAITING','verified','review_required')
    candidate=json.loads(detail['run']['candidate']);assert len(candidate['files'])==1
    # Reviewed here before adoption: json.loads and string type checks only;
    # exact output, no executable text eval, file, network or other effects.
    expected='import json\n\n\ndef run(text: str) -> str:\n    payload = json.loads(text)\n    if not isinstance(payload, dict):\n        raise ValueError("Expected a JSON object")\n    if "markdown" not in payload:\n        raise ValueError("Missing \'markdown\' field")\n    content = payload["markdown"]\n    if not isinstance(content, str):\n        raise ValueError("\'markdown\' field must be a string")\n    return content\n'
    assert candidate['files'][0]=={'path':'main.py','content':expected},'Candidate differs from explicitly reviewed code'
    ident=json.loads((OUT/'english-plan-start.json').read_text())['goal_id']
    source=(OUT/'english-actual.txt').read_text(encoding='utf-8').removesuffix('\n')
    original=client.call('/api/goals',{'action':'detail','id':ident},log=False)
    write(OUT/'english-rejoin-start.json',{'goal_id':ident,'development_id':dev,'approved_package':detail['run']['release_id'],
        'candidate_sha256':hashlib.sha256(expected.encode()).hexdigest(),'original_goal_status':original['plan']['status'],
        'material_sha256':hashlib.sha256(source.encode()).hexdigest(),'operator_assisted':True,'automatic_repair_return':False,
        'review':'material addresses the three requested scenarios; teaching notice explicitly fictional; user has not answered or provided audio, so proficiency unscored',
        'scoring':'complete exact-delivery conditions only, separate from English teaching quality and mastery'})
    client.call('/api/development',{'action':'approve','id':dev,'package_id':detail['run']['release_id']})
    client.call('/api/development-runner',{'id':dev,'network_enabled':False,'retry_unknown':False})
    for _ in range(60):
        detail=client.call('/api/development',{'action':'detail','id':dev},log=False)
        if detail['run']['status'] in ('SUCCEEDED','FAILED','CANCELLED'):break
        time.sleep(1)
    assert detail['run']['status']=='SUCCEEDED',detail['run']['error']
    write(OUT/'delivery-tool-adopted.json',{'run_id':dev,'status':detail['run']['status'],'package_id':detail['run']['release_id'],'calls':detail['calls']})
    # Keep the original objective and ID. The ordinary amendment ledger retains
    # the first unresolved plan and revokes its old planning grant.
    client.call('/api/goals',{'action':'amend','id':ident,'revision':original['plan']['revision'],'goal':original['plan']['request']['goal'],
      'input_text':json.dumps({'markdown':source},ensure_ascii=False)})
    client.call('/api/goals/plan',{'id':ident,'retry_unknown':False})
    for _ in range(60):
        now=client.call('/api/goals',{'action':'detail','id':ident},log=False)
        if now['plan']['status'] not in ('NEW','PLANNING'):break
        time.sleep(2)
    write(PRIVATE/'english-replan.json',now)
    plan=now['plan'];proposal=plan['proposal']
    assert plan['status']=='REVIEW' and len(proposal['steps'])==1 and proposal['steps'][0]['capability']=='plugin.reviewed-materials.v1'
    assert json.loads(proposal['input_text'])=={'markdown':source},'Planner changed reviewed content; retain result for correction'
    acceptance={'coverage':'complete','requirements':[{'id':'reviewed-content','text':'逐字交付已独立审阅的三场景英语练习材料；不是学习者掌握评分','kind':'literal','criterion_ids':['exact-delivery']}],
      'criteria':[{'id':'exact-delivery','step_id':'step-1','check':'text_equals','expected':source}]}
    write(OUT/'english-acceptance-frozen.json',{'goal_id':ident,'acceptance':acceptance,'quality_review_is_operator_supplied':True})
    accepted=client.call('/api/goals',{'action':'approve_and_run','id':ident,'revision':plan['revision'],'acceptance':acceptance,'budget_limit':6})
    write(OUT/'english-task-start.json',{'goal_id':ident,'task_id':accepted['task_id']})
    for _ in range(60):
        result=client.call('/api/goals',{'action':'detail','id':ident},log=False)
        if result['task']['status'] in ('SUCCEEDED','FAILED','CANCELLED'):break
        time.sleep(1)
    write(PRIVATE/'english-task-final.json',result)
    summary={'goal_id':ident,'task_id':accepted['task_id'],'status':result['task']['status'],'completion_state':result['completion']['state'],
        'condition_score':result['completion']['condition_score'],'same_goal_id':ident==original['plan']['id'],
        'generation':result['plan']['generation'],'original_plan_retained':bool(result['context']['history']),
        'operator_assisted':True,'automatic_repair_return':False,'oral_proficiency_score':None,'learning_gain':None}
    write(OUT/'english-task-result.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
