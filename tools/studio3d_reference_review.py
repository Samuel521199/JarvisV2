"""Run paired-image reviews through Jarvis, retaining usage and errors.

Invoke from the repository root with python -m tools.studio3d_reference_review.
Imports resolve inside this project without modifying the interpreter path.
"""
import argparse,base64,datetime,hashlib,json,sys,time,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from modules.skills.studio3d.hard_surface_review import prompt,parse,review_gate,VIEWS
from modules.skills.studio3d.review_evidence import verify_manifest
from modules.skills.studio3d.reference_policy import from_recipe,review_context_hash
p=argparse.ArgumentParser();p.add_argument('--origin',default='http://127.0.0.1:18283');p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--renders',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--iteration',required=True);p.add_argument('--provider',required=True);p.add_argument('--model',required=True);p.add_argument('--views',nargs='+',choices=VIEWS,default=list(VIEWS));p.add_argument('--facts',type=Path);p.add_argument('--evidence',type=Path);p.add_argument('--focus',type=Path,help='Optional per-view unretouched pixel crop boxes; requires full candidate evidence');p.add_argument('--data-root',type=Path,default=ROOT/'user-data');p.add_argument('--learning-contract',type=Path);p.add_argument('--fresh',action='store_true',help='Do not prime the reviewer with earlier correction labels');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
facts=json.loads(a.facts.read_text(encoding='utf-8')) if a.facts else None
reference_policy=from_recipe(a.asset_root)
methods=[]
if a.learning_contract:
    from host.studio3d_learning import plan
    selected=plan(a.data_root,json.loads(a.learning_contract.read_text(encoding='utf-8')))
    reference_policy=selected['contract']['reference_policy'];methods=selected['methods']

focus=json.loads(a.focus.read_text(encoding='utf-8')) if a.focus else {}
context_sha256=review_context_hash(reference_policy,facts,methods)
if focus and not a.evidence:raise ValueError('Detail crops require verified full-view candidate evidence')
evidence=verify_manifest(json.loads(a.evidence.read_text(encoding='utf-8')),{view:a.renders/(view+'.png') for view in a.views}) if a.evidence else None
if evidence and not focus and evidence['iteration']!=a.iteration:raise ValueError('Review iteration does not match the captured model')
def get(path):return json.load(urllib.request.urlopen(a.origin+path,timeout=30))
def post(path,body):
    token=get('/api/session')['token'];req=urllib.request.Request(a.origin+path,data=json.dumps(body,ensure_ascii=False).encode(),headers={'Origin':a.origin,'X-Jarvis-Token':token,'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=60))
def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def upload(path,name):
    data=path.read_bytes();reply=post('/api/studio3d/references',{'name':name,'source':'User-directed static exterior game-art paired image audit','license':'User project references or actual Blender render','data':base64.b64encode(data).decode()})
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(data).hexdigest(),'jarvis_reference_id':reply['id']}

def snapshot(path,view):
    dest=a.output/'review-inputs'/a.iteration/(view+'.png');dest.parent.mkdir(parents=True,exist_ok=True)
    data=path.read_bytes()
    if dest.exists() and dest.read_bytes()!=data:raise ValueError('Iteration already has different input pixels; choose a new iteration ID')
    if not dest.exists():dest.write_bytes(data)
    return dest

def focus_image(path,view,kind):
    if not focus:return path,None
    from PIL import Image
    spec=focus[view];box=spec[kind]
    if not isinstance(box,list) or len(box)!=4 or any(type(x)!=int for x in box):raise ValueError('Crop box must contain four integer pixel coordinates')
    with Image.open(path) as im:
        x0,y0,x1,y1=box
        if not (0<=x0<x1<=im.width and 0<=y0<y1<=im.height):raise ValueError('Crop outside original image')
        dest=a.output/'review-inputs'/a.iteration/(view+'-'+kind+'-crop.png');dest.parent.mkdir(parents=True,exist_ok=True)
        import io
        data=io.BytesIO();im.crop(box).save(data,format='PNG');raw=data.getvalue()
        if dest.exists() and dest.read_bytes()!=raw:raise ValueError('Crop iteration already contains different pixels')
        if not dest.exists():dest.write_bytes(raw)
    return dest,{'source_path':str(path.resolve()),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'box':box,'operation':'crop only; no retouch, repaint, resizing or color changes'}
ledger=a.output/'vision-results.json';rows=json.loads(ledger.read_text(encoding='utf-8')) if ledger.exists() else []
for view in a.views:
    stage=a.iteration+'-'+view
    existing=next((x for x in rows if x['stage']==stage),None)
    if existing:
        if existing.get('context_sha256')!=context_sha256:raise ValueError('Cached review uses a different or unrecorded reference policy/experience context; choose a new iteration ID')
        if existing.get('coverage','full')!=('detail' if focus else 'full'):raise ValueError('Cached review covers a different image scope')
        if evidence and (existing.get('candidate_evidence') or {}).get('model_sha256')!=evidence['model_sha256']:raise ValueError('Cached review belongs to another model hash')
        if focus:
            if any((existing.get('crops') or {}).get(k,{}).get('box')!=focus[view][k] for k in ('reference','render')):raise ValueError('Cached review used different crop boxes')
        elif existing['render']['sha256']!=hashlib.sha256((a.renders/(view+'.png')).read_bytes()).hexdigest():raise ValueError('Cached review used different rendered pixels')
        if existing.get('status')=='SUCCEEDED' and 'audit' not in existing:
            try:existing['audit']=parse(existing['reply'],view);existing['audit']['coverage']=existing.get('coverage','full');existing.pop('parse_error',None)
            except (ValueError,TypeError) as exc:existing['parse_error']=str(exc)
            save(ledger,rows)
        print(stage+' retained '+existing.get('status','submitted'),flush=True);continue
    reference_path,reference_crop=focus_image(a.asset_root/('reference-'+view+'.png'),view,'reference')
    render_path,render_crop=focus_image(a.renders/(view+'.png'),view,'render')
    reference=upload(reference_path,a.iteration+' reference '+view)
    rendered=upload(snapshot(render_path,view),a.iteration+' actual render '+view)
    previous=None if a.fresh else next((x['audit'] for x in reversed(rows) if x.get('view')==view and 'audit' in x),None)
    chat=post('/api/chats',{})['id'];turn='art-review-'+uuid.uuid4().hex
    post('/api/chat/update',{'id':chat,'patch':{'title':a.asset_root.name+' '+stage+' visual review'}})
    body={'chat_id':chat,'request_id':turn,'text':prompt(view,a.iteration,previous,facts,focus[view]['label'] if focus else None,reference_policy,methods),'provider':a.provider,'model':a.model,'reasoning':'default','skill':'none','memory_enabled':False,'reference_images':[reference['jarvis_reference_id'],rendered['jarvis_reference_id']]}
    row={'stage':stage,'view':view,'kind':'jarvis-model','turn_id':turn,'chat_id':chat,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reference':reference,'render':rendered,'candidate_evidence':evidence,'coverage':'detail' if focus else 'full','crops':{'reference':reference_crop,'render':render_crop} if focus else None,'request':body,'context_sha256':context_sha256,'reference_policy':reference_policy,'retrieved_methods':[{'id':m['id'],'revision':m['revision']} for m in methods],'status':'submitted'};rows.append(row);save(ledger,rows);tick=time.monotonic()
    try:
        row['accepted']=post('/api/chat/send',body)
        for _ in range(180):
            state=get('/api/chats/'+chat);item=next((x for x in state['turns'] if x['id']==turn),None)
            if item and item['status'] not in ('READY','RUNNING'):break
            time.sleep(1)
        else:raise RuntimeError('Review observation timed out; request retained, no resubmission')
        row.update(status=item['status'],reply=item.get('reply'),error=item.get('error'))
        row['usage']=[x for x in get('/api/usage') if x['turn_id']==turn]
        if item['status']=='SUCCEEDED':
            try:row['audit']=parse(item['reply'],view);row['audit']['coverage']=row['coverage']
            except (ValueError,TypeError) as exc:row['parse_error']=str(exc)
    except Exception as exc:row['observer_error']=str(exc);raise
    finally:row['elapsed_seconds']=time.monotonic()-tick;row['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save(ledger,rows)
    print(stage+' '+row['status']+' '+row.get('audit',{}).get('verdict',''),flush=True)
    if row['status']!='SUCCEEDED':break
save(a.output/(a.iteration+'-gate.json'),review_gate([r['audit'] for r in rows if r['stage'].startswith(a.iteration+'-') and 'audit' in r]))
