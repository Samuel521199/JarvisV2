'''Short-lived static fixture; serves public workbench assets only.'''
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,threading
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent/'ui-r2';OUT.mkdir(exist_ok=False)
actual=json.loads((Path(__file__).parent/'native-r1/fresh-source-excerpts.json').read_text(encoding='utf-8'))['planning_advice']
invalid={**actual,'current':False,'observation':{**actual['observation'],'review_required':True,'state':'NEEDS_CORRECTION'}}
inherited={**actual,'current':True,'inherited_from':'synthetic-parent-goal','model_dispatched':False,'model_calls':[],
    'observation':{'condition_score':None,'review_required':False}}
fixture=[{'title':'真实合成任务 · 条件已核验','value':actual},{'title':'反证后需要复核 · 展示状态','value':invalid},{'title':'上游依赖继承 · 不重发旧建议','value':inherited}]
HTML='''<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><title>Jarvis 经验参考显示验收</title><body><main id="test" style="padding:24px;max-width:1050px;margin:auto"></main><script type="module">import{planningAdvice}from'/planning-advice.js';const rows=await(await fetch('/fixture.json')).json();for(const row of rows){const box=document.createElement('section');box.className='card';const title=document.createElement('h2');title.textContent=row.title;box.append(title);planningAdvice(box,row.value,()=>{document.body.dataset.upstreamOpened='true'});for(const detail of box.querySelectorAll('details'))detail.open=true;document.getElementById('test').append(box);}document.body.dataset.ready='true';document.body.dataset.metrics=JSON.stringify({innerWidth:innerWidth,scrollWidth:document.documentElement.scrollWidth,mainWidth:document.getElementById('test').getBoundingClientRect().width,cardWidths:[...document.querySelectorAll('.card')].map(n=>n.getBoundingClientRect().width)});</script></body></html>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path=self.path.split('?',1)[0]
        if path=='/':value=HTML.encode();mime='text/html; charset=utf-8'
        elif path=='/fixture.json':value=json.dumps(fixture,ensure_ascii=False).encode();mime='application/json; charset=utf-8'
        elif path.startswith('/') and '/' not in path[1:] and Path(path).suffix in {'.js','.css','.svg'}:
            source=ROOT/'apps/workbench'/path[1:]
            if not source.is_file():self.send_error(404);return
            value=source.read_bytes();mime={'.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[source.suffix]
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(value)));self.end_headers();self.wfile.write(value)
    def do_POST(self):
        if self.path!='/finish':self.send_error(404);return
        self.send_response(200);self.end_headers();self.wfile.write(b'ok');threading.Thread(target=self.server.shutdown,daemon=True).start()
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
(OUT/'server.json').write_text(json.dumps({'url':'http://127.0.0.1:'+str(server.server_port),'scope':'static component with real synthetic receipt plus labelled display states; no business HTTP API'}),encoding='utf-8')
print('Static probe: http://127.0.0.1:'+str(server.server_port),flush=True)
try:server.serve_forever()
finally:server.server_close()
