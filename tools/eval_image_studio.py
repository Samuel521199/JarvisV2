"""Explicit real API smoke tests. Each model is called once, never retried."""
import argparse,json,time,uuid
from pathlib import Path
from host.image_generation import start,state,cancel,ACTIVE
from modules.image_generation.catalog import MODELS

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-root',required=True);p.add_argument('--provider',required=True);p.add_argument('--model',choices=MODELS,required=True);p.add_argument('--evidence',required=True);p.add_argument('--reference');p.add_argument('--size',default='1K');p.add_argument('--ratio',default='1:1');p.add_argument('--preset',default='free');p.add_argument('--prompt',default='Create one clean product illustration of a small blue industrial water pump, metal housing, brass fittings, white background, no text.');a=p.parse_args()
    root=Path(a.data_root).resolve();body={'id':uuid.uuid4().hex,'provider':a.provider,'model':a.model,'prompt':a.prompt,'size':a.size,'aspect_ratio':a.ratio,'design':{'preset':a.preset,'audience':'','style':'','constraints':''},'references':[a.reference] if a.reference else []}
    start(root,body);deadline=time.monotonic()+300;cancelled=False
    while True:
        r=state(root,body['id'])
        if r['status'] in {'SUCCEEDED','FAILED','UNKNOWN','CANCELLED'} and (str(root),body['id']) not in ACTIVE:break
        if time.monotonic()>deadline:
            if not cancelled:cancel(root,body['id']);cancelled=True;deadline=time.monotonic()+15
            else:break
        time.sleep(.2)
    target=Path(a.evidence);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'id':r['id'],'model':a.model,'status':r['status'],'error':r['error'],'file':r['receipt']['file'] if r['receipt'] else None},ensure_ascii=False))
    return 0 if r['status']=='SUCCEEDED' else 1
if __name__=='__main__':raise SystemExit(main())
