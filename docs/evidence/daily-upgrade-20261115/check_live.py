"""Authenticated served-byte verification and isolated development restart."""
from pathlib import Path
import hashlib,http.cookiejar,json,subprocess,sys,urllib.request
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from control.local_access import read_key
from tools.workstation import instance
from adapters.development_bridge import exchange

def main():
    report=json.loads((OUT/'production.json').read_text(encoding='utf-8'));assert report['passed']
    daily=Path('E:/Jarvis/runtime/user-data');package=daily/'deployment/packages'/report['final_build'];origin='http://127.0.0.1:18282'
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    req=urllib.request.Request(origin+'/api/local-access',data=json.dumps({'key':read_key(daily)}).encode(),headers={'Origin':origin,'Content-Type':'application/json'})
    with opener.open(req,timeout=10) as response:assert response.status==200
    assets={}
    for name in ('ui.js','development.js','companion-shell.js'):
        with opener.open(origin+'/'+name,timeout=10) as response:raw=response.read()
        expected=(package/'apps/workbench'/name).read_bytes();assert raw==expected
        assets[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'matches_adopted_package':True}
    before=instance(18282)
    p=subprocess.run([sys.executable,'-X','utf8','-B','-m','tools.workstation','restart-development'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=90)
    (OUT/'development-restart.txt').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0
    after=instance(18282);development=instance(18283);assert before==after and development and development['environment']=='development'
    budget=exchange(ROOT/'user-data','/status');write={'assets':assets,'daily_boot_unchanged_by_development_restart':before==after,'daily':after,'development':development,'model_budget':budget,'browser_interaction_tested':False,'passed':True}
    (OUT/'live-checks.json').write_text(json.dumps(write,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(write),flush=True)

if __name__=='__main__':main()
