"""Local reference-image intake; images are guidance, not automatic reconstruction."""
import base64,hashlib,json,re,struct,uuid
from control.paths import child
from sdk.protocol import CoreError,canonical

def upload(root,body):
    from host.studio3d import enabled
    enabled(root)
    return register(root,body)


def register(root,body):
    """Shared local intake; callers enforce their own skill and stop policy."""
    if not isinstance(body,dict) or set(body)!={'name','source','license','data'} or any(not isinstance(v,str) for v in body.values()):raise CoreError('studio3d_invalid','Expected PNG reference and provenance')
    if not all(1<=len(body[k])<=n for k,n in [('name',100),('source',500),('license',200)]) or len(body['data'])>16*1024**2:raise CoreError('studio3d_invalid','Reference budget exceeded')
    try:raw=base64.b64decode(body['data'],validate=True)
    except ValueError:raise CoreError('studio3d_invalid','Invalid reference encoding') from None
    if not 33<=len(raw)<=12*1024**2 or raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR':raise CoreError('studio3d_invalid','Use PNG reference')
    width,height=struct.unpack_from('>II',raw,16)
    if not 1<=width<=8192 or not 1<=height<=8192 or width*height>16000000:raise CoreError('studio3d_invalid','Reference pixel budget exceeded')
    ident=uuid.uuid4().hex;folder=child(root,'artifacts/studio3d-references');folder.mkdir(parents=True,exist_ok=True)
    row={'id':ident,'name':body['name'],'source':body['source'],'license':body['license'],'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'resolution':[width,height],'provenance_verified':False,'mode':'Local visual reference; no automatic cloud upload or image-to-mesh. Explicit image editing or vision_reference sends PNG to the selected Google route. Not photogrammetry.'}
    (folder/(ident+'.png')).write_bytes(raw);(folder/(ident+'.json')).write_text(canonical(row),encoding='utf-8');return row

def record(root,ident):
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise CoreError('studio3d_invalid','Unknown reference')
    folder=child(root,'artifacts/studio3d-references');row=json.loads((folder/(ident+'.json')).read_text(encoding='utf-8'));raw=(folder/(ident+'.png')).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise CoreError('studio3d_changed','Reference changed')
    return row,raw
