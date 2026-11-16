"""Append a verified immutable read-only recovery package to the existing final increment."""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from modules.release_recovery.application import Applications

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    receipt=json.loads((OUT/'recovery-increment.json').read_text());assert receipt['passed']
    dest=Path(receipt['destination']);root=Path('E:/Jarvis/runtime/user-data')
    assert all(sha(dest/n)==v['sha256'] for n,v in receipt['files'].items())
    ident=json.loads((OUT/'qualified.json').read_text())['fallback_build'];package=Path(Applications(root).approved(ident,fresh=False)['path'])
    for p in package.rglob('*'):
        if not p.is_file():continue
        n='user-data/'+p.relative_to(root).as_posix();target=dest/n;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert sha(target)==sha(p)
        else:shutil.copy2(p,target)
        receipt['files'][n]={'bytes':target.stat().st_size,'sha256':sha(target)}
    receipt['explicit_readonly_fallback_build']=ident
    raw=json.dumps(receipt,indent=2)+'\n';(dest/'verification.json').write_text(raw,encoding='utf-8');(OUT/'recovery-increment.json').write_text(raw,encoding='utf-8')
    print(json.dumps({'passed':True,'files':len(receipt['files']),'readonly_fallback':ident}))

if __name__=='__main__':main()
