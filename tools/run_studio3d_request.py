"""Run one explicit local Studio request; never retries model calls."""
import argparse,json,re,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--origin',default='http://127.0.0.1:18282');p.add_argument('--request',required=True);p.add_argument('--label',required=True);a=p.parse_args()
    if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{4,5}',a.origin) or not re.fullmatch('[a-z0-9-]{1,60}',a.label):p.error('Local origin and safe label required')
    folder=ROOT/'docs/evidence/studio3d-apple-2026-10-24'/a.label;folder.mkdir(parents=True,exist_ok=False)
    def get(path):return json.load(urllib.request.urlopen(a.origin+path,timeout=25))
    # Key-protected workbench: run as `python -m tools.run_studio3d_request` from the project root.
    try:from control.local_access import install_client;install_client(a.origin)
    except ImportError:pass
    token=get('/api/session')['token'];body=json.loads(Path(a.request).read_text(encoding='utf-8-sig'));result={'origin':a.origin,'request':body}
    def save():(folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    save();req=urllib.request.Request(a.origin+'/api/studio3d/jobs',data=json.dumps(body,ensure_ascii=False).encode(),headers={'Origin':a.origin,'X-Jarvis-Token':token,'Content-Type':'application/json'})
    result['accepted']=json.load(urllib.request.urlopen(req,timeout=30));save();last=None
    for _ in range(480):
        job=get('/api/studio3d/jobs/'+body['id']);result['job']=job;save()
        if job['phase']!=last:print(job['status']+' '+job['phase'],flush=True);last=job['phase']
        if job['status'] not in ('QUEUED','PLANNING','BUILDING'):break
        time.sleep(1)
    if job['status']!='DELIVERED':raise RuntimeError(str(job['error']))
    for filename in ('preview.png','normal.png','basecolor.png','orm.png','view-front.png','view-left.png','view-top.png'):
        if filename in job['receipt']['files']:(folder/filename).write_bytes(urllib.request.urlopen(a.origin+job['receipt']['files'][filename]['url'],timeout=30).read())
    print(json.dumps({'id':body['id'],'status':job['status'],'triangles':job['receipt']['report']['triangles'],'quality':job['receipt']['quality'],'resources':job['receipt']['resources']},ensure_ascii=False))
if __name__=='__main__':main()
