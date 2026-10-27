"""Local inspection viewer and immutable, licensed ESM resources."""
import hashlib,json,re
from pathlib import Path
from control.paths import child
from sdk.protocol import CoreError
from modules.skills.studio3d.inspection import inspect

ROOT=Path(__file__).resolve().parents[1]
IMPORT_MAP='{"imports":{"three":"/vendor/three/build/three.module.js"}}'
IMPORT_HASH=__import__('base64').b64encode(hashlib.sha256(IMPORT_MAP.encode()).digest()).decode()
CSP="default-src 'self'; script-src 'self' 'sha256-"+IMPORT_HASH+"'; connect-src 'self' blob:; img-src 'self' blob: data:; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

def vendor(path):
    name=path.removeprefix('/vendor/three/');source=json.loads((ROOT/'external/three/source.json').read_text(encoding='utf-8'))
    if name not in source['files']:raise CoreError('not_found','Unknown viewer resource')
    raw=(ROOT/'external/three'/name).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=source['files'][name]['sha256']:raise CoreError('studio3d_changed','Reviewed viewer dependency changed')
    return raw,'text/javascript' if name.endswith('.js') else 'text/plain'

def page(root,ident):
    from host.studio3d import state
    r=state(root,ident)
    if r['status']!='DELIVERED':raise CoreError('studio3d_missing','No delivered model')
    raw=(ROOT/'apps/workbench/studio3d-viewer.html').read_text(encoding='utf-8')
    return raw.replace('@@IMPORT_MAP@@',IMPORT_MAP).encode()

def inventory(root,ident,name='model.glb'):
    from host.studio3d import file,state
    raw,_=file(root,ident,name);out=inspect(raw);r=state(root,ident)
    out.update(id=ident,title=r['receipt']['title'],file=name,files=r['receipt']['files'],asset_pipeline=r['receipt']['report'].get('asset_pipeline'),source_job=r['receipt'].get('derived_from'))
    formal=r['receipt']['report'].get('gltf_validation',{}).get('files',{}).get(name)
    if formal:
        issues=formal.get('issues',{});out['gltf_validation']=formal;out['checks'].insert(0,{'id':'Khronos-format-validation','status':'fail' if issues.get('numErrors') else 'warn' if issues.get('numWarnings') or issues.get('truncated') else 'pass','message':str(issues.get('numErrors',0))+' errors / '+str(issues.get('numWarnings',0))+' warnings'+(' · issue report truncated' if issues.get('truncated') else '')})
    else:out['checks'].insert(0,{'id':'Khronos-format-validation','status':'unverified','message':'此旧产物尚无官方格式校验回执'})
    if out['asset_pipeline']:out['checks'].extend(out['asset_pipeline'].get('checks',[]))
    if out['asset_pipeline'] and name!='model.glb':
        level=next((x for x in out['asset_pipeline'].get('lods',[]) if x.get('file')==name),{})
        out['checks'].extend({**check,'id':'selected-LOD-'+check['id']} for check in level.get('checks',[]))
    return out
