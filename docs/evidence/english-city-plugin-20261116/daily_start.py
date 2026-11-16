"""Prepare an actual daily game question; no model call, fabricated answer or microphone."""
from pathlib import Path
import base64,io,json,sqlite3,sys,time,wave
sys.path.insert(0,str(Path(__file__).parent))
from trial import Client,OUT,ROOT
DAILY=Path('E:/Jarvis/runtime/user-data')

def main():
    production=json.loads((OUT/'production.json').read_text());assert production['passed']
    c=Client(18282,DAILY);ident='english-city-daily-first-q'
    db=sqlite3.connect((DAILY/'state/dialogue.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:prior=db.execute('SELECT chat_id FROM turns WHERE id=?',(ident,)).fetchone()
    finally:db.close()
    if prior:chat=prior[0]
    else:
        state=c.call('/api/english-learning',{'action':'status'});assert not state['games']['sessions']
        chat=c.call('/api/chats',{})['id'];c.call('/api/chat/update',{'id':chat,'patch':{'title':'英语城市 · 日常生活'}})
        c.call('/api/english-learning',{'action':'game_start','request_id':ident,'chat_id':chat,'provider':'auto','model':'','reasoning':'default','scene':'cafe','mode':'text'})
    for _ in range(60):
        state=c.call('/api/english-learning',{'action':'status'});job=next(j for j in state['jobs'] if j['id']==ident)
        if job['state']!='PENDING':break
        time.sleep(.2)
    assert job['state']=='RECORDED'
    ex=next(e for e in state['exercises'] if e['id']==ident);assert ex['assessment'] is None and ex['hints']==0 and not ex['exposed']
    voice=c.call('/api/english-learning',{'action':'speak_npc','exercise_id':ident});raw=base64.b64decode(voice['audio'])
    with wave.open(io.BytesIO(raw),'rb') as audio:meta={'seconds':audio.getnframes()/audio.getframerate(),'channels':audio.getnchannels(),'rate':audio.getframerate()}
    after=c.call('/api/english-learning',{'action':'status'});ex2=next(e for e in after['exercises'] if e['id']==ident);assert ex2==ex
    db=sqlite3.connect((DAILY/'state/dialogue.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:attempts=db.execute('SELECT count(*) FROM attempts WHERE turn_id=?',(ident,)).fetchone()[0]
    finally:db.close()
    assert attempts==0 and after['games']['software']['build']==production['independent_software']['build']
    result={'passed':True,'chat_id':chat,'question':ex,'session':next(s for s in state['games']['sessions'] if s['exercise_id']==ident),'local_npc_speech':meta,'npc_speech_exposes_reference':False,'model_calls':0,'user_answer_submitted':False,'microphone_access':False,'synthetic_scores_imported':False,'vocabulary_observations':after['games']['vocabulary_observations'],'written_progress':after['progress'],'oral_progress':after['oral_progress']}
    (OUT/'daily-first-game.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'passed':True,'model_calls':0,'scene':'cafe','chat_id':chat,'local_speech_seconds':meta['seconds']}))
if __name__=='__main__':main()
