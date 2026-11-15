"""Operator-identified real errors, corrected using the existing source gate."""
import json,time,sqlite3
from session import Client,OUT,PRIVATE,DATA,route,write

def main():
    before=json.loads((OUT/'materials-dialogue-start.json').read_text());client=Client()
    assert not (OUT/'materials-correction-start.json').exists(),'Observe existing correction, no blind replay'
    facts=[
      'WHO资料指出：任何量的身体活动好过完全不活动，应减少久坐。这里的“量”不能改写为“任何强度都适合个人”。来源：https://www.who.int/news-room/fact-sheets/detail/physical-activity/ ，核对日期2026-11-15。',
      'British Council提供A1至B2的日常及工作沟通口语资源。资源分级不代表已经测定用户英语等级。来源：https://learnenglish.britishcouncil.org/free-resources/speaking ，核对日期2026-11-15。',
      '用户已明确：工作20年，英语重点是生活交流、日常沟通和工作资料；个人健康也是关注方向。实际英语水平、录音表现及个人健康情况未提供。']
    plans=['后续根据用户真实作答调整英语练习；不把文字材料交付当作口语提升，不依据上述人群资料作个人诊断。']
    audit={'scope':'post-hoc semantic review of actual daily response, not a predeclared independent quality score',
      'observed_errors':['amount of activity changed to any intensity','confirmed use cases described as unconfirmed'],
      'operator_interventions':[{'actor':'codex_operator','kind':'semantic_review_and_corrective_instruction','count':1}],
      'original_reply_preserved':True,'automatic_failure_detection_claimed':False,
      'correction_gate':'existing source_excerpt_markdown_v1 and frozen F/P source bindings','rubric_limitation':'Initial five-item rubric insufficiently precise; do not claim it independently detected these semantic failures.'}
    write(OUT/'materials-semantic-review.json',audit)
    text='上一稿有两个需要纠正的问题：将任何量改成任何强度，扩大健康事实；将已明确的生活交流/日常沟通/工作资料需求写成未确认。请保留原记录，在当前会话给出更正。以下是冻结核对依据，逐字保留事实及已确认计划，不增加建议。\n'
    text+='\n'.join('F'+str(i+1)+'：'+v for i,v in enumerate(facts))+'\nP1：'+plans[0]
    ident='daily-real-materials-correction-20261115-r1';write(OUT/'materials-correction-start.json',{'request_id':ident,'chat_id':before['chat_id'],'facts':facts,'plans':plans,'linked_original_request':before['request_id']})
    client.call('/api/chat/send',{'chat_id':before['chat_id'],'request_id':ident,'text':text,**route(),'skill':'none','memory_enabled':False,'assistant_mode':False,'delivery_format':'source_excerpt_markdown_v1','delivery_basis':{'expected_revision':0,'facts':facts,'plans':plans}})
    for _ in range(90):
        detail=client.call('/api/chats/'+before['chat_id']);turn=next((v for v in detail['turns'] if v['id']==ident),None)
        if turn and turn['status'] not in ('READY','RUNNING'):break
        time.sleep(2)
    else:raise RuntimeError('Correction still pending; inspect original ID')
    write(PRIVATE/'materials-correction-dialogue.json',detail)
    value={'status':turn['status'],'error':turn.get('error'),'usage':turn.get('usage'),'reply':turn.get('reply'),'delivery_review':turn.get('delivery_review'),'request_id':ident,'chat_id':before['chat_id'],'source_gate_passed':(turn.get('delivery_review') or {}).get('state')=='EXCERPT_MATCH','business_repair_return_claimed':False}
    write(OUT/'materials-correction-result.json',value);print(json.dumps({'status':value['status'],'source_gate_passed':value['source_gate_passed'],'review':value['delivery_review']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
