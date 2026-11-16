"""One bounded semantic call for an actual synthetic recording in oral game mode."""
import base64,json,sqlite3,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from trial import Client,ROOT,OUT,ROUTE
from adapters.models.local_speech import synthesize

def main():
    ident='english-city-oral-shadow-a';question='english-city-oral-shadow-q';protocol=OUT/'oral-protocol.json';assert not protocol.exists(),'Inspect original paid request; do not replay the run'
    answer='Could we meet at four instead?'
    protocol.write_text(json.dumps({'max_external_calls':1,'answer':answer,'answer_id':ident,'question_id':question,'scope':'Synthetic local SAPI English audio + operator-confirmed transcript; not actual learner speech or an ASR/pronunciation test'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    c=Client();audio=synthesize(answer);recording=c.call('/api/english-learning',{'action':'record','audio':audio})['recording']
    chat=c.call('/api/chats',{})['id'];c.call('/api/chat/update',{'id':chat,'patch':{'title':'技术验证 · 独立软件口语录音 · 非本人表现'}})
    c.call('/api/english-learning',{'action':'game_start','request_id':question,'chat_id':chat,**ROUTE,'scene':'arrange','mode':'oral'})
    def wait(ident):
        for _ in range(90):
            state=c.call('/api/english-learning',{'action':'status'});job=next(j for j in state['jobs'] if j['id']==ident)
            if job['state']!='PENDING':
                (OUT/(ident+'.json')).write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');assert job['state']=='RECORDED','Inspect uncertain result; no automatic retry';return state
            time.sleep(2)
        raise RuntimeError('Observe original request; no timeout replay')
    before=wait(question)
    db=sqlite3.connect(ROOT/'user-data/state/dialogue.sqlite3')
    try:assert db.execute('SELECT count(*) FROM attempts WHERE turn_id=?',(ident,)).fetchone()[0]==0
    finally:db.close()
    c.call('/api/english-learning',{'action':'oral_answer','request_id':ident,'chat_id':chat,**ROUTE,'exercise_id':question,'answer':answer,'assistance':'independent','audio_id':recording['id']})
    state=wait(ident);ex=next(e for e in state['exercises'] if e['id']==question);a=ex['assessment'];assert a['speech']['sha256']==recording['sha256'] and a['game']['transition']['passed']
    assert state['oral_progress']['domains']['communication']['attempts']==before['oral_progress']['domains']['communication']['attempts']+1
    assert state['progress']==before['progress']
    restored=c.call('/api/english-learning',{'action':'recording','exercise_id':question});assert base64.b64decode(restored['audio'])==base64.b64decode(audio)
    (OUT/'oral-result.json').write_text(json.dumps({'passed':True,'recording':recording,'assessment':a,'oral_progress':state['oral_progress'],'written_progress_unchanged':True,'byte_exact_replay':True,'external_calls':1,'raw_audio_sent_to_model':False,'actual_user_speech':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Recorded oral game semantic turn passed; written progress unchanged')
if __name__=='__main__':main()
