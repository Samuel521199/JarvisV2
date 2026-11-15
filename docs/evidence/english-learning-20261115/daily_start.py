"""One first learning question in the real daily chat; never fabricate an answer."""
from pathlib import Path
import json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT));sys.path.insert(0,str(OUT))
from trial_api import Client,ROUTE
DAILY=Path('E:/Jarvis/runtime/user-data')

def main():
    assert json.loads((OUT/'production.json').read_text())['passed']
    client=Client(18282,DAILY);ident='english-daily-20261115-first';chat='chat-07c934420a2e4cd2a878fc3cf84cf837'
    state=client.call('/api/english-learning',{'action':'status'});existing=next((j for j in state['jobs'] if j['id']==ident),None)
    if not existing:
        assert not state['jobs'] and not state['exercises']
        value=client.call('/api/chats/'+chat);assert not value['removed'] and not value['archived'] and not value['project_id']
        protocol={'max_external_calls':1,'request_id':ident,'chat_id':chat,'route':ROUTE,'scope':'Actual user learning entry; only a first question, no invented user performance or baseline score'}
        (OUT/'daily-protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        client.call('/api/english-learning',{'action':'start','request_id':ident,'chat_id':chat,**ROUTE,'domain':'life','study_text':''})
    state=client.wait(ident);exercise=next(e for e in state['exercises'] if e['id']==ident)
    assert exercise['assessment'] is None and all(row['attempts']==0 for row in state['progress']['domains'].values())
    db=sqlite3.connect((DAILY/'state/dialogue.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        rows=[dict(r) for r in db.execute('SELECT turn_id,provider,model,status,usage,error FROM attempts WHERE turn_id=?',(ident,))]
        assert len(rows)==1 and rows[0]['status']=='SUCCEEDED'
    finally:db.close()
    for row in rows:row['usage']=json.loads(row['usage'])
    result={'passed':True,'exercise':exercise,'actual_user_answers':0,'progress':state['progress'],'attempts':rows,'automatic_unknown_retries':0}
    (OUT/'daily-first-question.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
