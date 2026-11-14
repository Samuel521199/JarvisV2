"""Read-only closeout checks; writes public synthetic verification receipts only."""
from pathlib import Path
import subprocess,json,hashlib,zipfile,sqlite3
ROOT=Path('E:/Jarvis/dev')
OUT=ROOT/'docs/evidence/goal-advice-20261114'
def main():
    commands=[['python','-B','tools/sync_doc_navigation.py','--root','.'],['python','-B','tools/check_docs.py','--root','.'],['python','-B','tools/check_architecture.py','--root','.'],['python','-B','tools/check_repo_size.py','--limit','50'],['python','-I','-B','E:/Jarvis/runtime/JarvisLaunch.py','--check']]
    rows=[]
    for cmd in commands:
        p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        rows.append({'command':cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        assert p.returncode==0,p.stderr
    backup=Path('D:/Jarvis-Recovery/controllers/2026-11-14-r2')
    copy=json.loads((OUT/'production-r1/disaster-copy.json').read_text())
    hashes={name:hashlib.sha256((backup/name).read_bytes()).hexdigest()==row['sha256'] for name,row in copy['files'].items()}
    assert all(hashes.values())
    with zipfile.ZipFile(backup/'controller.zip') as z:
        index=z.read('controller-files.json'); members=json.loads(index)
        assert hashlib.sha256(index).hexdigest()==copy['controller_build']
        assert len(z.namelist())==len(set(z.namelist()))
        assert set(z.namelist())==set(members)|{'controller-files.json'}
        assert all(hashlib.sha256(z.read(name)).hexdigest()==sha for name,sha in members.items())
        counts={'indexed_files':len(members),'zip_members_including_index':len(z.namelist())}
    with zipfile.ZipFile(backup/'runtime-source.zip') as z:
        manifest=json.loads(z.read('application.json'))
        assert len(z.namelist())==len(set(z.namelist()))
        assert set(z.namelist())==set(manifest['files'])|{'application.json'}
        assert all(hashlib.sha256(z.read(name)).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
    p=backup/'user-data/deployment/control.sqlite3'
    c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
    try:integrity=c.execute('pragma integrity_check').fetchone()[0]
    finally:c.close()
    assert integrity=='ok'
    r={'scope':'documentation, architecture, fixed root check and independent disk readback; no model request or application adoption','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'commands':rows,'disaster_hashes':hashes,'controller_archive':counts,'sqlite_integrity':integrity,'earlier_audit_correction':'An ad-hoc audit incorrectly expected total ZIP entries to equal 694 indexed files. Actual ZIP contains an additional controller-files.json index. Original backup hashes were all correct; membership is now checked against the signed index rather than a hardcoded total.','passed':True}
    (OUT/'closeout-checks.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'backup_files':len(hashes),'controller_archive':counts}))
if __name__=='__main__':main()
