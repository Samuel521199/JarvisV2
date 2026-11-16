"""Jarvis bridge: client-owned progress/evidence, externally versioned game rules."""
import json,time
from adapters.software_client import binding,invoke
from sdk.protocol import CoreError,digest

def load(store,ident):
    row=store.db.execute('SELECT body FROM software_sessions WHERE id=?',(ident,)).fetchone()
    if not row:raise CoreError('english_missing','Unknown software session')
    return json.loads(row[0])

def verify(store,chats,session,software=True):
    from host.learning_sources import source_valid
    if software and binding(store.root)!=session['software']:raise CoreError('software_stale','Software version changed; explicitly revalidate or choose a new session')
    for ident in session['dependencies']:
        if not source_valid(chats,ident,store):raise CoreError('english_stale','Game learning source unavailable')
        row=store.db.execute('SELECT a.disputed,e.withdrawn FROM assessments a JOIN exercises e ON e.id=a.exercise_id WHERE a.id=?',(ident,)).fetchone()
        if row and (row['disputed'] or row['withdrawn']):raise CoreError('english_stale','Game evaluation disputed or withdrawn')

def check(store,chats,game,question=None):
    s=load(store,game['session_id']);verify(store,chats,s)
    if s['revision']!=game['revision'] or s['state']!='ACTIVE' or question and s['exercise_id']!=question:raise CoreError('english_stale','Software session changed')

def prepare(store,chats,value):
    from host.learning_sources import active_chat
    action=value['action'];cfg=store.config()
    if action=='game_start':
        if value['scene'] not in ('cafe','arrange','work') or value['mode'] not in ('text','oral'):raise CoreError('english_invalid','Unknown scene or mode')
        software=binding(store.root);description=invoke(store.root,'describe',{},software)
        if description.get('id')!='english-city' or description.get('version')!=software['version']:raise CoreError('software_integrity','Software identity mismatch')
        ident='game-'+value['request_id'][8:]
        s={'id':ident,'chat_id':value['chat_id'],'software':software,'scene':value['scene'],'mode':value['mode'],'node':0,'attempt':0,'state':'ACTIVE','revision':0,'dependencies':[],'exercise_id':None,'created':time.time()}
        store.db.execute('PRAGMA user_version='+str(max(3,store.db.execute('PRAGMA user_version').fetchone()[0])))
        prior=store.db.execute('SELECT body FROM software_sessions WHERE id=?',(ident,)).fetchone()
        if prior:s=json.loads(prior[0])
        else:store.db.execute('INSERT INTO software_sessions VALUES(?,?)',(ident,json.dumps(s,ensure_ascii=False)))
    else:
        s=load(store,value['session_id']);verify(store,chats,s)
        if s['chat_id']!=value['chat_id'] or type(value['revision']) is not int or s['revision']!=value['revision']:raise CoreError('conflict','Software session revision changed')
        if s['state']!='ACTIVE' or s['exercise_id']:raise CoreError('english_busy','Finish the current turn or resume first')
    active_chat(chats,s['chat_id']);verify(store,chats,s)
    lesson=invoke(store.root,'lesson',{k:s[k] for k in ('scene','node','attempt')},s['software'])
    if lesson.get('schema')!=1 or lesson.get('scene')!=s['scene'] or lesson.get('node')!=s['node']:raise CoreError('software_output','Lesson binding mismatch')
    history=[]
    if s['attempt']:
        for ident in s['dependencies']:
            row=store.db.execute('SELECT body FROM assessments WHERE id=?',(ident,)).fetchone()
            if row:
                a=json.loads(row[0])
                if a.get('game',{}).get('node')==s['node']:history.append({'answer_turn':ident,'answer':a['answer'],'npc_reply':a['game']['npc_reply']})
        if sum(len(r['answer'])+len(r['npc_reply']) for r in history)>5000:raise CoreError('english_invalid','Conversation repair exceeds its bounded history; start a new scene')
    game={'session_id':s['id'],'revision':s['revision'],'software':s['software'],'lesson':lesson,'history':history}
    prompt=lesson['prompt']
    if history:
        prompt='【教学示例 · 虚构场景】'+lesson['title']+'\n任务：'+scene_goal(lesson)+'\n对方接着说：'+history[-1]['npc_reply']+'\n你上次说：'+history[-1]['answer']+'\n这是同一段对话（接续 '+str(s['attempt'])+'），可以只补充缺少的信息；前次原答分别保留。'
    if len(prompt)>2000:raise CoreError('english_invalid','Repair context is too long; start a new short scene')
    s['exercise_id']=value['request_id'];store.db.execute('UPDATE software_sessions SET body=? WHERE id=?',(json.dumps(s,ensure_ascii=False),s['id']))
    question={'schema':'jarvis.english-learning.v1','prompt':prompt,'reference':lesson['reference'],'hint':lesson['hint']}
    body={'revision':cfg['revision'],'api_digest':digest(value),'dependencies':list(s['dependencies']),'target':lesson['target'],'difficulty':1,'study_text':'','material_origin':'generated_example','previous_prompts':[],'background':[],'practice_mode':s['mode'],'game':game,'fixed_question':question}
    return body,'开始独立软件英语剧情：'+lesson['title']

def scene_goal(lesson):return lesson['prompt'].split('\n任务：',1)[1].split('\n对方：',1)[0]

INSTRUCTION='''本题来自独立英语情境软件。额外返回game对象，恰有requirements,evidence,intent,npc_reply,focus_items。
requirements和evidence的键恰好对应给定任务条件ID。requirements每项是met/missing/uncertain；evidence每项是逐字引用answer或previous_user_answers中用户原答的依据，缺失时空串。按同一回合的对话累计信息，允许只补充缺项，不强迫重说已确认内容；最新回答否定或改正旧信息时以最新意思为准。NPC话语不能当作用户已经表达的证据。不要只凭关键词判定；否定、时间、对象和修饰关系都要核对。不能凭参考表达不一样而扣分。用户请求重说是clarify，不是完成原任务；改目标是change_goal，不能强迫原目标；暂停是pause；其他为answer。
intent仅answer/clarify/change_goal/pause。npc_reply给本回合角色的一句自然英文响应，不泄露下回合答案；不完整则补问，错误则澄清，合理正确表达则确认。不得声称发邮件、下订单或执行真实操作。focus_items至多3项，每项恰有word,quote,suggestion,reason；word从给定words选择，quote逐字来自answer，suggestion和reason用简短文字说明真实问题；没有真实错误就空数组，风格优化不当错词。所有评价都是可争议的内容估计，不能推断发音/听力或掌握。'''

def parse(value,job):
    game=job['body']['game'];answer=job['body']['answer'];lesson=game['lesson'];g=value.get('game')
    fields={'requirements','evidence','intent','npc_reply','focus_items'}
    if not isinstance(g,dict) or set(g)!=fields or not isinstance(g['requirements'],dict) or not isinstance(g['evidence'],dict) or set(g['requirements'])!=set(lesson['requirements']) or set(g['evidence'])!=set(lesson['requirements']):raise CoreError('english_model_invalid','Invalid software judgement')
    evidence_sources={}
    history=game.get('history',[])
    for key,status in g['requirements'].items():
        quote=g['evidence'][key]
        if status not in ('met','missing','uncertain') or not isinstance(quote,str) or len(quote)>500 or quote and quote not in answer and not any(quote in h['answer'] for h in history) or status=='met' and not quote:raise CoreError('english_model_invalid','Unbound requirement evidence')
        evidence_sources[key]=job['id'] if quote and quote in answer else next((h['answer_turn'] for h in history if quote and quote in h['answer']),None)
    if g['intent'] not in ('answer','clarify','change_goal','pause') or not isinstance(g['npc_reply'],str) or not 1<=len(g['npc_reply'])<=700 or not isinstance(g['focus_items'],list) or len(g['focus_items'])>3:raise CoreError('english_model_invalid','Invalid game response')
    for item in g['focus_items']:
        if not isinstance(item,dict) or set(item)!={'word','quote','suggestion','reason'} or any(not isinstance(v,str) or not 1<=len(v)<=300 for v in item.values()) or item['word'] not in lesson['words'] or item['quote'] not in answer:raise CoreError('english_model_invalid','Unbound vocabulary observation')
    result=invoke(job['_root'],'advance',{'lesson':lesson,'judgement':{'requirements':g['requirements'],'meaning':value['meaning'],'confidence':value['confidence'],'intent':g['intent']}},game['software'])
    if result.get('schema')!=1 or result.get('state') not in ('ACTIVE','PAUSED','COMPLETED') or type(result.get('node')) is not int or type(result.get('attempt')) is not int or type(result.get('passed')) is not bool:raise CoreError('software_output','Invalid proposed transition')
    return {**g,'requirements_text':lesson['requirements'],'evidence_sources':evidence_sources,'transition':result,'software':game['software'],'session_id':game['session_id'],'scene':lesson['scene'],'node':lesson['node']}

def control(store,chats,value):
    s=load(store,value['session_id']);verify(store,chats,s,software=value['action']!='game_rebind')
    if type(value['revision']) is not int or s['revision']!=value['revision']:raise CoreError('conflict','Software session revision changed')
    pending=store.db.execute("SELECT 1 FROM jobs WHERE state IN ('PENDING','UNKNOWN') AND json_extract(body,'$.game.session_id')=?",(s['id'],)).fetchone()
    if pending:raise CoreError('english_busy','Resolve the original pending or unknown turn before changing the session')
    if value['action']=='game_rebind':
        current=binding(store.root)
        if current['build']!=s['software']['build'] or current['version']!=s['software']['version']:raise CoreError('software_stale','Changed software requires a separately reviewed state migration or a new scene')
        s['software']=current
    elif value['action']=='game_pause':
        if s['state']!='ACTIVE':raise CoreError('english_stale','Session is not active')
        s['state']='PAUSED'
    else:
        if s['state']!='PAUSED' or s['attempt']>=6:raise CoreError('english_stale','Start a new scene after the retry ceiling or completed scene')
        s['state']='ACTIVE'
    s['revision']+=1;store.db.execute('UPDATE software_sessions SET body=? WHERE id=?',(json.dumps(s,ensure_ascii=False),s['id']))
    # A prepared unanswered exercise remains valid across a user pause/resume.
    if s['exercise_id']:
        row=store.db.execute('SELECT body FROM exercises WHERE id=?',(s['exercise_id'],)).fetchone()
        if row:
            body=json.loads(row['body']);body['game']['revision']=s['revision'];body['game']['software']=s['software'];store.db.execute('UPDATE exercises SET body=? WHERE id=?',(json.dumps(body,ensure_ascii=False),s['exercise_id']))

def overview(store,chats,valid):
    sessions=[]
    try:
        from control.software_registry import read
        item=read(store.root)['software'].get('english-city');policy={'enabled':item['enabled'],'revision':item['revision']} if item else None
    except (CoreError,KeyError,TypeError):policy=None
    try:software=binding(store.root);available=True;reason=None
    except (CoreError,OSError,ValueError) as exc:software=None;available=False;reason=getattr(exc,'code','software_unavailable')
    for row in store.db.execute('SELECT body FROM software_sessions ORDER BY rowid DESC LIMIT 20'):
        s=json.loads(row[0]);status=s['state']
        try:verify(store,chats,s)
        except (CoreError,OSError,ValueError):status='SOURCE_OR_SOFTWARE_UNAVAILABLE'
        sessions.append({k:s[k] for k in ('id','chat_id','scene','mode','node','attempt','revision','exercise_id')}|{'state':status,'software_build':s['software']['build']})
    words=[]
    for a in sorted(valid,key=lambda r:r['created'],reverse=True):
        for item in a.get('game',{}).get('focus_items',[]):words.append({**item,'source':a['answer_turn'],'created':a['created'],'judge':'provisional'})
    from modules.english_learning.store import schedule
    due=sorted(schedule(valid).values(),key=lambda r:(not r['due_now'],r['count']>0,r['count']))
    domain=due[0]['domain'] if due else 'life'
    due_items=[r for r in due if r['due_now']][:2]
    return {'available':available,'policy':policy,'software':software,'unavailable_reason':reason,'sessions':sessions,'vocabulary_observations':words[:30],'recommended_scene':{'life':'cafe','communication':'arrange','work':'work'}[domain],'due_targets':[{'target':r['target'],'label':r['label']} for r in due_items],'planning':'Prioritizes existing due reviews, then less-practiced targets; no background schedule.'}
