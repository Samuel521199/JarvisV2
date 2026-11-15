"""Continue the user's real daily chat with the existing English workflow."""
import json,time
from session import Client,OUT,PRIVATE,route,write

def main():
    target=OUT/'english-coach-start.json'
    assert not target.exists(),'Observe saved request; never replay an uncertain call'
    chat=json.loads((OUT/'english-dialogue-start.json').read_text())['chat_id']
    request='daily-real-english-coach-20261115-r1'
    text='''开始英语练习：更正需求，我要直接基于Jarvis这个AI系统平时学习英语，不是购买英语服务。已确认用途是生活交流、日常沟通、工作资料；已工作20年，但年龄、行业、英语水平未知。上面的材料是参考，不能算我已作答。请成为这个会话里的英语练习伙伴：每次一个实用场景，先让我回答；我回答后，区分影响理解的错误与可选风格建议，解释一两个重点，再换一个类似但不同的场景检查能否应用。中文解释可用，练习用英文，不提前泄露本题答案。遇到工作资料仅使用我提供的文本或明确标记的教学示例。每轮结尾可记录简短学习卡（实际题目、我的原回答、修改理由、尚需复习项），没有作答记“待作答”，不要编造错题、掌握分或学习进步。只承诺现有同会话记录，不声称自动建成跨会话词库、语音评分或提醒。现在只需用中文简短说明练法，然后给一道生活交流开场题，等我回答；不重复给整套课，不创建购买任务、外部提醒或推断健康情况。'''
    client=Client()
    write(target,{'chat_id':chat,'request_id':request,'skill':'english-coach','user_scope':'Jarvis-native practice; not English-service purchasing','operator_setup':True,'learner_answer_supplied':False,'request_text':text})
    client.call('/api/chat/send',{'chat_id':chat,'request_id':request,'text':text,**route(),'skill':'english-coach','memory_enabled':False,'assistant_mode':False})
    for _ in range(90):
        detail=client.call('/api/chats/'+chat)
        turn=next((t for t in detail['turns'] if t['id']==request),None)
        if turn and turn['status'] not in ('READY','RUNNING'):break
        time.sleep(2)
    else:raise RuntimeError('Observe saved request; no uncertain retries')
    write(PRIVATE/'english-coach-dialogue.json',detail)
    assert turn['status']=='SUCCEEDED',turn['status']
    reply=turn['reply'];guidance=turn['guidance']
    if isinstance(guidance,str):guidance=json.loads(guidance)
    assert guidance['id']=='english-coach'
    (OUT/'english-coach-opening.txt').write_text(reply+'\n',encoding='utf-8')
    write(OUT/'english-coach-result.json',{'chat_id':chat,'request_id':request,'status':turn['status'],'selected_skill':guidance['id'],'skill_version':guidance['version'],'state':'WAITING_FOR_REAL_LEARNER_ANSWER','learning_gain':None,'cross_session_review_verified':False})
    print(reply,flush=True)

if __name__=='__main__':main()
