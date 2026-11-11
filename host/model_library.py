"""The workbench, CLI and reference retrieval share one model library service."""
import base64,json,re,tempfile
from pathlib import Path
from modules.skills.model_library.store import Library,slug,EXT
from sdk.protocol import CoreError

def decode_import(raw):
 from sdk.protocol import _object,canonical
 if not isinstance(raw,bytes) or len(raw)>90000000:raise CoreError('library_invalid','Import exceeds64MiB model allowance')
 try:
  value=json.loads(raw.decode('utf-8'),object_pairs_hook=_object,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')));canonical(value).encode('utf-8');return value
 except (UnicodeError,ValueError,RecursionError) as exc:raise CoreError('library_invalid','Invalid import JSON') from exc

def summary(root):
 with Library(root) as lib:return lib.catalogue()
def query(root,value):
 if not isinstance(value,dict) or set(value)-{'query','category','kind'}:raise CoreError('library_invalid','Unknown query controls')
 with Library(root) as lib:return lib.catalogue(value.get('query',''),value.get('category',''),value.get('kind',''))
def upload(root,value):
 allowed={'name','category','kind','tags','description','filename','data','asset_id','label'}
 if not isinstance(value,dict) or set(value)-allowed:raise CoreError('library_invalid','Invalid import fields')
 filename=value.get('filename','')
 if not isinstance(filename,str):raise CoreError('library_invalid','Unsupported model filename')
 suffix=Path(filename).suffix.lower()
 if not isinstance(filename,str) or suffix not in {'.glb','.vrm','.blend','.fbx','.obj'} or len(filename)>180 or '/' in filename or '\\' in filename:raise CoreError('library_invalid','Unsupported model filename')
 data=value.get('data','')
 if not isinstance(data,str) or len(data)>90000000:raise CoreError('library_invalid','Browser imports are limited to64MiB')
 try:raw=base64.b64decode(data,validate=True)
 except (ValueError,TypeError):raise CoreError('library_invalid','Invalid file encoding')
 if not 0<len(raw)<=64*1024**2:raise CoreError('library_invalid','Browser imports are limited to64MiB')
 # Validate embedded models before creating a catalogue entry or storing bytes.
 if suffix in {'.glb','.vrm'}:
  from modules.skills.studio3d.inspection import inspect
  inspect(raw)
 import uuid
 with Library(root) as lib:
  ident=value.get('asset_id') or 'model-'+uuid.uuid4().hex[:16]
  if value.get('asset_id'):lib.asset(ident)
  else:lib.put_asset({'id':ident,'name':value.get('name',''),'category':value.get('category','general'),'kind':value.get('kind','model'),'tags':value.get('tags',[]),'description':value.get('description',''),'status':'draft','rights':'用户导入；授权范围待用户登记','default_variant':'original'})
  folder=lib.root/'imports';folder.mkdir(exist_ok=True);path=folder/(uuid.uuid4().hex+suffix);path.write_bytes(raw)
  try:
   file_id=lib.add_file(ident,path,'source',source_label=filename)
   if suffix in {'.glb','.vrm'}:
    version='original' if not lib.detail(ident)['variants'] else 'version-'+uuid.uuid4().hex[:10]
    lib.add_variant(ident,version,file_id,value.get('label','原始模型'),'original')
  finally:path.unlink(missing_ok=True)
  return lib.detail(ident)

def viewer_state(root,asset_id,variant_id):
 with Library(root) as lib:
  a=lib.detail(asset_id);v=next((v for v in a['variants'] if v['id']==variant_id),None)
  if not v:raise CoreError('library_missing','Model version not registered')
  files={'model.glb':{'url':v['file']['url'],'sha256':v['file']['sha256']}}
  cover=next((f for f in a['files'] if f['role']=='cover'),None)
  if cover:files['preview.png']={'url':cover['url'],'sha256':cover['sha256']}
  editable=next((f for f in a['files'] if f['ext']=='.blend' and f['role']=='editable'),None)
  if editable:files['model.blend']={'url':editable['url'],'sha256':editable['sha256']}
  for f in a['files']:
   if f['role'].startswith('view-'):files[f['role']+'.png']={'url':f['url'],'sha256':f['sha256']}
  return {'status':'DELIVERED','receipt':{'id':asset_id,'title':a['name']+' · '+v['label'],'configuration':{'materials':[],'asset':True},'report':{},'files':files,'library_asset':{'id':asset_id,'name':a['name'],'status':a.get('status','draft'),'current_variant':variant_id,'versions':[{'id':x['id'],'label':x['label'],'sha256':x['file']['sha256'],'viewer':x['viewer'],'viewable':x['file']['meta']['inventory'].get('preview_supported',True)} for x in a['variants']]}}}
def inventory(root,asset_id,variant_id):
 with Library(root) as lib:
  a=lib.detail(asset_id);v=next((v for v in a['variants'] if v['id']==variant_id),None)
  if not v:raise CoreError('library_missing','Unknown version')
  return {**v['file']['meta']['inventory'],'id':asset_id,'file':'model.glb','files':viewer_state(root,asset_id,variant_id)['receipt']['files'],'title':a['name']+' · '+v['label'],'asset_pipeline':None}
