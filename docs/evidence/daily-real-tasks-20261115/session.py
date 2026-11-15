"""Authenticated ordinary daily endpoints; no fixture, direct model or grant bypass."""
from pathlib import Path
import http.cookiejar,json,sqlite3,sys,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT))
from control.local_access import read_key
from tools.workstation import state,instance
from modules.preferences.store import Preferences
DATA=Path('E:/Jarvis/runtime/user-data')
PRIVATE=Path('E:/Jarvis/validation/daily-real-tasks-20261115-private')

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

class Client:
    def __init__(self):
        self.origin='http://127.0.0.1:18282';self.token=''
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.call('/api/local-access',{'key':read_key(DATA)},log=False)
        self.token=self.call('/api/session',log=False)['token']
    def call(self,path,body=None,*,log=True):
        reserve=(2 if path=='/api/goals/plan' else 1 if path=='/api/chat/send' else
                 4 if path=='/api/development-runner' and body and body.get('network_enabled') else 0)
        protocol_path=OUT/'protocol.json'
        if reserve and protocol_path.exists():
            protocol=json.loads(protocol_path.read_text(encoding='utf-8'));started=protocol.get('started_at',protocol_path.stat().st_mtime)
            used=0
            for name,table in (('core','model_calls'),('dialogue','attempts')):
                db=sqlite3.connect((DATA/('state/'+name+'.sqlite3')).as_uri()+'?mode=ro',uri=True)
                try:used+=db.execute('SELECT count(*) FROM '+table+' WHERE created>=?',(started,)).fetchone()[0]
                finally:db.close()
            if used+reserve>protocol['session_paid_call_limit']:raise RuntimeError('Trial call ceiling would be exceeded; do not reset it')
        req=urllib.request.Request(self.origin+path,data=None if body is None else json.dumps(body).encode(),headers={'Origin':self.origin,'Content-Type':'application/json','X-Jarvis-Token':self.token})
        started=time.time()
        try:
            with self.opener.open(req,timeout=30) as response:result=json.loads(response.read(8000000))
        except urllib.error.HTTPError as error:
            result=json.loads(error.read())
            if log and body is not None:
                PRIVATE.mkdir(parents=True,exist_ok=True)
                with (PRIVATE/'operator-actions.jsonl').open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps({'time':started,'path':path,'command':body,'response':result,'http_status':error.code,'actor':'codex_operator','scope':'failed intervention; no automatic success inferred'},ensure_ascii=False)+'\n')
            raise RuntimeError(str(error.code)+' '+str(result)) from error
        if log and body is not None:
            PRIVATE.mkdir(parents=True,exist_ok=True)
            with (PRIVATE/'operator-actions.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'time':started,'path':path,'command':body,'response':result,'actor':'codex_operator','scope':'task setup or explicit intervention; never counted as autonomous Jarvis action'},ensure_ascii=False)+'\n')
        return result

def route():
    store=Preferences(DATA)
    try:
        cfg=store.read()['catalog'];provider=cfg['default_provider']
        return {'provider':provider,'model':cfg['providers'][provider]['model'],'reasoning':'default'}
    finally:store.close()

def english_plan():
    assert not (OUT/'english-plan-start.json').exists(),'Inspect prior IDs; do not replay a paid operation'
    before=state(DATA);assert before['active']['version']=='0.1.10'
    client=Client();selected=route()
    goal='为我制作实际应用导向的英语练习：我已工作20年，重视生活交流、日常沟通和阅读工作资料。先给一份可用的首日练习：生活交流、请求澄清、工作资料阅读各一项，带示例表达、中文说明、自我作答机会和参考答案，保存成可读材料。我的英语水平尚未测定，不要推断年龄、职业、健康情况或掌握程度；没有录音不能评定发音、听力或真实口语进步。遇到缺少能力须明确指出，不得换成乘法练习或字符统计。'
    request={'request_id':'daily-real-english-20261115-r1','goal':goal,'input_text':'真实用户需求：英语口语与英语学习；工作20年；生活交流、日常沟通、工作资料。未提供具体工作文件、英语水平或录音。',**selected}
    protocol={'scope':'user-origin practical English request through daily goal planning; not a synthetic multiplication task','started_at':time.time(),'before':before,'instance':instance(18282),'route':selected,'goals':['original requirements retained','no fake oral proficiency score','no invented source documents'],'unknown_retry':False,'session_paid_call_limit':12,'global_policy_changed':False,'quote_status':'awaiting genuine offers and budget/delivery constraints','health_status':'general interest only; no invented medical profile','operator_setup_actions_counted':True}
    write(OUT/'protocol.json',protocol)
    result=client.call('/api/goals',{'action':'create','request':request,'context':{'scope':'personal','enabled':False,'chat_id':'','turn_id':''}})
    ident=result['id'];write(OUT/'english-plan-start.json',{'goal_id':ident,'route':selected,'request_id':request['request_id']})
    client.call('/api/goals/plan',{'id':ident,'retry_unknown':False})
    for _ in range(60):
        detail=client.call('/api/goals',{'action':'detail','id':ident},log=False)
        if detail['plan']['status'] not in ('NEW','PLANNING'):
            write(PRIVATE/'english-plan-result.json',detail)
            value={'goal_id':ident,'status':detail['plan']['status'],'error':detail['plan']['error'],'proposal':detail['plan']['proposal'],'task_id':detail['plan']['task_id'],'execution_or_learning_success_claimed':False}
            write(OUT/'english-plan-result.json',value);print(json.dumps(value,ensure_ascii=False),flush=True);return
        time.sleep(2)
    raise RuntimeError('Planning observation timed out; inspect existing ID, never retry UNKNOWN')

if __name__=='__main__':english_plan()
