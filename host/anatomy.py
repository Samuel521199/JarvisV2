"""Trusted Anatomy renderer; only bounded declarative scene data enters templates."""
import hashlib,json,math,os,re,shutil,subprocess,threading,uuid
from pathlib import Path
from control.paths import child
from control.recovery.gate import StopGate
from modules.skills.catalog import Skills
from sdk.protocol import CoreError
from host.anatomy_scene import validate_scene,PRESETS
ROOT=Path(__file__).resolve().parents[1]
LOCK=threading.Lock()
def validate_request(value):
    if not isinstance(value,dict) or 'mechanism' not in value:raise CoreError('anatomy_invalid','Select a mechanism')
    mechanism=value['mechanism']
    if mechanism=='slider-crank' and set(value)=={'mechanism'}:return mechanism,{}
    if mechanism=='studio':
        if set(value)=={'mechanism','scene'}:return mechanism,validate_scene(value['scene'])
        if set(value)<={'mechanism','preset'} and isinstance(value.get('preset','engine'),str) and value.get('preset','engine') in PRESETS:return mechanism,validate_scene(PRESETS[value.get('preset','engine')])
        raise CoreError('anatomy_scene_invalid','Select one scene or registered preset')
    if mechanism!='planetary' or set(value)-{'mechanism','sun_teeth','planet_teeth','mode'}:raise CoreError('anatomy_invalid','Unknown mechanism or parameters')
    sun=value.get('sun_teeth',24);planet=value.get('planet_teeth',18);mode=value.get('mode','ring-fixed')
    if type(sun) is not int or type(planet) is not int or not 18<=sun<=48 or not 18<=planet<=36 or mode not in ('ring-fixed','sun-fixed','carrier-fixed'):
        raise CoreError('anatomy_invalid','Invalid tooth counts or held member')
    ring=sun+2*planet
    if (sun+ring)%3 or (sun+planet)*math.sin(math.pi/3)<=planet+2:raise CoreError('anatomy_invalid','Three-planet assembly conditions failed')
    return mechanism,{'sun_teeth':sun,'planet_teeth':planet,'mode':mode}

def render(root,value):
    StopGate(root).require_running()
    mechanism,config=validate_request(value)
    skills=Skills(root)
    try:
        if not next(x for x in skills.list() if x['id']=='gears')['enabled']:raise CoreError('skill_unavailable','Anatomy is disabled')
    finally:skills.close()
    source=json.loads((ROOT/'external/anatomy/source.json').read_text(encoding='utf-8'))
    for name,sha in source['files'].items():
        if hashlib.sha256((ROOT/'external/anatomy'/name).read_bytes()).hexdigest()!=sha:raise CoreError('anatomy_changed','Review modified upstream files before use')
    node=shutil.which('node')
    if not node:raise CoreError('anatomy_dependency','Node.js is required')
    if not LOCK.acquire(blocking=False):raise CoreError('conflict','Renderer busy')
    try:
        result=subprocess.run([node,str(ROOT/'modules/skills/anatomy/build.mjs'),mechanism],input=json.dumps(config).encode(),capture_output=True,timeout=15,env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP'}},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        StopGate(root).require_running()
        if result.returncode or not 10000<len(result.stdout)<1000000:raise CoreError('anatomy_build','Fixed renderer did not deliver bounded HTML')
        folder=child(root,'artifacts/anatomy');folder.mkdir(parents=True,exist_ok=True);ident=uuid.uuid4().hex
        output=child(root,'artifacts/anatomy/'+ident+'.html');output.write_bytes(result.stdout)
        receipt={'id':ident,'skill':'gears','mechanism':mechanism,'configuration':config,'adapter_version':'4.0.0','source':source,'sha256':hashlib.sha256(result.stdout).hexdigest(),'bytes':len(result.stdout),'url':'/api/anatomy/artifacts/'+ident,'path':str(output),'model_calls':0,'renderer_sha256':{p:hashlib.sha256((ROOT/'modules/skills/anatomy'/p).read_bytes()).hexdigest() for p in ('build.mjs','page.html','planetary-model.mjs','planetary-view.js','planetary.html','studio.html','studio-view.js','studio-model.mjs','scene-schema.json','studio-presets.json','structure3d.mjs','structure-scenes.mjs')},'limits':'Bounded declarative teaching scenes; no CAD, combustion/CFD/FEA, circuit transient or hydraulic load solver. Field particles are qualitative.'}
        receipt['host_validation_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('host/anatomy.py','host/anatomy_scene.py','host/anatomy_composer.py')}
        output.with_suffix('.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');return receipt
    except subprocess.TimeoutExpired:raise CoreError('anatomy_timeout','Renderer exceeded 15 seconds') from None
    finally:LOCK.release()
def artifact(root,ident):
    if not re.fullmatch('[a-f0-9]{32}',ident):raise CoreError('not_found','Unknown artifact')
    p=child(root,'artifacts/anatomy/'+ident+'.html');receipt=json.loads(p.with_suffix('.json').read_text(encoding='utf-8'));raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=receipt['sha256']:raise CoreError('anatomy_changed','Artifact changed')
    return raw
