"""One authenticated live development request; no private source text or retries."""
from pathlib import Path
import http.cookiejar,json,sys,time,urllib.request,uuid
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
from adapters.development_bridge import exchange
from control.local_access import read_key
from modules.dialogue.document_format import FORMAT
from modules.task_resource import body_evidence
from modules.preferences.store import resolve
from sdk.pricing import estimate


def main():
    dev=ROOT/'user-data';output=Path(sys.argv[1]).resolve()
    if output.exists():raise FileExistsError('Do not replace an earlier live probe')
    status=exchange(dev,'/status');catalog=exchange(dev,'/catalog')['catalog'];route=resolve(catalog,catalog['default_provider'],None,'low')
    if status['calls_in_24h']>=status['daily_call_limit']:raise RuntimeError('Existing call allowance exhausted')
    base='http://127.0.0.1:18283';nonce=None
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path,value=None):
        headers={'Origin':base,'Content-Type':'application/json'}
        if nonce:headers['X-Jarvis-Token']=nonce
        data=json.dumps(value,ensure_ascii=False).encode() if value is not None else None
        with opener.open(urllib.request.Request(base+path,data=data,headers=headers),timeout=10) as response:
            return json.loads(response.read(1000000))
    request('/api/local-access',{'key':read_key(dev)});nonce=request('/api/session')['token']
    chat=request('/api/chats',{'project_id':''})['id'];ident='document-probe-'+uuid.uuid4().hex
    fact='本次probe_doc是E盘开发服务的合成文档验收。';plan='验收后保留测试会话，不安排真实提醒。'
    command={'chat_id':chat,'request_id':ident,'text':'只把当前核对事实和计划整理成来源摘录文档，不增加建议。\nF1：'+fact+'\nP1：'+plan,
        'provider':route['id'],'model':route['model'],'reasoning':'low','skill':'none','memory_enabled':False,'assistant_mode':True,
        'delivery_format':FORMAT,'delivery_basis':{'expected_revision':0,'facts':[fact],'plans':[plan]}}
    report={'request_id':ident,'chat_id':chat,'model_calls_limit':1,'request_retries':0,'auth_material_saved':False,
        'source':'synthetic development-only fact/plan','production_modified':False}
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    request('/api/chat/send',command);deadline=time.monotonic()+150
    while True:
        detail=request('/api/chats/'+chat);turn=next((x for x in detail['turns'] if x['id']==ident),None)
        if turn and turn['status'] not in {'READY','RUNNING'}:break
        if time.monotonic()>deadline:
            report.update(terminal=False,passed=False,remaining='Poll this exact request; do not resend')
            output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');raise TimeoutError('Live turn remains pending; no retry')
        time.sleep(.25)
    reply=json.loads(turn['reply']) if turn['status']=='SUCCEEDED' else None
    checks=body_evidence.assess({'sources':{'F1':fact,'P1':plan},'facts':['F1'],'plans':['P1']},reply) if reply else []
    review=turn.get('delivery_review') or {}
    report.update(terminal=True,status=turn['status'],error=turn.get('error'),reply=reply,checks=checks,
        rendering=review.get('rendering'),review_state=review.get('state'),usage=turn.get('usage'),
        api_estimate=estimate(route.get('billing_profile'),turn.get('usage') or {},time.time()),
        passed=turn['status']=='SUCCEEDED' and bool(checks) and all(c['status']=='passed' for c in checks) and review.get('state')=='EXCERPT_MATCH')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['status','review_state','passed','usage']}),flush=True)
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
