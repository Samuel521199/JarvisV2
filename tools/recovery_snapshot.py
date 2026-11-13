"""Private local snapshot/restore rehearsal; never start restored work or clear STOP.

Uses explicit roots, OS workload locks, SQLite backup and per-file hashes. This
does not reconstruct deleted projects or protect against failure of its disk.
"""
from contextlib import ExitStack
from datetime import datetime,timezone
import hashlib,json,re,shutil,sqlite3
from pathlib import Path

from control.paths import reject_links
from control.recovery.gate import RunLock

LANES=['application-release','workbench-host','task-runner','executor','dialogue','planning',
       'development','local-models','image-generation','mail']


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def destination_for(base,label,name):
    if not re.fullmatch('[a-z][a-z0-9-]*',label):raise ValueError('Invalid root label')
    part=Path(name)
    if part.is_absolute() or part.drive or '..' in part.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe recovery file path')
    path=base/label/part;reject_links(path)
    if not path.resolve().is_relative_to((base/label).resolve()):raise ValueError('Recovery path escapes root')
    return path


def snapshot(roots,destination,*,managed_root,missing_projects=()):
    roots={label:Path(root).resolve() for label,root in roots.items()};destination=Path(destination).resolve()
    reject_links(destination)
    for label,root in roots.items():
        destination_for(destination,label,'inventory-check')
        reject_links(root)
        if not root.is_dir() or destination==root or destination.is_relative_to(root) or root.is_relative_to(destination):
            raise ValueError('Snapshot roots and destination must be separate existing trees')
    with ExitStack() as locks:
        # A free lease is proven by acquiring it, not by reading an old PID file.
        for lane in LANES:locks.enter_context(RunLock(Path(managed_root),lane))
        destination.mkdir(parents=True,exist_ok=False);files=[];databases=0
        for label,root in roots.items():
            for source in sorted(root.rglob('*')):
                reject_links(source)
                if not source.is_file() or source.suffix=='.lock' or source.name.endswith(('-wal','-shm')):continue
                name=source.relative_to(root).as_posix();target=destination_for(destination,label,name)
                target.parent.mkdir(parents=True,exist_ok=True)
                before=source.stat()
                if source.suffix=='.sqlite3':
                    original=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);copy=sqlite3.connect(target)
                    try:
                        original.backup(copy)
                        if copy.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Snapshot database failed integrity check')
                    finally:copy.close();original.close()
                    databases+=1
                else:
                    shutil.copy2(source,target)
                    if digest(source)!=digest(target):raise ValueError('Source changed during snapshot')
                after=source.stat()
                if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Source changed during snapshot')
                files.append({'root':label,'path':name,'bytes':target.stat().st_size,'sha256':digest(target)})
        manifest={'schema':1,'created_utc':datetime.now(timezone.utc).isoformat(),'roots':{k:str(v) for k,v in roots.items()},
            'files':files,'sqlite_integrity_ok':databases,'missing_projects':list(missing_projects),
            'scope':'Existing explicit trees, except ephemeral lock/WAL/SHM; SQLite backup incorporates WAL. Operational markers remain inert; no automatic execution or credential export.'}
        (destination/'snapshot.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return {'files':len(files),'bytes':sum(row['bytes'] for row in files),'sqlite_integrity_ok':databases,'snapshot':str(destination)}


def restore(snapshot_root,destination):
    snapshot_root=Path(snapshot_root).resolve();destination=Path(destination).resolve();reject_links(snapshot_root);reject_links(destination)
    if destination==snapshot_root or destination.is_relative_to(snapshot_root) or snapshot_root.is_relative_to(destination):
        raise ValueError('Restore must use a separate new tree')
    manifest=json.loads((snapshot_root/'snapshot.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!=1:raise ValueError('Unknown snapshot schema')
    # Validate the entire manifest and hashes before creating any output.
    seen=set()
    for row in manifest['files']:
        key=(row['root'],row['path']);normalized=tuple(part.casefold() for part in key)
        if normalized in seen:raise ValueError('Duplicate recovery path')
        seen.add(normalized);source=destination_for(snapshot_root,*key);target=destination_for(destination,*key)
        if not source.is_file() or source.stat().st_size!=row['bytes'] or digest(source)!=row['sha256']:
            raise ValueError('Snapshot content changed')
    destination.mkdir(parents=True,exist_ok=False);databases=0
    for row in manifest['files']:
        source=destination_for(snapshot_root,row['root'],row['path']);target=destination_for(destination,row['root'],row['path'])
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if digest(target)!=row['sha256']:raise ValueError('Restored file changed')
        if target.suffix=='.sqlite3':
            db=sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True)
            try:
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Restored database failed integrity check')
            finally:db.close()
            databases+=1
    return {'files':len(manifest['files']),'sqlite_integrity_ok':databases,'destination':str(destination),
        'byte_exact':True,'work_started':False,'missing_projects':manifest.get('missing_projects',[]),
        'operational_restore_complete':False,'remaining':'Paths, machine-bound optional tools, restored controller identity and execution permissions require separate reconciliation before starting this copy.'}
