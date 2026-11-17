"""Persistent pseudonymous identifier for this installation's local owner."""
import json,os,uuid
from control.paths import child
from sdk.protocol import CoreError


def owner_id(root):
    path=child(root,'config/eachlabs-owner.json')
    if not path.exists():
        value={'schema':1,'owner_id':'jarvis-owner-'+uuid.uuid4().hex,'binding':'local installation owner'}
        try:
            with path.open('x',encoding='utf-8') as stream:
                json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        except FileExistsError:pass
    value=json.loads(path.read_text(encoding='utf-8'))
    ident=value.get('owner_id','')
    if value.get('schema')!=1 or not isinstance(ident,str) or not ident.startswith('jarvis-owner-') or len(ident)!=45:
        raise CoreError('eachlabs_owner','Invalid owner binding; never substitute a request-specific ID')
    return ident
