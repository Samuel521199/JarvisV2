"""Short native Edge static-component check. No running workbench data or API."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,threading,subprocess,time
ROOT=Path('E:/Jarvis/dev');OUT=ROOT/'docs/evidence/advice-pair-20261114/ui-r1';PROFILE=Path('E:/Jarvis/validation/exposure-ui-20261114-r1')
OUT.mkdir(exist_ok=False);PROFILE.mkdir(exist_ok=False)
actual=json.loads((OUT.parent/'current-ui-projection.json').read_text())
invalid={**actual,'current':False,'observation':{'condition_score':100,'review_required':True,'state':'NEEDS_CORRECTION'}}
inherited={**actual,'current':True,'message_exposure':None,'inherited_from':'synthetic-parent-goal','model_dispatched':False,'model_calls':[],'observation':{'condition_score':None,'review_required':False}}
fixture=[{'title':'模型替身 · 新规划账本体积','value':actual},{'title':'需要复核 · 展示状态','value':invalid},{'title':'继承依赖 · 不重发上游经验','value':inherited}]
HTML='''<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><title>Jarvis 经验体积诊断显示验收</title><body><main id="test" style="padding:24px;max-width:1050px;margin:auto"></main><script type="module">import{planningAdvice}from'/planning-advice.js';const rows=await(await fetch('/fixture.json')).json();for(const row of rows){const box=document.createElement('section');box.className='card';const title=document.createElement('h2');title.textContent=row.title;box.append(title);planningAdvice(box,row.value,()=>{document.body.dataset.upstreamOpened='true'});for(const detail of box.querySelectorAll('details'))detail.open=true;document.getElementById('test').append(box);}document.body.dataset.ready='true';</script></body></html>'''
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
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
edge=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe');assert edge.is_file();browser=None
try:
    with (OUT/'browser.txt').open('w',encoding='utf-8') as stream:
        browser=subprocess.Popen([str(edge),'--headless=new','--disable-gpu','--no-first-run','--remote-debugging-port=0','--user-data-dir='+str(PROFILE),'about:blank'],stdout=stream,stderr=stream,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    portfile=PROFILE/'DevToolsActivePort'
    for _ in range(100):
        if portfile.exists():break
        if browser.poll() is not None:raise RuntimeError('Browser exited before DevTools became ready')
        time.sleep(.1)
    port=portfile.read_text().splitlines()[0]
    result=subprocess.run(['node',str(OUT.parent/'render_ui.cjs'),port,'http://127.0.0.1:'+str(server.server_port),str(OUT)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=45)
    (OUT/'client.txt').write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0,result.stderr
    browser.wait(timeout=10);report=json.loads((OUT/'render-result.json').read_text());assert report['passed']
    print(json.dumps({'passed':True,'viewports':[row['width'] for row in report['rows']],'browser_exited':browser.poll() is not None,'static_server_stopped':True}),flush=True)
finally:
    server.shutdown();server.server_close();thread.join(timeout=5)
    if browser and browser.poll() is None:browser.terminate();browser.wait(timeout=10)
