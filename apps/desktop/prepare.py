"""Register a locally compiled, explicitly reviewed first-party shell binary."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from control.atomic import write_json
from control.paths import data_root,reject_links


def prepare(root,binary):
    root=data_root(root);binary=Path(binary).resolve();reject_links(binary)
    if binary.suffix.lower()!='.exe' or not 100000<binary.stat().st_size<96*1024**2:
        raise ValueError('Expected a bounded local Windows companion executable')
    digest=hashlib.sha256(binary.read_bytes()).hexdigest();folder=root/'optional/desktop-presence';folder.mkdir(parents=True,exist_ok=True)
    target=folder/(digest+'.exe')
    if not target.exists():shutil.copy2(binary,target)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('Copy changed')
    record={'schema':1,'protocol':1,'file':target.name,'sha256':digest,'reviewed_local_source':True,
        'source_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [ROOT/'apps/desktop/Cargo.toml',ROOT/'apps/desktop/Cargo.lock',ROOT/'apps/desktop/src/main.rs']}}
    write_json(folder/'prepared.json',record);return {'prepared':True,'bytes':target.stat().st_size,'sha256':digest}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--reviewed-source',action='store_true');a=p.parse_args()
    if not a.reviewed_source:p.error('Review source and dependency lock before preparing this optional binary')
    print(json.dumps(prepare(a.data_root,a.binary)))
