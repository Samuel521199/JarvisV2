"""Explicit local/paid plugin acceptance; each case preserves its raw receipt."""
import argparse,base64,json,time,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--origin',default='http://127.0.0.1:18282');p.add_argument('--label',required=True);p.add_argument('--preset');p.add_argument('--prompt');p.add_argument('--model',default='gemini-4-argon');p.add_argument('--import-glb');p.add_argument('--reuse');p.add_argument('--final',action='store_true');p.add_argument('--eevee',action='store_true');a=p.parse_args()
    import re
    if not re.fullmatch('http://127.0.0.1:[0-9]{4,5}',a.origin) or not re.fullmatch('[a-z0-9-]{1,40}',a.label):p.error('Local origin and safe label required')
    folder=ROOT/'docs/evidence/studio3d-2026-10-23'/a.label;folder.mkdir(parents=True,exist_ok=False);output=folder/'result.json';record={'status':'running','origin':a.origin,'id':uuid.uuid4().hex,'paid_model_calls_requested':1 if a.prompt else 0}
    def save():output.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    def get(path):return json.load(urllib.request.urlopen(a.origin+path,timeout=15))
    token=get('/api/session')['token']
    def post(path,value):return json.load(urllib.request.urlopen(urllib.request.Request(a.origin+path,data=json.dumps(value,ensure_ascii=False).encode(),headers={'Origin':a.origin,'X-Jarvis-Token':token,'Content-Type':'application/json'}),timeout=25))
    try:
        body={'id':record['id']}
        if a.prompt:body.update(prompt=a.prompt,provider='vertex',model=a.model)
        elif a.reuse:body['reuse_candidate']=a.reuse
        elif a.import_glb:
            asset=post('/api/studio3d/assets',{'name':'Jarvis original acceptance.glb','source':'Jarvis first-party wheel study acceptance','license':'Original project test asset','data':base64.b64encode(Path(a.import_glb).read_bytes()).decode()});body['asset']=asset['id'];record['input_asset']=asset
        else:body['preset']=a.preset or 'gt-study'
        if not a.prompt:body['render']={'quality':'final' if a.final else 'preview','engine':'BLENDER_EEVEE_NEXT' if a.eevee else 'CYCLES','view':'front'}
        record['request']=body;save();record['accepted']=post('/api/studio3d/jobs',body);save();deadline=time.monotonic()+470;last=None
        while time.monotonic()<deadline:
            r=get('/api/studio3d/jobs/'+record['id']);record['job']=r;save()
            if r['phase']!=last:print(r['status']+' '+r['phase'],flush=True);last=r['phase']
            if r['status'] not in ('QUEUED','PLANNING','BUILDING'):break
            time.sleep(1)
        if r['status']!='DELIVERED':raise RuntimeError('3D job '+r['status']+': '+str(r['error']))
        receipt=r['receipt'];image=urllib.request.urlopen(a.origin+receipt['files']['preview.png']['url']).read();(folder/'preview.png').write_bytes(image)
        record['idempotent_replay']=post('/api/studio3d/jobs',body);assert record['idempotent_replay']['existing']
        if r['turn_id']:record['usage']=[u for u in get('/api/usage') if u['turn_id']==r['turn_id']]
        record['status']='passed';save();print(json.dumps({'status':'passed','id':record['id'],'triangles':receipt['report']['triangles'],'objects':receipt['report']['visible_objects'],'resources':receipt['resources'],'model_receipt':receipt['model_receipt']},ensure_ascii=False))
    except BaseException as exc:record.update(status='failed',error=str(exc));save();raise
if __name__=='__main__':main()
