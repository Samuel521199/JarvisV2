"""One additional frozen call: supplement previous speech instead of repeating it."""
from pathlib import Path
import json,sqlite3,sys,time
sys.path.insert(0,str(Path(__file__).parent))
from trial import Client,ROUTE,ROOT,OUT

def main():
    protocol=OUT/'repair-protocol.json';assert not protocol.exists(),'Inspect the original request before resuming'
    original=json.loads((OUT/'trial-results.json').read_text(encoding='utf-8'));case=next(r for r in original['results'] if r['case']['id']=='cafe-incomplete');s=case['session'];client=Client()
    answer='Small, hot, no sugar, to go, please.';ident='english-city-repair-shadow-a';question='english-city-repair-shadow-q'
    protocol.write_text(json.dumps({'max_external_calls':1,'question':question,'answer_id':ident,'answer':answer,'expected':'The previous user answer A coffee, please supplies coffee; new short reply fills missing conditions. Preserve original partial score.','scope':'Development synthetic learner, not actual user learning'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def wait(ident):
        for _ in range(90):
            state=client.call('/api/english-learning',{'action':'status'});j=next(j for j in state['jobs'] if j['id']==ident)
            if j['state']!='PENDING':
                (OUT/(ident+'.json')).write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');assert j['state']=='RECORDED','No unknown replay';return state
            time.sleep(2)
        raise RuntimeError('Inspect original request; do not replay timeout')
    client.call('/api/english-learning',{'action':'game_next','request_id':question,'chat_id':s['chat_id'],**ROUTE,'session_id':s['id'],'revision':s['revision']});wait(question)
    db=sqlite3.connect(ROOT/'user-data/state/dialogue.sqlite3')
    try:assert db.execute('SELECT count(*) FROM attempts WHERE turn_id=?',(ident,)).fetchone()[0]==0
    finally:db.close()
    client.call('/api/english-learning',{'action':'answer','request_id':ident,'chat_id':s['chat_id'],**ROUTE,'exercise_id':question,'answer':answer,'assistance':'independent'})
    state=wait(ident);a=next(e['assessment'] for e in state['exercises'] if e['id']==question);assert a['game']['transition']['passed']
    assert a['game']['evidence_sources']['drink']=='english-city-shadow-cafe-incomplete-a'
    first=next(e['assessment'] for e in state['exercises'] if e['id']=='english-city-shadow-cafe-incomplete-q');assert first==case['assessment']
    (OUT/'repair-result.json').write_text(json.dumps({'passed':True,'assessment':a,'original_assessment_unchanged':True,'previous_information_source':a['game']['evidence_sources']['drink'],'external_calls':1,'user_progress':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Short repair passed; original score unchanged')
if __name__=='__main__':main()
