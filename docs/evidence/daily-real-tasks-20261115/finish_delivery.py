"""Resume only admission after a rejected operator payload; retain every old call."""
import hashlib,json,sqlite3,time
from session import Client,DATA,OUT,PRIVATE,route,write

def finish(client,label,ident,expected):
    assert not (OUT/(label+'-task-start.json')).exists(),'Inspect persisted task before re-execution'
    now=client.call('/api/goals',{'action':'detail','id':ident},log=False);plan=now['plan']
    assert plan['status']=='REVIEW' and not plan['task_id']
    assert len(plan['proposal']['steps'])==1 and plan['proposal']['steps'][0]['capability']=='plugin.reviewed-materials.v1'
    assert json.loads(plan['proposal']['input_text'])=={'markdown':expected}
    acceptance={'coverage':'complete','requirements':[{'id':'reviewed-content','text':'逐字交付已审阅的当前材料；不代表学习者能力或健康改善','kind':'literal','criterion_ids':['exact-delivery']}],
      'criteria':[{'id':'exact-delivery','step_id':'step-1','check':'text_equals','expected':expected}]}
    write(OUT/(label+'-acceptance-valid.json'),{'goal_id':ident,'acceptance':acceptance,'content_review':'operator supplied separately; literal delivery condition only'})
    result=client.call('/api/goals',{'action':'approve_and_run','id':ident,'revision':plan['revision'],'acceptance':acceptance,'budget_limit':6})
    write(OUT/(label+'-task-start.json'),{'goal_id':ident,'task_id':result['task_id']})
    for _ in range(90):
        after=client.call('/api/goals',{'action':'detail','id':ident},log=False)
        if after['task']['status'] in ('SUCCEEDED','FAILED','CANCELLED'):break
        time.sleep(1)
    write(PRIVATE/(label+'-task-final.json'),after)
    receipt=next((a['result'] for a in after['actions'] if a['step_id']=='deliver' and a['status']=='CONFIRMED'),None)
    actual=next((a['result']['text'] for a in after['actions'] if a['step_id']=='step-1' and a['status']=='CONFIRMED'),None)
    if actual is not None:(OUT/(label+'-delivered.txt')).write_text(actual,encoding='utf-8')
    summary={'goal_id':ident,'task_id':result['task_id'],'task_status':after['task']['status'],'completion_state':after['completion']['state'],
      'condition_score':after['completion']['condition_score'],'actual_matches_reviewed':actual==expected,'delivery_receipt':receipt,
      'actual_sha256':hashlib.sha256(actual.encode()).hexdigest() if actual is not None else None,
      'generation':after['plan']['generation'],'original_history_preserved':bool((after.get('context') or {}).get('history')),
      'operator_assisted':True,'automatic_repair_return':False,'proficiency_or_health_outcome_score':None}
    write(OUT/(label+'-task-result.json'),summary);print(json.dumps(summary,ensure_ascii=False),flush=True)

def main():
    client=Client();ident=json.loads((OUT/'english-plan-start.json').read_text())['goal_id']
    db=sqlite3.connect((DATA/'state/core.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:absent=not db.execute('SELECT 1 FROM grants WHERE id=?',(ident+'-execute',)).fetchone()
    finally:db.close()
    assert absent
    write(OUT/'operator-admission-failure.json',{'error':'acceptance_invalid','cause':'operator used criteria rather than kind/criterion_ids in requirement object','prior_payload':'english-acceptance-frozen.json','admitted_execute_grant_absent':absent,'retry_scope':'correct request schema only; no new model calls, no condition relaxed','counts_as_operator_intervention':True})
    finish(client,'english',ident,(OUT/'english-actual.txt').read_text(encoding='utf-8').removesuffix('\n'))
    correction=json.loads((OUT/'materials-correction-result.json').read_text());assert correction['source_gate_passed']
    text=json.loads(correction['reply'])['document'];(OUT/'materials-corrected.txt').write_text(text,encoding='utf-8')
    assert not (OUT/'materials-goal-start.json').exists()
    request={'request_id':'daily-real-materials-delivery-20261115-r1','goal':'将已通过来源核对的日常英语和健康资料卡逐字保存为当前结果。不要改写正文或扩充健康结论；这是来源忠实交付，不是诊断或学习能力评分。','input_text':json.dumps({'markdown':text},ensure_ascii=False),**route()}
    result=client.call('/api/goals',{'action':'create','request':request,'context':{'scope':'personal','enabled':False,'chat_id':'','turn_id':''}});mid=result['id']
    write(OUT/'materials-goal-start.json',{'goal_id':mid,'source_turn':correction['request_id'],'source_chat':correction['chat_id'],'operator_linked_after_source_correction':True})
    client.call('/api/goals/plan',{'id':mid,'retry_unknown':False})
    for _ in range(60):
        now=client.call('/api/goals',{'action':'detail','id':mid},log=False)
        if now['plan']['status'] not in ('NEW','PLANNING'):break
        time.sleep(2)
    finish(client,'materials',mid,text)

if __name__=='__main__':main()
