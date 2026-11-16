"""Explicitly install reviewed first-party English City without installing dependencies."""
import argparse,hashlib,json,re,sys
from pathlib import Path
from control.atomic import write_json
from control.recovery.gate import RunLock
from control.paths import reject_links,data_root
from sdk.protocol import canonical

def install(source,destination,root):
    source=Path(source).resolve();destination=Path(destination).resolve();root=data_root(root)
    project=Path(__file__).resolve().parents[1]
    if source.is_relative_to(project) or destination.is_relative_to(project):raise ValueError('Independent software source and releases must stay outside the Jarvis project')
    reject_links(source);reject_links(destination)
    raw=(source/'engine.py').read_bytes()
    version=(source/'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}',version):raise ValueError('Invalid independent software version')
    manifest={'schema':1,'id':'english-city','version':version,'entry':'engine.py','files':{'engine.py':hashlib.sha256(raw).hexdigest()}}
    ident=hashlib.sha256(canonical(manifest).encode()).hexdigest();folder=destination/'releases'/ident
    folder.mkdir(parents=True,exist_ok=True)
    for name,value in [('engine.py',raw),('software.json',canonical(manifest).encode())]:
        path=folder/name
        if path.exists():assert path.read_bytes()==value,'Never overwrite a changed release'
        else:path.write_bytes(value)
    with RunLock(root,'software-config'):
        path=root/'config/software.json';config=json.loads(path.read_text()) if path.exists() else {'schema':1,'software':{}}
        prior=config['software'].get('english-city');item={'enabled':True,'release':str(folder),'build':ident,'revision':(prior['revision']+1 if prior else 1)}
        if prior and all(prior.get(k)==v for k,v in item.items() if k!='revision'):item=prior
        config['software']['english-city']=item;write_json(path,config)
    return {'id':'english-city','version':version,**item}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True);a=p.parse_args()
    print(json.dumps(install(a.source,a.destination,a.data_root)))
