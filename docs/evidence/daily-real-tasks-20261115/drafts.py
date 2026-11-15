"""Two user-relevant daily dialogue deliveries; no invented proficiency or quotes."""
import json,sqlite3,time
from session import Client,DATA,OUT,PRIVATE,route,write

SOURCES=[
 {'url':'https://www.who.int/news-room/fact-sheets/detail/physical-activity/','checked':'2026-11-15','summary':'WHO说明身体活动有益于身心健康；活动包括步行、出行与家务等，任何量的活动好过完全不活动，并应减少久坐。它是人群健康资料，不是针对这位用户的诊断或运动处方。'},
 {'url':'https://learnenglish.britishcouncil.org/free-resources/speaking','checked':'2026-11-15','summary':'British Council提供按A1至B2组织的口语练习资源，包含生活和工作沟通情境、视频和练习。资源分级不代表已测定用户等级。'}]

PROMPTS={
 'english':'''请直接写出一份我今天就能使用的英语实践材料，Markdown正文，不调用工具或提出任务操作。我已经工作20年，想提高生活交流、日常沟通和阅读工作资料的应用能力，而不是应试。不要推断我的年龄、职业或英语等级。
包含三个短场景：1生活交流（如问路或点餐），2没有听懂时如何礼貌请求重说并核对理解，3阅读一段你原创且明确标注为“教学示例、不是用户真实工作文件”的简短英文工作通知。每个场景有常用英语与中文意思、先让我自己作答的问题、放在后面的参考答案。总练习约10分钟，时长只是起步建议。不要在我尚未回答时打掌握分；没有录音就不能评发音、听力或口语进步。最后只问一个适合我实际回答的开场问题，便于下一轮真正练习。不要复制教材段落。''',
 'materials':'''请基于下列已核对的两个公开来源，制作一页“日常英语与个人健康资料卡”，Markdown正文，不调用工具或发起提醒。实际用途是为我的英语实践和健康关注整理可回看资料。每个来源单独给标题、两项以内中文要点、链接、核对日期，并区分公开资料事实与尚未确认的个人情况。不要扩大摘录中的健康结论，不开药，不作个人诊断，不假定年龄/疾病/体能/英语等级，不声称改善已发生。不要把“关注健康”写成已确诊疾病。不要编造供应商、价格或真实工作文件。资料：\n'''+json.dumps(SOURCES,ensure_ascii=False)}

def main():
    client=Client();selected=route();write(OUT/'sources.json',SOURCES)
    for label,text in PROMPTS.items():
        start=OUT/(label+'-dialogue-start.json')
        assert not start.exists(),'Inspect existing request before any paid replay'
        chat=client.call('/api/chats',{})['id'];ident='daily-real-'+label+'-20261115-r1'
        rubric={'scope':'delivered material quality, not learning gain or health outcome','checks':['requested situations or sources all present','source/example boundaries explicit','no fabricated personal profile','no unsupported proficiency or health-outcome claim','useful output with original evidence retained'],'automatic_repair_claimed':False}
        write(OUT/(label+'-rubric.json'),rubric)
        write(start,{'chat_id':chat,'request_id':ident,'route':selected,'origin':'actual user preferences; operator supplied explicit output constraints','user_interventions':0,'operator_prompt_setup':1})
        client.call('/api/chat/send',{'chat_id':chat,'request_id':ident,'text':text,**selected,'skill':'none','memory_enabled':False,'assistant_mode':False})
        for _ in range(90):
            detail=client.call('/api/chats/'+chat);turn=next((v for v in detail['turns'] if v['id']==ident),None)
            if turn and turn['status'] not in ('READY','RUNNING'):break
            time.sleep(2)
        else:raise RuntimeError('Still running; observe exact request, do not resubmit')
        write(PRIVATE/(label+'-dialogue.json'),detail)
        if turn['status']!='SUCCEEDED':
            write(OUT/(label+'-failure.json'),{'status':turn['status'],'error':turn.get('error')});raise RuntimeError('Daily response failed; preserve call before correction')
        raw=turn['reply'];reply=json.loads(raw) if isinstance(raw,str) and raw.startswith('{') else raw
        if isinstance(reply,dict):reply=reply.get('text',reply.get('reply',reply))
        assert isinstance(reply,str),type(reply)
        (OUT/(label+'-actual.txt')).write_text(reply+'\n',encoding='utf-8')
        db=sqlite3.connect((DATA/'state/dialogue.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        calls=[dict(r) for r in db.execute('SELECT id,turn_id,status,usage,error,provider,model FROM attempts WHERE turn_id=? ORDER BY id',(ident,))];db.close()
        for call in calls:call['usage']=json.loads(call['usage']) if call['usage'] else None
        write(OUT/(label+'-dialogue-result.json'),{'status':turn['status'],'request_id':ident,'chat_id':chat,'calls':calls,'content_review':'pending','delivered_through_daily_dialogue':True,'goal_rejoined':False,'learning_or_health_gain_measured':False})
        print(json.dumps({'domain':label,'status':turn['status'],'calls':len(calls)}),flush=True)

if __name__=='__main__':main()
