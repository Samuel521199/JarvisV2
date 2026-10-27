"""Admit self-contained GLB only; never fetch external URIs."""
import json,struct
from sdk.protocol import CoreError
MAX_GLB_BYTES=96*1024**2
MAX_GLB_BASE64_BYTES=4*((MAX_GLB_BYTES+2)//3)
MAX_GLB_UPLOAD_BYTES=MAX_GLB_BASE64_BYTES+8192
MAX_GLB_MESHES=256
MAX_GLB_NODES=512
def decode_upload(raw,*,max_bytes=29000000):
    """Dedicated file-transfer envelope; ordinary core JSON limit stays intact."""
    from sdk.protocol import canonical
    if not isinstance(raw,bytes) or len(raw)>max_bytes:raise CoreError('studio3d_asset_invalid','Upload envelope exceeds limit')
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise CoreError('invalid_json','Duplicate upload key')
            d[k]=v
        return d
    try:
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
        canonical(value).encode('utf-8');return value
    except (ValueError,UnicodeError,RecursionError):raise CoreError('invalid_json','Invalid upload JSON') from None
def validate_glb(raw,*,max_bytes=MAX_GLB_BYTES):
    def bad():raise CoreError('studio3d_asset_invalid','Use a bounded self-contained GLB 2.0 file')
    if not isinstance(raw,bytes) or not 28<=len(raw)<=max_bytes:bad()
    magic,version,total=struct.unpack_from('<III',raw)
    if magic!=0x46546c67 or version!=2 or total!=len(raw):bad()
    size,kind=struct.unpack_from('<II',raw,12)
    if kind!=0x4e4f534a or size>2*1024**2 or size%4 or 20+size>len(raw):bad()
    try:value=decode_upload(raw[20:20+size].rstrip(b' \x00'))
    except (ValueError,UnicodeError):bad()
    if not isinstance(value,dict) or not isinstance(value.get('asset'),dict) or value['asset'].get('version')!='2.0':bad()
    def scan(x):
        if isinstance(x,dict):
            if 'uri' in x:bad()
            for v in x.values():scan(v)
        elif isinstance(x,list):
            for v in x:scan(v)
    try:scan(value)
    except RecursionError:bad()
    if not isinstance(value.get('nodes',[]),list) or len(value.get('nodes',[]))>MAX_GLB_NODES or not isinstance(value.get('meshes'),list) or not 1<=len(value['meshes'])<=MAX_GLB_MESHES:bad()
    for key,limit in [('accessors',2048),('bufferViews',4096),('materials',128),('images',64)]:
        if not isinstance(value.get(key,[]),list) or len(value.get(key,[]))>limit:bad()
    pos=20+size;binary=0
    while pos<len(raw):
        if pos+8>len(raw):bad()
        size,kind=struct.unpack_from('<II',raw,pos);pos+=8
        if size%4 or pos+size>len(raw) or kind!=0x004e4942:bad()
        binary+=1;pos+=size
    if binary!=1 or not isinstance(value.get('buffers'),list) or len(value['buffers'])!=1:bad()
    return {'bytes':len(raw),'mesh_definitions':len(value['meshes']),'nodes':len(value.get('nodes',[])),'external_uris':False}


def decode_job(raw):
    """Larger bounded geometry data; core/model message budgets stay unchanged."""
    if not isinstance(raw,bytes) or not 1<=len(raw)<=2*1024**2:raise CoreError('studio3d_invalid','Scene request exceeds 2 MiB')
    value=decode_upload(raw)
    if not isinstance(value,dict):raise CoreError('studio3d_invalid','Expected scene request object')
    return value
