"""Two bounded real text-model calls; local synthetic speech, not user proficiency."""
from pathlib import Path
import base64,json,sqlite3,sys,time
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OUT.parent/'english-learning-20261115'))
from trial_api import Client,ROUTE

def main():
    assert not (OUT/'voice-trial.json').exists(),'Inspect saved IDs before resuming'
    client=Client();prefix='english-voice-20261116-'
    def call(value):
        if value['action'] in ('oral_start','oral_answer'):
            db=sqlite3.connect((ROOT/'user-data/state/dialogue.sqlite3').as_uri()+'?mode=ro',uri=True)
            try:count=db.execute('SELECT count(*) FROM attempts WHERE turn_id LIKE ?',(prefix+'%',)).fetchone()[0]
            finally:db.close()
            assert count<2,'Never expand the frozen two-call budget'
        return client.call('/api/english-learning',value)
    def wait(ident):
        for _ in range(90):
            state=call({'action':'status'});job=next(j for j in state['jobs'] if j['id']==ident)
            if job['state']!='PENDING':
                (OUT/(ident+'.json')).write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                assert job['state']=='RECORDED','Preserve UNKNOWN; never blindly retry';return state
            time.sleep(2)
        raise RuntimeError('Inspect original request; do not replay timeout')
    raw=Path('E:/Jarvis/validation/english-voice-fixture-20261116.wav').read_bytes()
    chat=client.call('/api/chats',{})['id'];client.call('/api/chat/update',{'id':chat,'patch':{'title':'技术验证 · 合成录音与确认转写 · 非本人表现'}})
    protocol={'scope':'Local SAPI synthetic English audio + operator-confirmed transcript. Text-model semantic feedback only; no pronunciation/listening assessment. Never imported into daily.','max_external_calls':2,'chat_id':chat,'question':prefix+'question','answer':prefix+'answer'}
    (OUT/'voice-protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    saved=call({'action':'record','audio':base64.b64encode(raw).decode()})['recording']
    call({'action':'oral_start','request_id':prefix+'question','chat_id':chat,**ROUTE,'domain':'life','study_text':'教学示例情境：你在咖啡店，桌上没有餐巾纸，请用英语礼貌请求几张餐巾纸。'})
    wait(prefix+'question')
    call({'action':'oral_answer','request_id':prefix+'answer','chat_id':chat,**ROUTE,'exercise_id':prefix+'question','answer':'Could I have some napkins, please?','assistance':'independent','audio_id':saved['id']})
    state=wait(prefix+'answer');ex=next(e for e in state['exercises'] if e['id']==prefix+'question')
    restored=call({'action':'recording','exercise_id':ex['id']});assert base64.b64decode(restored['audio'])==raw
    assert ex['assessment']['speech']['sha256']==saved['sha256'] and ex['assessment']['meaning']==2
    assert state['oral_progress']['domains']['life']['attempts']==1
    result={'passed':True,'protocol':protocol,'recording':saved,'assessment':ex['assessment'],'written_progress':state['progress'],'oral_progress':state['oral_progress'],'byte_exact_replay':True,'actual_user_learning_gain':None,'raw_audio_sent_to_model':False}
    (OUT/'voice-trial.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'passed':True,'rating':[ex['assessment'][k] for k in ('meaning','form','appropriacy')],'seconds':saved['seconds']}))
if __name__=='__main__':main()
