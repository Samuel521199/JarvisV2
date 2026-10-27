"""Durable, single-job 3D plugin; model planning uses the existing dialogue lane."""
import hashlib,json,os,re,sqlite3,subprocess,threading,time,uuid
from pathlib import Path
from control.paths import child
from control.recovery.gate import StopGate
from modules.skills.catalog import Skills
from modules.skills.studio3d.contract import CONTRACT,validate
from modules.skills.studio3d.presets import PRESETS
from modules.skills.studio3d.assets import MAX_GLB_BYTES,MAX_GLB_BASE64_BYTES
from modules.dialogue.store import Dialogues
from sdk.protocol import CoreError,canonical,digest,decode

ROOT=Path(__file__).resolve().parents[1]
LOCK=threading.Lock()
ACTIVE={}
GUARD=threading.Lock()
REQUIRED_FILES=('preview.png','model.blend','model.glb','scene.json','report.json')
FILES={'preview.png':'image/png','model.blend':'application/octet-stream','model.glb':'model/gltf-binary','scene.json':'application/json','report.json':'application/json', 'model-lod1.glb':'model/gltf-binary','model-lod2.glb':'model/gltf-binary','basecolor.png':'image/png','normal.png':'image/png','orm.png':'image/png','ao.png':'image/png'}
FILES.update({('view-'+v+'.png'):'image/png' for v in ('front','rear','left','right','top')});FILES['reference.png']='image/png'
FILES['review.json']='application/json';FILES['surface-albedo.png']='image/png'
FILES.update({f'lod{level}-{channel}.png':'image/png' for level in (1,2) for channel in ('basecolor','normal','orm','ao')})
RUNTIME=json.loads((ROOT/'modules/skills/studio3d/runtime.json').read_text(encoding='utf-8'))

def db(root):
    d=sqlite3.connect(child(root,'state/studio3d.sqlite3'),timeout=5,isolation_level=None);d.row_factory=sqlite3.Row
    d.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,signature TEXT NOT NULL,status TEXT NOT NULL,phase TEXT NOT NULL,created REAL NOT NULL,chat_id TEXT,turn_id TEXT,error TEXT,cancel INTEGER NOT NULL DEFAULT 0,receipt TEXT)')
    return d
def enabled(root):
    StopGate(root).require_running();s=Skills(root)
    try:
        if not next(x for x in s.list() if x['id']=='studio3d')['enabled']:raise CoreError('skill_unavailable','3D Studio is disabled')
    finally:s.close()
def _readiness(root):
    try:
        lock=json.loads(child(root,'optional/studio3d/prepared.json').read_text(encoding='utf-8'));p=Path(lock['executable'])
        ready=p.is_file() and lock.get('runtime_sha256')==hashlib.sha256((ROOT/'modules/skills/studio3d/runtime.json').read_bytes()).hexdigest()
        return {'ready':ready,'version':lock.get('version'),'executable':str(p),'hash_check':'on every accepted build','adapter_version':'1.6.0','max_upload_bytes':MAX_GLB_BYTES,'limits':RUNTIME['limits'],'contract':CONTRACT}
    except (OSError,ValueError,KeyError):return {'ready':False,'adapter_version':'1.6.0','contract':CONTRACT,'error':'studio3d_not_prepared'}
def readiness(root):
    from modules.skills.studio3d.production import PROFILES,BRIEF,CATEGORY_GUIDANCE
    return {**_readiness(root),'production_profiles':PROFILES,'production_brief':BRIEF,'category_guidance':CATEGORY_GUIDANCE}

def update(root,ident,**changes):
    d=db(root)
    try:d.execute('UPDATE jobs SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',(*changes.values(),ident))
    finally:d.close()
def state(root,ident):
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise CoreError('studio3d_missing','Unknown 3D job')
    d=db(root)
    try:r=d.execute('SELECT * FROM jobs WHERE id=?',(ident,)).fetchone()
    finally:d.close()
    if not r:raise CoreError('studio3d_missing','Unknown 3D job')
    r=dict(r);r.pop('signature');r['receipt']=json.loads(r['receipt']) if r['receipt'] else None
    with GUARD:live=(str(root),ident) in ACTIVE
    if r['status'] in ('QUEUED','PLANNING','BUILDING') and not live:
        update(root,ident,status='UNKNOWN',phase='服务重启，未自动重放');r.update(status='UNKNOWN',phase='服务重启，未自动重放')
    if r['turn_id'] and r['status'] not in ('QUEUED','PLANNING'):
        store=Dialogues(root)
        try:
            t=store.turn(r['turn_id'])
            if t['status']=='SUCCEEDED':
                r['candidate']=model_candidate(t['reply'])
                r['planning_reference']=decode(t['request']).get('reference_image')
        except CoreError:pass
        finally:store.close()
    return r
def listing(root):
    d=db(root)
    try:ids=[r['id'] for r in d.execute('SELECT id FROM jobs ORDER BY created DESC LIMIT 20')]
    finally:d.close()
    return [state(root,i) for i in ids]
def check(root,ident):
    enabled(root);d=db(root)
    try:r=d.execute('SELECT cancel FROM jobs WHERE id=?',(ident,)).fetchone()
    finally:d.close()
    if not r or r['cancel']:raise CoreError('studio3d_cancelled','3D job cancelled')
def cancel(root,ident):
    r=state(root,ident)
    if r['status'] not in ('QUEUED','PLANNING','BUILDING'):return r
    update(root,ident,cancel=1)
    if r['turn_id']:
        s=Dialogues(root)
        try:s.cancel(r['turn_id'])
        finally:s.close()
    return {'id':ident,'status':'CANCEL_REQUESTED'}
def model_candidate(raw):
    # One enclosing JSON fence is transport normalization only, retained in turn.
    match=re.fullmatch(r'\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*',raw)
    if match:raw=match.group(1)
    try:
        v=validate(decode(raw))
        if any(k in v for k in ('asset','asset_pipeline','reference','master','surface_texture')):raise CoreError('studio3d_invalid','Model cannot choose private assets or start preparation')
        return v
    except (ValueError,TypeError):raise CoreError('studio3d_invalid','Model did not return valid scene data') from None
def start(root,body,dialogues):
    enabled(root)
    if not isinstance(body,dict) or set(body)-{'id','preset','scene','prompt','provider','model','render','asset','reuse_candidate','prepare_asset','texture_size','reference','production','vision_reference','refine','focus','reuse_review'} or not isinstance(body.get('id'),str) or not re.fullmatch('[a-f0-9]{32}',body['id']):raise CoreError('studio3d_invalid','Expected request ID')
    if 'reuse_review' in body and 'refine' not in body:raise CoreError('studio3d_invalid','Review reuse requires explicit refinement')
    if sum(k in body for k in ('preset','scene','prompt','asset','reuse_candidate','prepare_asset','refine'))!=1:raise CoreError('studio3d_invalid','Choose one 3D operation')
    if 'focus' in body and ('refine' not in body or not isinstance(body['focus'],str) or len(body['focus'])>1000):raise CoreError('studio3d_invalid','Focus belongs to bounded refinement')
    if 'texture_size' in body and 'prepare_asset' not in body:raise CoreError('studio3d_invalid','Texture size belongs to asset preparation')
    if 'production' in body and 'prepare_asset' not in body:raise CoreError('studio3d_invalid','Production requires a delivered high master')
    if 'vision_reference' in body and (type(body['vision_reference']) is not bool or not {'prompt','refine'}&body.keys() or body['vision_reference'] and 'reference' not in body):raise CoreError('studio3d_invalid','Image planning requires prompt and attached reference')
    scene=None
    if 'preset' in body:
        if not isinstance(body['preset'],str) or body['preset'] not in PRESETS:raise CoreError('studio3d_invalid','Unknown preset')
        scene=PRESETS[body['preset']]()
    elif 'scene' in body:scene=validate(body['scene'])
    elif 'prepare_asset' in body:
        prior=state(root,body['prepare_asset'])
        if prior['status']!='DELIVERED':raise CoreError('studio3d_invalid','Prepare a delivered asset')
        import copy
        scene=copy.deepcopy(prior['receipt']['configuration']);scene['asset_pipeline']={'texture_size':body.get('texture_size',512)};scene['title']=scene['title'][:60]+' · 烘焙与LOD';scene=validate(scene)
        if 'production' in body:
            from modules.skills.studio3d.production import PROFILES
            cfg=body['production']
            if not isinstance(cfg,dict) or set(cfg)-{'category','triangle_budget','ray_distance'} or not isinstance(cfg.get('category'),str) or cfg['category'] not in PROFILES:raise CoreError('studio3d_invalid','Choose a bounded production category')
            if prior['receipt']['configuration'].get('asset_pipeline'):raise CoreError('studio3d_invalid','Use the unbaked master, not an already baked low mesh')
            scene['asset_pipeline'].update(method='project',**cfg);scene['master']=prior['id'];scene['title']='游戏低模 · '+prior['receipt']['title'][:52]+' · PBR/LOD';scene=validate(scene)
    elif 'reuse_candidate' in body:
        prior=state(root,body['reuse_candidate'])
        if prior['status'] not in ('FAILED','CANCELLED','UNKNOWN','DELIVERED') or 'candidate' not in prior:raise CoreError('studio3d_invalid','No completed valid model plan to reuse')
        scene=prior['candidate']
    elif 'refine' in body:
        prior=state(root,body['refine'])
        if prior['status']!='DELIVERED' or any(k in prior['receipt']['configuration'] for k in ('asset','master','asset_pipeline')):raise CoreError('studio3d_invalid','Refine a delivered editable high scene')
        if not body.get('vision_reference') or 'reference' not in body or any(not isinstance(body.get(k),str) or not body[k] or body[k]=='auto' for k in ('provider','model')):raise CoreError('studio3d_invalid','Review requires explicit reference and model route')
    elif 'asset' in body:
        asset_record(root,body['asset']);scene=validate({'schema':CONTRACT['schema'],'units':'m','title':'导入资产 · 摄影棚渲染','asset':body['asset'],'materials':[{'id':'placeholder','color':'#888888'}],'objects':[],'unfulfilled':['资产由使用者提供，来源与使用权由导入记录声明。','导入和渲染不证明拓扑、机械结构或 3A 质量。']})
    else:
        if not isinstance(body['prompt'],str) or not 1<=len(body['prompt'].strip())<=1600 or any(not isinstance(body.get(k),str) or not body[k] or body[k]=='auto' for k in ('provider','model')):raise CoreError('studio3d_invalid','Select explicit model route')
    if scene is not None and {'provider','model'}&body.keys():raise CoreError('studio3d_invalid','No model call for a data build')
    if 'reference' in body or scene is not None and 'reference' in scene:
        from host.studio3d_reference import record
        reference=body.get('reference',scene.get('reference') if scene else None);record(root,reference)
        if scene is not None:scene['reference']=reference
    if scene is not None and 'surface_texture' in scene:
        from host.studio3d_reference import record
        record(root,scene['surface_texture']['reference'])
    if 'render' in body:
        if scene is None:raise CoreError('studio3d_invalid','Put render settings in generated scene')
        scene['render']=body['render'];scene=validate(scene)
    if not readiness(root)['ready']:raise CoreError('studio3d_not_prepared','Prepare installed Blender first')
    prepared=json.loads(child(root,'optional/studio3d/prepared.json').read_text(encoding='utf-8'))
    if hashlib.sha256(Path(prepared['executable']).read_bytes()).hexdigest()!=prepared['executable_sha256']:raise CoreError('studio3d_changed','Review changed Blender before any paid planning')
    d=db(root);signature=digest(body);ident=body['id']
    try:
        with GUARD:
            old=d.execute('SELECT signature FROM jobs WHERE id=?',(ident,)).fetchone()
            if old:
                if old['signature']!=signature:raise CoreError('conflict','Request identity already used')
                return {'id':ident,'existing':True}
            if ACTIVE:raise CoreError('busy','A 3D job is already active')
            if not LOCK.acquire(blocking=False):raise CoreError('busy','3D renderer busy')
            ACTIVE[(str(root),ident)]=True
            try:
                d.execute('INSERT INTO jobs(id,signature,status,phase,created) VALUES(?,?,?,?,?)',(ident,signature,'QUEUED','已受理',time.time()))
                t=threading.Thread(target=run,args=(root,body,scene,dialogues),daemon=True,name='studio3d-'+ident[:8]);t.start()
            except BaseException:ACTIVE.pop((str(root),ident),None);LOCK.release();raise
    finally:d.close()
    return {'id':ident,'existing':False}

def run(root,body,scene,dialogues):
    from host.studio3d_reference import record
    ident=body['id'];model_receipt=None;review=None
    try:
        if 'reuse_candidate' in body:
            prior=state(root,body['reuse_candidate']);model_receipt={'source_job':prior['id'],'chat_id':prior['chat_id'],'turn_id':prior['turn_id'],'status':'SUCCEEDED','new_model_calls':0,'visual_review':False}
            model_receipt['reference_image_sent']=bool(prior.get('planning_reference'))
            if prior.get('planning_reference'):model_receipt['reference_sha256']=record(root,prior['planning_reference'])[0]['sha256']
        check(root,ident)
        if 'refine' in body:
            from host.studio3d_refinement import begin
            scene,model_receipt,review=begin(root,body,dialogues)
        if scene is None:
            update(root,ident,status='PLANNING',phase='模型规划曲面与材质');store=Dialogues(root)
            try:
                chat=store.create();store.update(chat,{'title':'3D 工作室 · '+body['prompt'][:35]});turn='studio3d-'+ident
                update(root,ident,chat_id=chat,turn_id=turn)
                example=wheel_example()
                prompt='You plan original editable Blender visual assets as bounded DATA. Return one strict JSON object only. Do not output code, file paths, URLs or change schema. Use metres, Euler degrees. Prefer curved loft/lathe/mesh over stacked blocks. IDs lowercase letters/digits/hyphens. Maximum 24 objects for model output; keep geometry compact. Only supported fields. Materials require id/color; unspecified numeric values default. Objects require id/kind/material; optional position, rotation, scale, params, modifiers. Loft rings all have same width; closed rings/caps form solid. Lathe profile is radius,Z around local Z. Rotation [90,0,0] puts shaft along Y. Bezier curve points form a smooth tube. Cutters must precede target, visible=false. Report all unmet details honestly in unfulfilled. Do not claim OEM accuracy, full vehicle internals, 3A quality, mechanics/fluids/collision validation. Choose render quality=preview engine=CYCLES. Contract: '+canonical(CONTRACT)+'\nExample: '+canonical(example)+'\nUSER REQUEST:\n'+body['prompt']
                if len(prompt)>12000:raise CoreError('studio3d_invalid','Planning context budget exceeded')
                dialogues.submit_background({'chat_id':chat,'request_id':turn,'text':prompt,'provider':body['provider'],'model':body['model'],'reasoning':'default','skill':'none','memory_enabled':False,**({'reference_image':body['reference']} if body.get('vision_reference') else {})})
                deadline=time.monotonic()+160
                while True:
                    check(root,ident);r=store.turn(turn)
                    if r['status'] not in ('READY','RUNNING'):break
                    if time.monotonic()>deadline:
                        store.cancel(turn);raise CoreError('model_unknown','Model deadline reached; no replay')
                    time.sleep(.25)
                if r['status']!='SUCCEEDED':raise CoreError('model_unknown' if r['status']=='UNKNOWN' else 'studio3d_model_failed','3D planning did not succeed')
                scene=model_candidate(r['reply']);model_receipt={'chat_id':chat,'turn_id':turn,'provider':body['provider'],'model':body['model'],'status':r['status'],'visual_review':False,'reference_image_sent':body.get('vision_reference',False),'reference_sha256':record(root,body['reference'])[0]['sha256'] if body.get('vision_reference') else None}
                if 'reference' in body:scene['reference']=body['reference']
            finally:store.close()
        check(root,ident);update(root,ident,status='BUILDING',phase='Blender 曲面建模与渲染');receipt=build(root,ident,scene,model_receipt)
        if review is not None:
            from host.studio3d_refinement import finish
            receipt=finish(root,body,dialogues,receipt,review)
        if 'prepare_asset' in body:
            receipt['derived_from']=body['prepare_asset'];child(root,'artifacts/studio3d/'+ident+'/receipt.json').write_text(canonical(receipt),encoding='utf-8')
        check(root,ident);update(root,ident,status='DELIVERED',phase='已交付可编辑模型、渲染与检查回执',receipt=canonical(receipt))
    except BaseException as exc:
        if 'prompt' in body:
            pending=Dialogues(root)
            try:
                try:pending.cancel('studio3d-'+ident)
                except CoreError:pass
            finally:pending.close()
        code=exc.code if isinstance(exc,CoreError) else 'studio3d_build_failed'
        update(root,ident,status='CANCELLED' if code in ('studio3d_cancelled','stopped','skill_unavailable') else 'UNKNOWN' if code=='model_unknown' else 'FAILED',phase='没有自动重试',error=code)
    finally:
        with GUARD:ACTIVE.pop((str(root),ident),None)
        LOCK.release()
def wheel_example():
    return {'schema':'jarvis.studio3d.v1','units':'m','title':'曲面壳体','materials':[{'id':'metal','color':'#617e94','metallic':.8,'roughness':.25}], 'objects':[{'id':'shell','kind':'lathe','material':'metal','params':{'profile':[[.1,0],[.15,.05],[.2,.2],[.18,.4],[.16,.42]],'segments':64},'modifiers':{'thickness':.008}}],'unfulfilled':['没有制造尺寸与载荷验证。'],'render':{'quality':'preview','engine':'CYCLES','view':'front'}}

def build(root,ident,scene,model_receipt=None):
    import ctypes
    from ctypes import wintypes as w
    lock=json.loads(child(root,'optional/studio3d/prepared.json').read_text(encoding='utf-8'));exe=Path(lock['executable'])
    if hashlib.sha256(exe.read_bytes()).hexdigest()!=lock['executable_sha256']:raise CoreError('studio3d_changed','Blender changed; prepare and review again')
    folder=child(root,'artifacts/studio3d/'+ident);folder.mkdir(parents=True,exist_ok=False)
    source_paths=['host/studio3d.py',RUNTIME['worker'],RUNTIME['bootstrap'],'adapters/studio3d/asset_pipeline.py','adapters/studio3d/projection.py','modules/skills/studio3d/production.py','modules/skills/studio3d/contract.py','modules/skills/studio3d/presets.py','modules/skills/studio3d/tracked_vehicle.py','host/studio3d_reference.py','adapters/models/vision.py','adapters/models/native.py','adapters/models/native_transport.py','host/dialogue.py','modules/dialogue/store.py','adapters/studio3d/organic.py','adapters/studio3d/framing.py','modules/skills/studio3d/assets.py','modules/skills/studio3d/runtime.json']
    source_snapshot={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths}
    for p in ('host/studio3d_refinement.py','modules/skills/studio3d/refinement.py','adapters/studio3d/weathering.py'):source_snapshot[p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    asset=None;reference=None;surface_texture=None
    frozen_master=None
    if 'master' in scene:
        prior=state(root,scene['master'])
        if prior['status']!='DELIVERED' or prior['receipt']['configuration'].get('asset_pipeline') or prior['receipt']['quality']['status']=='needs_revision':raise CoreError('studio3d_invalid','Use a delivered unbaked master with valid format checks')
        raw,_=file(root,scene['master'],'model.blend');(folder/'source.blend').write_bytes(raw)
        names=[o['id'] for o in prior['receipt']['report']['objects']]
        (folder/'master-parts.json').write_text(canonical(names),encoding='utf-8')
        frozen_master={'id':scene['master'],'blend_sha256':hashlib.sha256(raw).hexdigest(),'parts':names,'source':'SHA-verified first-party delivered blend; external blend upload unsupported'}
    if 'reference' in scene:
        from host.studio3d_reference import record
        reference,raw=record(root,scene['reference']);(folder/'reference.png').write_bytes(raw)
    if 'surface_texture' in scene:
        from host.studio3d_reference import record
        surface_texture,raw=record(root,scene['surface_texture']['reference']);(folder/'surface-albedo.png').write_bytes(raw)
    if 'asset' in scene:
        import shutil
        asset=asset_record(root,scene['asset']);shutil.copyfile(child(root,'artifacts/studio3d-assets/'+scene['asset']+'.glb'),folder/'source.glb')
    (folder/'scene.json').write_text(canonical(scene),encoding='utf-8');(folder/'config').mkdir();out=folder/'stdout.log';err=folder/'stderr.log'
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR')};env.update(TEMP=str(folder),TMP=str(folder),BLENDER_USER_CONFIG=str(folder/'config'),BLENDER_USER_SCRIPTS=str(folder/'config'),OMP_NUM_THREADS='4')
    job=None;native=None;began=time.monotonic();phase=''
    with out.open('wb') as stdout,err.open('wb') as stderr:
        process=subprocess.Popen([str(exe),'--background','--factory-startup','--disable-autoexec','--threads','4','--python-exit-code','2','--python',str(ROOT/RUNTIME['bootstrap']),'--',str(folder)],cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            if os.name=='nt':
                from control.worker import win32 as n
                native=n.bind();job=native['CreateJobObjectW'](None,None);limits=n.JobLimit();limits.basic.flags=0x2000|0x8|0x100|0x200|0x2;limits.basic.processes=2;limits.basic.cpu=1200*10_000_000;limits.memory=limits.job_memory=4*1024**3
                assign=n.api('kernel32','AssignProcessToJobObject',w.BOOL,w.HANDLE,w.HANDLE)
                if not job or not native['SetInformationJobObject'](job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not assign(job,int(process._handle)):raise CoreError('studio3d_limit','Resource Job unavailable')
            while process.poll() is None:
                check(root,ident)
                if time.monotonic()-began>300 or sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())>256*1024**2 or out.stat().st_size>2*1024**2 or err.stat().st_size>2*1024**2:raise CoreError('studio3d_limit','3D task exceeded resource budget')
                tail=out.read_text(encoding='utf-8',errors='replace')[-4000:];phases=re.findall(r'STUDIO3D ([^\r\n]+)',tail)
                if phases and phases[-1]!=phase:phase=phases[-1];update(root,ident,phase='Blender · '+phase)
                time.sleep(.15)
            if process.returncode:raise CoreError('studio3d_build_failed','Fixed Blender worker failed')
        finally:
            if process.poll() is None:process.kill()
            process.wait();resource={'elapsed_seconds':time.monotonic()-began,'exit_code':process.returncode,**RUNTIME['limits'],'isolation':RUNTIME['isolation']}
            if job:
                measured=n.JobLimit()
                if native['QueryInformationJobObject'](job,9,ctypes.byref(measured),ctypes.sizeof(measured),None):resource['peak_memory_bytes']=measured.job_peak
                native['CloseHandle'](job)
            (folder/'execution.json').write_text(canonical(resource),encoding='utf-8')
    check(root,ident);files={}
    if scene['render'].get('five_views') and any(not (folder/('view-'+v+'.png')).is_file() for v in ('front','rear','left','right','top')):raise CoreError('studio3d_build_failed','Five-view delivery incomplete')
    if sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())>256*1024**2:raise CoreError('studio3d_limit','Final output quota exceeded')
    for name in FILES:
        p=folder/name
        if not p.is_file() and name not in REQUIRED_FILES:continue
        if not p.is_file() or not 10<p.stat().st_size<128*1024**2:raise CoreError('studio3d_build_failed','Required deliverable absent')
        files[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'url':'/api/studio3d/files/'+ident+'/'+name}
    report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
    if not report['glb_roundtrip']['passed']:raise CoreError('studio3d_build_failed','GLB roundtrip bounds failed')
    import shutil
    node=shutil.which('node')
    if not node:raise CoreError('studio3d_build_failed','Node required for official GLB validation')
    manifest=json.loads((ROOT/'external/gltf-validator/source.json').read_text(encoding='utf-8'))
    for name,row in manifest['files'].items():
        if hashlib.sha256((ROOT/'external/gltf-validator'/name).read_bytes()).hexdigest()!=row['sha256']:raise CoreError('studio3d_changed','Reviewed validator changed')
    validations={}
    for name in ('model.glb','model-lod1.glb','model-lod2.glb'):
        if not (folder/name).is_file():continue
        check(root,ident);result=subprocess.run([node,'--max-old-space-size=256',str(ROOT/'adapters/studio3d/validate.cjs'),str(folder/name)],capture_output=True,timeout=20,env=env,cwd=folder,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode or len(result.stdout)>200000:raise CoreError('studio3d_build_failed','Official validator failed')
        validations[name]=json.loads(result.stdout)
    report['gltf_validation']={'implementation':'Khronos glTF-Validator','version':manifest['version'],'files':validations}
    (folder/'report.json').write_text(canonical(report),encoding='utf-8')
    files['report.json']={'sha256':hashlib.sha256((folder/'report.json').read_bytes()).hexdigest(),'bytes':(folder/'report.json').stat().st_size,'url':'/api/studio3d/files/'+ident+'/report.json'}
    receipt={'id':ident,'skill':'studio3d','adapter_version':'1.6.0','title':scene['title'],'url':'/api/studio3d/view/'+ident,'files':files,'report':report,'configuration':scene,'model_receipt':model_receipt,'resources':resource,'runtime':{k:lock[k] for k in ('version','executable_sha256','source','license')},'source_sha256':source_snapshot,'quality':{'status':'visual_asset_export_checked','AAA_certified':False,'visual_score':None,'mechanical_validation':False},'unfulfilled':scene['unfulfilled']}
    receipt['input_asset']=asset
    receipt['frozen_master']=frozen_master
    receipt['reference']=reference
    receipt['surface_texture']=surface_texture
    if any(r.get('issues',{}).get('numErrors',0) or r.get('issues',{}).get('truncated') for r in validations.values()) or any(r['status']=='fail' for r in report.get('asset_pipeline',{}).get('checks',[])):receipt['quality']['status']='needs_revision'
    (folder/'receipt.json').write_text(canonical(receipt),encoding='utf-8');return receipt

def upload(root,body):
    import base64
    from modules.skills.studio3d.assets import validate_glb
    enabled(root)
    if not isinstance(body,dict) or set(body)!={'name','source','license','data'} or any(not isinstance(body[k],str) for k in body) or not 1<=len(body['name'])<=100 or not 1<=len(body['source'])<=500 or not 1<=len(body['license'])<=200 or len(body['data'])>MAX_GLB_BASE64_BYTES:raise CoreError('studio3d_asset_invalid','Supply asset provenance and GLB data')
    try:raw=base64.b64decode(body['data'],validate=True)
    except ValueError:raise CoreError('studio3d_asset_invalid','Invalid base64') from None
    checks=validate_glb(raw);ident=uuid.uuid4().hex;folder=child(root,'artifacts/studio3d-assets');folder.mkdir(parents=True,exist_ok=True)
    record={'id':ident,**{k:body[k] for k in ('name','source','license')},'sha256':hashlib.sha256(raw).hexdigest(),'checks':checks,'provenance_verified':False}
    (folder/(ident+'.glb')).write_bytes(raw);(folder/(ident+'.json')).write_text(canonical(record),encoding='utf-8');return record
def asset_record(root,ident):
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise CoreError('studio3d_asset_invalid','Invalid asset')
    folder=child(root,'artifacts/studio3d-assets');r=json.loads((folder/(ident+'.json')).read_text(encoding='utf-8'));raw=(folder/(ident+'.glb')).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise CoreError('studio3d_changed','Asset changed')
    return r

def file(root,ident,name):
    r=state(root,ident)
    if r['status']!='DELIVERED' or name not in FILES or name not in r['receipt']['files']:raise CoreError('studio3d_missing','No delivered file')
    p=child(root,'artifacts/studio3d/'+ident+'/'+name);raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=r['receipt']['files'][name]['sha256']:raise CoreError('studio3d_changed','Artifact changed')
    return raw,FILES[name]
def view(root,ident):
    from host.studio3d_viewer import page
    return page(root,ident)
