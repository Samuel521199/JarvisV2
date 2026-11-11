"""Model routes run after the normal owner, origin, nonce and local login gates."""
import json,mimetypes,re
from pathlib import Path
from urllib.parse import quote
from host import model_library as service
from modules.skills.model_library.store import Library
from sdk.protocol import CoreError

def get(h,path):
 if path=='/model-library':
  h.reply(200,(Path(__file__).parent/'model-library.html').read_bytes(),'text/html');return True
 if path.startswith('/model-library/compare/'):
  pieces=path.split('/')
  if len(pieces)!=4:return False
  try:
   with Library(h.server.data_root) as lib:lib.asset(pieces[3])
  except CoreError as exc:h.json({'error':exc.code},404);return True
  h.reply(200,(Path(__file__).parent/'model-library-compare.html').read_bytes(),'text/html');return True
 if path.startswith('/model-library/view/'):
  pieces=path.split('/')
  if len(pieces)!=5:return False
  try:service.viewer_state(h.server.data_root,pieces[3],pieces[4])
  except (CoreError,ValueError,OSError) as exc:
   h.json({'error':exc.code if isinstance(exc,CoreError) else 'library_unavailable'},404 if isinstance(exc,CoreError) and exc.code=='library_missing' else 400);return True
  from host.studio3d_viewer import IMPORT_MAP
  raw=(Path(__file__).parent/'studio3d-viewer.html').read_text(encoding='utf-8').replace('@@IMPORT_MAP@@',IMPORT_MAP)
  h.reply(200,raw.encode(),'text/html',viewer='library');return True
 if not path.startswith('/api/model-library'):return False
 try:
  parts=path.split('/')
  if path=='/api/model-library':h.json(service.summary(h.server.data_root))
  elif len(parts)==5 and parts[3]=='assets':
   with Library(h.server.data_root) as lib:h.json(lib.detail(parts[4]))
  elif len(parts)==6 and parts[3] in {'view','inspect'}:h.json((service.viewer_state if parts[3]=='view' else service.inventory)(h.server.data_root,parts[4],parts[5]))
  elif len(parts)==6 and parts[3]=='files':
   with Library(h.server.data_root) as lib:f=lib.file(parts[4],parts[5]);source=lib.object_path(f)
   h.send_response(200);h.send_header('Content-Type',{'.glb':'model/gltf-binary','.vrm':'model/gltf-binary','.blend':'application/octet-stream'}.get(f['ext'],mimetypes.guess_type(f['name'])[0] or 'application/octet-stream'));h.send_header('Content-Length',str(f['bytes']));h.send_header('X-Content-Type-Options','nosniff');h.send_header('Cache-Control','private, max-age=3600');h.send_header('ETag','"'+f['sha256']+'"');h.send_header('Content-Disposition',"inline; filename*=UTF-8''"+quote(f['name']));h.end_headers()
   with source.open('rb') as stream:
    for block in iter(lambda:stream.read(1024*1024),b''):h.wfile.write(block)
  else:h.json({'error':'library_missing'},404)
 except (CoreError,ValueError,OSError) as exc:h.json({'error':exc.code if isinstance(exc,CoreError) else 'library_unavailable'},404 if isinstance(exc,CoreError) and exc.code=='library_missing' else 400)
 return True
def post(h,path,value):
 if path=='/api/model-library/query':h.json(service.query(h.server.data_root,value));return True
 if path=='/api/model-library/import':h.json(service.upload(h.server.data_root,value));return True
 if path=='/api/model-library/metadata':
  if not isinstance(value,dict) or set(value)!={'asset_id','tags','description'}:raise CoreError('library_invalid','Explicit metadata fields required')
  with Library(h.server.data_root) as lib:h.json(lib.metadata(value['asset_id'],value['tags'],value['description']))
  return True
 if path=='/api/model-library/annotations':
  if not isinstance(value,dict) or set(value)!={'asset_id','annotation'}:raise CoreError('library_invalid','Explicit annotation fields required')
  with Library(h.server.data_root) as lib:h.json(lib.annotate(value['asset_id'],value['annotation']))
  return True
 return False
