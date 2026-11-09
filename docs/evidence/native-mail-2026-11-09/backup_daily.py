"""Local stopped-host backup. Never exports private values to console or Git."""
from pathlib import Path
import hashlib,json,shutil,sqlite3,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from control.recovery.gate import RunLock
from control.paths import reject_links


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def table_hashes(path):
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        out={}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            quoted='"'+name.replace('"','""')+'"';rows=[]
            for row in db.execute('SELECT * FROM '+quoted):
                values=[{'blob':value.hex()} if isinstance(value,bytes) else value for value in row]
                rows.append(json.dumps(values,ensure_ascii=False,separators=(',',':')))
            out[name]={'rows':len(rows),'sha256':hashlib.sha256('\n'.join(sorted(rows)).encode()).hexdigest()}
        return out
    finally:db.close()


def _backup(root,destination):
    reject_links(root);reject_links(destination)
    destination.mkdir(parents=True,exist_ok=False);files={};databases={}
    for folder in ('config','private','sessions','state'):
        base=root/folder
        if not base.exists():continue
        for source in sorted(base.rglob('*')):
            if not source.is_file():continue
            name=source.relative_to(root).as_posix()
            if source.suffix in {'.lock'} or name.endswith(('-wal','-shm')):continue
            reject_links(source)
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
            if source.suffix=='.sqlite3':
                original=sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True);copy=sqlite3.connect(target)
                try:
                    original.backup(copy)
                    if copy.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity failure')
                finally:copy.close();original.close()
                databases[name]=table_hashes(target)
            else:shutil.copy2(source,target)
            files[name]={'bytes':target.stat().st_size,'sha256':digest(target)}
    assets={}
    for folder in ('artifacts','exports'):
        base=root/folder
        if base.exists():
            for source in base.rglob('*'):
                if source.is_file():
                    reject_links(source);stat=source.stat()
                    assets[source.relative_to(root).as_posix()]=[stat.st_size,stat.st_mtime_ns]
    report={'schema':1,'files':files,'databases':databases,'assets_metadata':assets,'root':str(root),'backup':str(destination),
            'scope':'config/private/sessions/state; SQLite online-backup API while managed host stopped; no assets copied'}
    (destination/'inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={'files':len(files),'bytes':sum(x['bytes'] for x in files.values()),'databases':len(databases),
             'tables':sum(len(x) for x in databases.values()),'asset_metadata_files':len(assets),
             'backup':str(destination),'integrity':'all ok'}
    print(json.dumps(summary,ensure_ascii=False));return summary


def backup(root,destination):
    with RunLock(root,'application-release'),RunLock(root,'workbench-host'):
        return _backup(root,destination)


if __name__=='__main__':backup(*map(lambda value:Path(value).resolve(),sys.argv[1:]))
