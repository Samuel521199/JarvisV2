"""Content-addressed model storage and a versioned, searchable asset catalogue."""
import hashlib,json,os,re,shutil,sqlite3,tempfile,uuid,math
from datetime import datetime,timezone
from pathlib import Path
from sdk.protocol import CoreError

SLUG=re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
EXT={'.glb','.vrm','.blend','.fbx','.obj','.png','.jpg','.jpeg','.zip','.json','.txt'}
CATEGORIES=[{'id':'wwii','name':'二战','description':'车辆、火炮与可复用部件'},{'id':'characters','name':'人物','description':'人物、角色和附件'},{'id':'general','name':'其他模型','description':'道具、场景与其他三维资产'}]

def slug(value):
 if not isinstance(value,str) or not SLUG.fullmatch(value):raise CoreError('library_invalid','Invalid asset or variant identifier')
 return value
def stamp():return datetime.now(timezone.utc).isoformat()
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()

class Library:
 def __init__(self,data_root):
  location=Path(data_root).resolve()/'model-library';settings=location/'location.json'
  self.root=Path(json.loads(settings.read_text(encoding='utf-8'))['repository']).resolve() if settings.exists() else location
  self.root.mkdir(parents=True,exist_ok=True);self.objects=self.root/'objects';self.objects.mkdir(exist_ok=True)
  self.db=sqlite3.connect(self.root/'catalog.sqlite3',timeout=30);self.db.row_factory=sqlite3.Row
  self.db.executescript('''PRAGMA journal_mode=WAL;
   CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,body TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,asset_id TEXT NOT NULL,name TEXT NOT NULL,sha256 TEXT NOT NULL,ext TEXT NOT NULL,bytes INTEGER NOT NULL,role TEXT NOT NULL,meta TEXT NOT NULL,UNIQUE(asset_id,sha256,role));
   CREATE TABLE IF NOT EXISTS variants(asset_id TEXT NOT NULL,id TEXT NOT NULL,file_id TEXT NOT NULL,label TEXT NOT NULL,role TEXT NOT NULL,PRIMARY KEY(asset_id,id));
   CREATE TABLE IF NOT EXISTS cases(asset_id TEXT NOT NULL,id TEXT NOT NULL,body TEXT NOT NULL,PRIMARY KEY(asset_id,id));
   CREATE TABLE IF NOT EXISTS annotations(asset_id TEXT NOT NULL,id TEXT PRIMARY KEY,body TEXT NOT NULL);''')
 def close(self):self.db.close()
 def __enter__(self):return self
 def __exit__(self,*exc):self.close()
 def put_asset(self,value):
  value=dict(value);ident=slug(value['id']);name=value.get('name')
  if not isinstance(name,str) or not 1<=len(name)<=120 or value.get('category') not in {c['id'] for c in CATEGORIES} or value.get('kind') not in {'model','part','character'}:raise CoreError('library_invalid','Name, category and kind required')
  tags=value.get('tags',[])
  if not isinstance(tags,list) or len(tags)>30 or any(not isinstance(t,str) or len(t)>60 for t in tags):raise CoreError('library_invalid','Invalid tags')
  if not isinstance(value.get('description',''),str) or len(value.get('description',''))>6000:raise CoreError('library_invalid','Description exceeds6000 characters')
  old=self.db.execute('SELECT created FROM assets WHERE id=?',(ident,)).fetchone();when=stamp()
  self.db.execute('INSERT INTO assets VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated',(ident,json.dumps(value,ensure_ascii=False),old['created'] if old else when,when));self.db.commit();return ident
 def add_file(self,asset_id,path,role,expected_sha=None,source_label=None):
  self.asset(asset_id);path=Path(path).resolve(strict=True);ext=path.suffix.lower()
  if ext not in EXT or not path.is_file() or not 0<path.stat().st_size<=1024**3:raise CoreError('library_invalid','Unsupported file or file exceeds 1GiB')
  with path.open('rb') as src:
   handle,tmp=tempfile.mkstemp(prefix='ingest-',dir=self.root);h=hashlib.sha256();size=0
   try:
    with os.fdopen(handle,'wb') as out:
     for block in iter(lambda:src.read(4*1024*1024),b''):h.update(block);out.write(block);size+=len(block)
    sha=h.hexdigest()
    if expected_sha and sha!=expected_sha:raise CoreError('library_changed','Source digest does not match its provenance')
    target=self.objects/sha[:2]/(sha+ext);target.parent.mkdir(exist_ok=True)
    if target.exists():
     if digest(target)!=sha:raise CoreError('library_changed','Stored object is corrupt')
    else:os.replace(tmp,target)
   finally:
    if Path(tmp).exists():Path(tmp).unlink()
  meta={'source_name':source_label or path.name,'ingested_at':stamp()}
  if ext in {'.glb','.vrm'}:
   if size<=128*1024**2:
    from modules.skills.studio3d.inspection import inspect
    info=inspect(target.read_bytes());info['preview_supported']=info['triangles']<=1500000 and info['texture_memory_estimate_bytes']<=768*1024**2
   else:
    import struct
    with target.open('rb') as stream:header=stream.read(12)
    if len(header)!=12 or struct.unpack('<III',header)!=(0x46546c67,2,size):raise CoreError('library_invalid','Large original is not a GLB2 container')
    info={'triangles':None,'bytes':size,'sha256':sha,'preview_supported':False,'scope':'Original download only; separate bounded display preview required. Viewer128MiB/1.5M triangle limits unchanged.'}
   meta['inventory']=info
  existing=self.db.execute('SELECT id FROM files WHERE asset_id=? AND sha256=? AND role=?',(asset_id,sha,role)).fetchone()
  if existing:return existing['id']
  ident=uuid.uuid4().hex;self.db.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?)',(ident,asset_id,source_label or path.name,sha,ext,size,role,json.dumps(meta,ensure_ascii=False)));self.db.commit();return ident
 def add_variant(self,asset_id,ident,file_id,label,role):
  slug(ident);f=self.file(asset_id,file_id)
  if f['ext'] not in {'.glb','.vrm'}:raise CoreError('library_invalid','Only embedded GLB/VRM can be previewed')
  old=self.db.execute('SELECT file_id FROM variants WHERE asset_id=? AND id=?',(asset_id,ident)).fetchone()
  if old and old['file_id']!=file_id:raise CoreError('library_conflict','Preserve the previous version under its existing identifier')
  self.db.execute('INSERT OR REPLACE INTO variants VALUES(?,?,?,?,?)',(asset_id,ident,file_id,label,role));self.db.commit()
 def add_case(self,asset_id,value):
  self.asset(asset_id);value=dict(value);ident=slug(value['id']);value['scope']=value.get('scope','asset-local candidate');value['promoted']=False
  if not value.get('prerequisites') or not value.get('counterexamples'):raise CoreError('library_invalid','Reference method needs prerequisites and counterexamples')
  self.db.execute('INSERT OR REPLACE INTO cases VALUES(?,?,?)',(asset_id,ident,json.dumps(value,ensure_ascii=False)));self.db.commit()
 def file(self,asset_id,ident):
  slug(asset_id)
  if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise CoreError('library_missing','File not registered')
  row=self.db.execute('SELECT * FROM files WHERE asset_id=? AND id=?',(asset_id,ident)).fetchone()
  if not row:raise CoreError('library_missing','File not registered for this asset')
  f=dict(row);f['meta']=json.loads(f['meta']);f['url']=f'/api/model-library/files/{asset_id}/{ident}';return f
 def object_path(self,f):
  path=(self.objects/f['sha256'][:2]/(f['sha256']+f['ext'])).resolve()
  if not path.is_relative_to(self.objects.resolve()) or not path.is_file() or path.stat().st_size!=f['bytes']:raise CoreError('library_missing','Stored object missing or changed')
  return path
 def asset(self,ident):
  slug(ident);r=self.db.execute('SELECT * FROM assets WHERE id=?',(ident,)).fetchone()
  if not r:raise CoreError('library_missing','Asset not registered')
  body=json.loads(r['body']);body.update(created_at=r['created'],updated_at=r['updated']);return body
 def detail(self,ident):
  body=self.asset(ident);body['files']=[self.file(ident,r['id']) for r in self.db.execute('SELECT id FROM files WHERE asset_id=? ORDER BY rowid',(ident,))]
  byid={f['id']:f for f in body['files']};body['variants']=[]
  for r in self.db.execute('SELECT * FROM variants WHERE asset_id=? ORDER BY rowid',(ident,)):
   v=dict(r);v.update(file=byid[v['file_id']],viewer=f'/model-library/view/{ident}/{v["id"]}');body['variants'].append(v)
  body['methods']=[json.loads(r['body']) for r in self.db.execute('SELECT body FROM cases WHERE asset_id=?',(ident,))]
  body['annotations']=[json.loads(r['body']) for r in self.db.execute('SELECT body FROM annotations WHERE asset_id=?',(ident,)) if not json.loads(r['body']).get('archived')]
  cover=next((f for f in body['files'] if f['role']=='cover'),None);body['cover']=cover['url'] if cover else None
  return body
 def metadata(self,ident,tags,description):
  if not isinstance(description,str) or len(description)>6000:raise CoreError('library_invalid','Description exceeds6000 characters')
  body=self.asset(ident);body.update(tags=tags,description=description);self.put_asset(body);return self.detail(ident)
 def annotate(self,ident,value):
  self.asset(ident)
  if not isinstance(value,dict) or set(value)-{'id','title','text','variant_id','sha256','point','point_space','object_name','archived','status'}:raise CoreError('library_invalid','Unknown annotation fields')
  title=value.get('title','');text=value.get('text','');variant=value.get('variant_id');point=value.get('point')
  if variant is not None and not isinstance(variant,str):raise CoreError('library_invalid','Invalid version identifier')
  if not isinstance(title,str) or not 1<=len(title)<=120 or not isinstance(text,str) or len(text)>6000:raise CoreError('library_invalid','Annotation title/text invalid')
  if point is not None and (not isinstance(point,list) or len(point)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>1e6 for x in point)):raise CoreError('library_invalid','Invalid 3D annotation point')
  if variant:
   row=self.db.execute('SELECT file_id FROM variants WHERE asset_id=? AND id=?',(ident,slug(variant))).fetchone()
   if not row or self.file(ident,row['file_id'])['sha256']!=value.get('sha256'):raise CoreError('library_changed','Annotation must match the exact model version')
  elif point is not None:raise CoreError('library_invalid','Spatial annotations require a specific model version')
  if not isinstance(value.get('object_name',''),str) or len(value.get('object_name',''))>180 or value.get('point_space','object') not in {'object','world'} or type(value.get('archived',False)) is not bool:raise CoreError('library_invalid','Invalid annotation controls')
  if value.get('status','open') not in {'open','resolved'}:raise CoreError('library_invalid','Invalid annotation status')
  note_id=value.get('id') or uuid.uuid4().hex
  if not isinstance(note_id,str) or not re.fullmatch('[a-f0-9]{32}',note_id):raise CoreError('library_invalid','Invalid annotation identifier')
  old=self.db.execute('SELECT asset_id,body FROM annotations WHERE id=?',(note_id,)).fetchone()
  if old and old['asset_id']!=ident:raise CoreError('library_missing','Annotation belongs to another asset')
  body={**value,'id':note_id,'asset_id':ident,'created_at':json.loads(old['body'])['created_at'] if old else stamp(),'updated_at':stamp()}
  self.db.execute('INSERT OR REPLACE INTO annotations VALUES(?,?,?)',(ident,note_id,json.dumps(body,ensure_ascii=False)));self.db.commit();return body
 def catalogue(self,query='',category='',kind=''):
  if not isinstance(query,str) or len(query)>200 or category and category not in {c['id'] for c in CATEGORIES} or kind and kind not in {'model','part','character'}:raise CoreError('library_invalid','Invalid search filters')
  terms=query.casefold().split();items=[]
  for r in self.db.execute('SELECT id FROM assets ORDER BY created,id LIMIT 2000'):
   a=self.detail(r['id']);text=' '.join([a['name'],a.get('description',''),*a.get('tags',[])]).casefold()
   if category and a['category']!=category or kind and a['kind']!=kind or any(t not in text for t in terms):continue
   items.append(a)
  return {'schema':'jarvis.model-library.v1','categories':CATEGORIES,'assets':items,'total':self.db.execute('SELECT COUNT(*) FROM assets').fetchone()[0],'storage':'SHA-256 content-addressed originals; variants and methods stay associated with their asset'}
