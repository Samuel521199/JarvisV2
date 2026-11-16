"""Owner-local software enablement. It is not an arbitrary-code trust sandbox."""
from control.atomic import write_json
from control.paths import child
from control.recovery.gate import RunLock
from sdk.protocol import CoreError,read_json

def read(root):
    path=child(root,'config/software.json')
    value=read_json(path) if path.exists() else {'schema':1,'software':{}}
    if not isinstance(value,dict) or set(value)!={'schema','software'} or type(value['schema']) is not int or value['schema']!=1 or not isinstance(value['software'],dict):raise CoreError('software_integrity','Invalid software registry')
    return value

def configure(root,ident,enabled,revision):
    if ident!='english-city' or type(enabled) is not bool or type(revision) is not int:raise CoreError('software_invalid','Invalid software policy request')
    with RunLock(root,'software-config'):
        value=read(root);prior=value['software'].get(ident)
        if not prior or prior['revision']!=revision:raise CoreError('conflict','Software policy changed')
        value['software'][ident]={**prior,'enabled':enabled,'revision':revision+1}
        write_json(child(root,'config/software.json'),value)
    return value['software'][ident]
