"""Normal authenticated development API; bounded real-model shadow trials."""
from pathlib import Path
import http.cookiejar,json,sqlite3,sys,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from control.local_access import read_key
DATA=ROOT/'user-data'

def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

class Client:
    def __init__(self,port=18283,data=DATA):
        self.origin='http://127.0.0.1:'+str(port);self.data=data;self.token=''
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.call('/api/local-access',{'key':read_key(data)});self.token=self.call('/api/session')['token']
    def call(self,path,body=None):
        if path=='/api/english-learning' and body and body.get('action') in ('start','answer'):
            db=sqlite3.connect((self.data/'state/dialogue.sqlite3').as_uri()+'?mode=ro',uri=True)
            try:n=db.execute("SELECT count(*) FROM attempts WHERE turn_id LIKE 'english-shadow-20261115-%'").fetchone()[0]
            finally:db.close()
            if n>=9:raise RuntimeError('Shadow paid-call ceiling reached; do not expand or reset it')
        request=urllib.request.Request(self.origin+path,data=None if body is None else json.dumps(body).encode(),headers={'Origin':self.origin,'Content-Type':'application/json','X-Jarvis-Token':self.token})
        try:
            with self.opener.open(request,timeout=30) as response:return json.loads(response.read(12000000))
        except urllib.error.HTTPError as error:raise RuntimeError(str(error.code)+' '+error.read().decode()) from error
    def wait(self,ident):
        for _ in range(90):
            state=self.call('/api/english-learning',{'action':'status'});job=next(j for j in state['jobs'] if j['id']==ident)
            if job['state']!='PENDING':
                write(ident+'.json',{'job':job,'state':state})
                if job['state']!='RECORDED':raise RuntimeError('Inspect '+ident+'; never automatically replay UNKNOWN')
                return state
            time.sleep(2)
        raise RuntimeError('Observe original request; do not replay timeout')

ROUTE={'provider':'vertex','model':'gemini-3.8-flash','reasoning':'default'}
CASES={
 'life':{'text':'教学示例情境：在咖啡店点一杯小杯不加糖的热咖啡。','answer':"I'd like a small hot coffee with no sugar, please.",'expect':'meaning=2; accept equivalent wording'},
 'communication':{'text':'教学示例情境：没有听清对方说明，请对方说慢一点，并重说最后一句。','answer':'Could you speak a little more slowly and repeat the last sentence, please?','expect':'meaning=2; polite equivalent wording'},
 'work':{'text':'教学示例：The office will be closed on Friday. Please submit your report by Thursday at 3 p.m. 任务：读懂应该何时交报告。','answer':'We need to submit the report on Friday at 3 p.m.','expect':'meaning<=1; must identify Thursday deadline'}
}

def main():
    phase=sys.argv[1];client=Client()
    if phase in ('questions','questions-r2'):
        suffix='-r2' if phase.endswith('r2') else ''
        assert not (OUT/('shadow-protocol'+suffix+'.json')).exists(),'Resume saved IDs instead'
        write('shadow-protocol'+suffix+'.json',{'scope':'Synthetic learner answers in development only; real model, not actual user performance','cases':CASES,'route':ROUTE,'max_paid_calls':9,'automatic_unknown_retry':False,'runtime_source':'working tree before qualification','started_at':time.time()})
        state=client.call('/api/english-learning',{'action':'status'})
        if not state['config']['enabled']:client.call('/api/english-learning',{'action':'configure','enabled':True,'revision':state['config']['revision']})
        for domain,case in CASES.items():
            chat=client.call('/api/chats',{})['id'];client.call('/api/chat/update',{'id':chat,'patch':{'title':'技术验证 · 非用户实际表现 · '+domain}})
            ident='english-shadow-20261115-'+domain+'-question'+suffix
            write(domain+'-start'+suffix+'.json',{'chat_id':chat,'request_id':ident})
            client.call('/api/english-learning',{'action':'start','request_id':ident,'chat_id':chat,**ROUTE,'domain':domain,'study_text':case['text']})
            state=client.wait(ident);ex=next(e for e in state['exercises'] if e['id']==ident);print(json.dumps({'domain':domain,'question':ex['exercise']['prompt']},ensure_ascii=False),flush=True)
    elif phase=='answers':
        for domain,case in CASES.items():
            start=json.loads((OUT/(domain+('-start-r3.json' if (OUT/(domain+'-start-r3.json')).exists() else '-start-r2.json'))).read_text());ident='english-shadow-20261115-'+domain+'-answer';assert not (OUT/(ident+'.json')).exists()
            client.call('/api/english-learning',{'action':'answer','request_id':ident,'chat_id':start['chat_id'],**ROUTE,'exercise_id':start['request_id'],'answer':case['answer'],'assistance':'independent'})
            state=client.wait(ident);ex=next(e for e in state['exercises'] if e['id']==start['request_id']);print(json.dumps({'domain':domain,'assessment':ex['assessment']},ensure_ascii=False),flush=True)
    elif phase=='work-r3':
        assert not (OUT/'work-start-r3.json').exists()
        old=json.loads((OUT/'work-start-r2.json').read_text());client.call('/api/english-learning',{'action':'withdraw','exercise_id':old['request_id']})
        ident='english-shadow-20261115-work-question-r3';write('work-start-r3.json',{'chat_id':old['chat_id'],'request_id':ident})
        client.call('/api/english-learning',{'action':'start','request_id':ident,'chat_id':old['chat_id'],**ROUTE,'domain':'work','study_text':CASES['work']['text']})
        state=client.wait(ident);print(json.dumps(next(e for e in state['exercises'] if e['id']==ident),ensure_ascii=False),flush=True)
    elif phase=='cross-session':
        assert not (OUT/'cross-session-start.json').exists()
        chat=client.call('/api/chats',{})['id'];client.call('/api/chat/update',{'id':chat,'patch':{'title':'技术验证 · 跨会话错题复习 · 非用户表现'}})
        ident='english-shadow-20261115-cross-review';write('cross-session-start.json',{'chat_id':chat,'request_id':ident})
        client.call('/api/english-learning',{'action':'start','request_id':ident,'chat_id':chat,**ROUTE,'domain':'mistakes','study_text':''})
        state=client.wait(ident);print(json.dumps({'progress':state['progress'],'review':next(e for e in state['exercises'] if e['id']==ident)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
