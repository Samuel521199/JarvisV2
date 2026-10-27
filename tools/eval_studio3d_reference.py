"""Explicit owner-requested image-planning acceptance, preserving each attempt."""
import argparse,base64,json,time,urllib.request,uuid,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--origin',default='http://127.0.0.1:18282');p.add_argument('--image',required=True);p.add_argument('--prompt-file',required=True);p.add_argument('--label',required=True);p.add_argument('--provider',default='vertex');p.add_argument('--model',default='gemini-4-argon');a=p.parse_args()
    if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{4,5}',a.origin) or not re.fullmatch('[a-z0-9-]{1,60}',a.label):p.error('Local origin and safe label required')
    folder=ROOT/'docs/evidence/studio3d-apple-2026-10-24'/a.label;folder.mkdir(parents=True,exist_ok=False)
    def get(path):return json.load(urllib.request.urlopen(a.origin+path,timeout=25))
    token=get('/api/session')['token']
    def post(path,value):return json.load(urllib.request.urlopen(urllib.request.Request(a.origin+path,data=json.dumps(value,ensure_ascii=False).encode(),headers={'Origin':a.origin,'X-Jarvis-Token':token,'Content-Type':'application/json'}),timeout=30))
    raw=Path(a.image).read_bytes();prompt=Path(a.prompt_file).read_text(encoding='utf-8')
    if len(prompt)>1600:p.error('Studio request text limit is 1600 characters')
    ref=post('/api/studio3d/references',{'name':'apple-reference.png','source':'Codex built-in image_gen, owner requested 2026-10-24; generated reference, not real photo','license':'Owner-requested AI generated reference for this original asset study','data':base64.b64encode(raw).decode()})
    (folder/'reference.png').write_bytes(raw)
    body={'id':uuid.uuid4().hex,'prompt':prompt,'provider':a.provider,'model':a.model,'reference':ref['id'],'vision_reference':True}
    result={'origin':a.origin,'reference':ref,'request':body,'paid_calls_requested':1}
    def save():(folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    save();result['accepted']=post('/api/studio3d/jobs',body);save();last=None
    for _ in range(480):
        job=get('/api/studio3d/jobs/'+body['id']);result['job']=job;save()
        if job['phase']!=last:print(job['status']+' '+job['phase'],flush=True);last=job['phase']
        if job['status'] not in ('QUEUED','PLANNING','BUILDING'):break
        time.sleep(1)
    if job['turn_id']:
        result['usage']=[u for u in get('/api/usage') if u.get('turn_id')==job['turn_id']];save()
    if job['status']!='DELIVERED':raise RuntimeError(str(job['error']))
    for filename in ('preview.png','view-front.png','view-left.png','view-top.png'):
        if filename in job['receipt']['files']:(folder/filename).write_bytes(urllib.request.urlopen(a.origin+job['receipt']['files'][filename]['url'],timeout=30).read())
    print(json.dumps({'id':body['id'],'status':job['status'],'triangles':job['receipt']['report']['triangles'],'quality':job['receipt']['quality'],'model_receipt':job['receipt']['model_receipt']},ensure_ascii=False))
if __name__=='__main__':main()
