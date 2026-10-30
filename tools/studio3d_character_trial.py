"""One bounded, asset-scoped character blockout and Jarvis review trial."""
import base64, hashlib, json, shutil, sys, time, urllib.request, uuid
from pathlib import Path
from control.local_access import install_client
from control.recovery.gate import StopGate
from host.studio3d_learning import _process, validate_export
from modules.skills.studio3d.character_contract import FAMILY, parameters, validate, VIEWS
from modules.skills.studio3d.character_recipe import scene
from modules.context_knowledge.character_experience import methods, record
from modules.workspace.store import Workspace

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'user-data'
ASSET=ROOT/'3DModels/SilverHairCharacter'
ORIGIN='http://127.0.0.1:18282'
SOURCE=Path('C:/Users/samuel/Desktop/模型')
FILES={'front':'前.png','rear':'后.png','right':'右.png','left':'左.png'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def get(path):
    with urllib.request.urlopen(ORIGIN+path,timeout=30) as r:return json.load(r)
def post(path,body):
    token=get('/api/session')['token']
    req=urllib.request.Request(ORIGIN+path,json.dumps(body,ensure_ascii=False).encode(),{'Content-Type':'application/json','Origin':ORIGIN,'X-Jarvis-Token':token})
    with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
def upload(path,label):
    return post('/api/studio3d/references',{'name':label,'source':'User-supplied character project reference or actual Blender render','license':'User-provided task reference','data':base64.b64encode(path.read_bytes()).decode()})['id']
def ask(project,route,key,text,images):
    chat=post('/api/chats',{'project_id':project})['id']
    post('/api/chat/update',{'id':chat,'patch':{'title':'人物建模 · '+key}})
    request='character-'+uuid.uuid4().hex
    post('/api/chat/send',{'chat_id':chat,'request_id':request,'text':text,'provider':route['provider'],'model':route['model'],
         'reasoning':'default','skill':'none','memory_enabled':False,'reference_images':images})
    for _ in range(240):
        row=get('/api/chats/'+chat);turn=next((t for t in row['turns'] if t['id']==request),None)
        if turn and turn['status'] not in ('READY','RUNNING'):
            if turn['status']!='SUCCEEDED':raise RuntimeError('Character model call failed: '+str(turn.get('error')))
            return {'chat_id':chat,'request_id':request,'reply':turn['reply'],'status':'SUCCEEDED'}
        time.sleep(1)
    raise TimeoutError('Character model call unknown; do not replay')

def main():
    StopGate(DATA).require_running()
    instance=get('/api/instance')
    if instance.get('root_digest')!=hashlib.sha256(str(DATA.resolve()).casefold().encode()).hexdigest():raise ValueError('Wrong Jarvis instance')
    install_client(ORIGIN,DATA)
    if ASSET.exists():raise ValueError('Character trial already exists; inspect state before resuming')
    ASSET.mkdir();refs=ASSET/'references';refs.mkdir();meta=ASSET/'metadata';meta.mkdir()
    state={'status':'INITIALIZING','family':FAMILY,'asset_id':'character-silverhair-01','user_approval':False,'automatic_promotion':False,
           'limitations':['Authored fixed character blockout, not an autonomous learned mesh generator','No rig, animation, deformation or game-ready topology'],
           'author_intervention':'Codex authored the fixed recipe and controller; Jarvis reviews the actual outputs.'}
    path=meta/'trial.json';save(path,state)
    try:
        frozen={}
        for view,name in FILES.items():
            dest=refs/(view+'.png');shutil.copyfile(SOURCE/name,dest)
            if sha(dest)!=sha(SOURCE/name):raise ValueError('Reference copy mismatch')
            frozen[view]=sha(dest)
        contract=validate({'schema':'jarvis.studio3d.character.v1','family':FAMILY,'asset_id':state['asset_id'],
            'parameters':parameters(),'reference_sha256':frozen,'stage':'static_base'})
        save(meta/'contract.json',contract);save(meta/'methods.json',methods(FAMILY))
        workspace=Workspace(DATA)
        try:project=workspace.open(str(ASSET))['id']
        finally:workspace.close()
        state.update(project_id=project,reference_sha256=frozen,status='REFERENCE_ANALYSIS');save(path,state)
        settings=get('/api/snapshot')['settings'];choice=next(c for c in settings['connections'] if c['id']==settings['default_provider'])
        route={'provider':choice['id'],'model':choice['model']};state['route']=route;save(path,state)
        refids={v:upload(refs/(v+'.png'),'人物参考 '+v) for v in VIEWS}
        state['reference_ids']=refids;save(path,state)
        prompt='你正在单独学习一个风格化人物的静态三维基础模型。图片为用户提供的建模参考。请客观描述人物轮廓、比例、发型、脸部、姿态和四视图之间可能的遮挡；不要提供代码或假设已完成绑定。回答简短，提出可检查的几项要点。'
        state['reference_analysis']=ask(project,route,'参考分析',prompt,[refids['front'],refids['right']]);save(path,state)
        ident=uuid.uuid4().hex;folder=DATA/'artifacts/studio3d-character'/ident;folder.mkdir(parents=True)
        save(folder/'scene.json',scene(contract['parameters']))
        state.update(status='BUILDING',run_id=ident);save(path,state)
        prepared=json.loads((DATA/'optional/studio3d/prepared.json').read_text(encoding='utf-8'))
        exe=Path(prepared['executable'])
        if sha(exe)!=prepared['executable_sha256']:raise ValueError('Blender executable changed')
        _process(DATA,folder,exe,operation='character')
        report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
        if not report['glb_roundtrip']['passed']:raise ValueError('GLB roundtrip failed')
        format_report=validate_export(folder/'model.glb');save(folder/'format-validation.json',format_report)
        out=ASSET/'blockout-01';out.mkdir()
        for name in ['model.blend','model.glb','preview.png','report.json','format-validation.json','resource-lane.json']+['view-'+v+'.png' for v in ('front','rear','left','right','top')]:
            if (folder/name).is_file():shutil.copyfile(folder/name,out/name)
        hashes={p.name:sha(p) for p in out.iterdir() if p.is_file()}
        save(out/'manifest.json',hashes);state.update(status='REVIEWING',files=hashes,output=str(out));save(path,state)
        reviews={}
        for view in ('front','right'):
            render=out/('view-'+view+'.png')
            if not render.exists():continue
            image=upload(render,'人物草模真实渲染 '+view)
            reviews[view]=ask(project,route,view+' 对照','第一张为人物建模参考，第二张为实际 Blender 静态草模。客观比较头身比例、整体轮廓、面部、头发、手脚和连接部位。列出明显缺点，不要把草模说成完成；不输出代码。',[refids[view],image])
            state['reviews']=reviews;save(path,state)
        evidence=sha(out/'manifest.json')
        record(DATA,family=FAMILY,asset_id=state['asset_id'],iteration='blockout-01',evidence_sha256=evidence,reviews=reviews)
        state.update(status='BLOCKOUT_REVIEWED',user_approval=False);save(path,state)
        print(json.dumps({'status':state['status'],'project_id':project,'output':str(out),'reviews':list(reviews)},ensure_ascii=False),flush=True)
    except BaseException as exc:
        state.update(status='INTERRUPTED_OR_FAILED',error=str(exc));save(path,state);raise

if __name__=='__main__':main()
