"""Explicit Jarvis production acceptance. No model calls or automatic retries."""
import argparse,json,time,urllib.request,uuid,re
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--origin',default='http://127.0.0.1:18283');p.add_argument('--master');p.add_argument('--preset',default='panzer2-master');p.add_argument('--label',required=True);p.add_argument('--size',type=int,default=1024);p.add_argument('--budget',type=int,default=30000);p.add_argument('--category',default='vehicle');a=p.parse_args()
    if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{4,5}',a.origin) or not re.fullmatch('[a-z0-9-]{1,60}',a.label):p.error('Local origin and safe label required')
    folder=Path(__file__).resolve().parents[1]/'docs/evidence/studio3d-production-2026-10-24'/a.label;folder.mkdir(parents=True,exist_ok=False)
    def get(path):return json.load(urllib.request.urlopen(a.origin+path,timeout=25))
    # Key-protected workbench: run as `python -m tools.eval_studio3d_production` from the project root.
    try:from control.local_access import install_client;install_client(a.origin)
    except ImportError:pass
    token=get('/api/session')['token']
    def post(path,value):return json.load(urllib.request.urlopen(urllib.request.Request(a.origin+path,data=json.dumps(value).encode(),headers={'Origin':a.origin,'X-Jarvis-Token':token,'Content-Type':'application/json'}),timeout=30))
    body={'id':uuid.uuid4().hex}
    if a.master:
        prior=get('/api/studio3d/jobs/'+a.master);render=dict(prior['receipt']['configuration']['render']);render['five_views']=False
        body.update(prepare_asset=a.master,texture_size=a.size,production={'category':a.category,'triangle_budget':a.budget,'ray_distance':.04},render=render)
    else:body['preset']=a.preset
    record={'request':body,'origin':a.origin,'paid_model_calls':0};record['accepted']=post('/api/studio3d/jobs',body);last=None
    for _ in range(480):
        job=get('/api/studio3d/jobs/'+body['id']);record['job']=job;(folder/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        if job['phase']!=last:print(job['status']+' '+job['phase'],flush=True);last=job['phase']
        if job['status'] not in ('QUEUED','PLANNING','BUILDING'):break
        time.sleep(1)
    if job['status']!='DELIVERED':raise RuntimeError(str(job['error']))
    for filename in ('preview.png','normal.png','basecolor.png','orm.png'):
        if filename in job['receipt']['files']:(folder/filename).write_bytes(urllib.request.urlopen(a.origin+job['receipt']['files'][filename]['url'],timeout=30).read())
    print(json.dumps({'id':body['id'],'status':job['status'],'quality':job['receipt']['quality'],'triangles':job['receipt']['report']['triangles'],'resources':job['receipt']['resources']},ensure_ascii=False))
if __name__=='__main__':main()
