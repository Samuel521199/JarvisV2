"""One-shot offline Codex home relocation. Run only AFTER closing Codex.

No model/account calls, no rewriting chat contents, no background watcher. The
NTFS compatibility junction keeps existing shortcuts using the same new home.
"""
import argparse,hashlib,json,os,shutil,sqlite3,subprocess,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
from control.paths import reject_links


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def active_clients():
    script="Get-Process | Where-Object { $_.ProcessName -eq 'codex' -or $_.ProcessName -eq 'codex-code-mode-host' -or ($_.ProcessName -eq 'ChatGPT' -and $_.Path -like '*OpenAI.Codex*') } | Select-Object ProcessName,Id | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,encoding='utf-8',timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Cannot verify Codex processes; keep original home')
    return json.loads(result.stdout) if result.stdout.strip() else []


def require_offline():
    if active_clients():raise RuntimeError('Close all Codex app/CLI windows first, then run this migration again. No original files were removed.')


def independent_disks():
    script="$ErrorActionPreference='Stop'; @{primary_disk=(Get-Partition -DriveLetter E | Get-Disk).Number;backup_disk=(Get-Partition -DriveLetter D | Get-Disk).Number} | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,encoding='utf-8',timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Cannot verify independent E/D disks; original home retained')
    value=json.loads(result.stdout)
    if any(type(value.get(k)) is not int for k in ('primary_disk','backup_disk')) or value['primary_disk']==value['backup_disk']:
        raise ValueError('Primary E and recovery D must be on different physical disks')
    return value


EPHEMERAL_DIRS={'.sandbox','.sandbox-bin','.sandbox-secrets','.tmp','tmp','thread-writer-locks','mcp-oauth-locks','project-metadata-locks'}


def home_files(source):
    files=[];omitted=[]
    for folder,dirs,names in os.walk(source,followlinks=False):
        parent=Path(folder)
        if parent==source:dirs[:]=[name for name in dirs if name not in EPHEMERAL_DIRS]
        for name in dirs:
            item=parent/name
            if item.is_symlink() or item.is_junction():raise ValueError('Unexpected reparse directory; preserve original for review')
        for name in names:
            item=parent/name
            if item.is_symlink():raise ValueError('Unexpected linked file; preserve original')
            known_lock=parent==source and name in {'auth.json.lock','auth.lock','session_index.jsonl.lock','.sqlite-maintenance.lock'}
            sqlite_shm=False
            if name.endswith('-shm'):
                database=item.with_name(name[:-4])
                if database.is_file():
                    reject_links(database)
                    with database.open('rb') as stream:sqlite_shm=stream.read(16)==b'SQLite format 3\x00'
            if known_lock or sqlite_shm:omitted.append(item.relative_to(source).as_posix());continue
            files.append(item)
    return files,omitted


def verify_home(source,records):
    """Catch earlier-file changes or new sessions even if a client already exited."""
    paths,_=home_files(source)
    if {p.relative_to(source).as_posix() for p in paths}!={row['path'] for row in records}:
        raise ValueError('Source inventory changed after copy; original home retained')
    for row in records:
        path=source/row['path']
        if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:
            raise ValueError('Source content changed after copy; original home retained')


def rebind_sqlite_config(text,source,target):
    import re,tomllib
    config=tomllib.loads(text);configured=config.get('sqlite_home')
    if not configured:return text
    old=Path(configured).resolve();source=source.resolve()
    if not old.is_relative_to(source):raise ValueError('Separate SQLite home requires reconciliation')
    value=str(target/old.relative_to(source))
    changed=re.sub(r'^(\s*)sqlite_home\s*=.*$',lambda match:match[1]+'sqlite_home = '+json.dumps(value),text,count=1,flags=re.MULTILINE)
    if tomllib.loads(changed)!={**config,'sqlite_home':value}:raise ValueError('SQLite path rebinding changed unexpected settings')
    return changed


def copy_home(source,destination,archive):
    """Offline byte-checked copy with an independently verified ZIP backup."""
    original_path=Path(source).absolute();source=original_path.resolve();destination=Path(destination).absolute();archive=Path(archive).absolute()
    if destination.exists() or archive.exists():raise FileExistsError('Keep previous migration files; choose a fresh destination/archive')
    if destination==source or destination.is_relative_to(source) or source.is_relative_to(destination):raise ValueError('Homes must be separate')
    require_offline();reject_links(original_path);reject_links(destination);reject_links(archive)
    destination.mkdir(parents=True);archive.parent.mkdir(parents=True,exist_ok=True)
    files,omitted=home_files(source)
    total=sum(path.stat().st_size for path in files)
    same_volume=destination.stat().st_dev==archive.parent.stat().st_dev
    home_required=(2 if same_volume else 1)*total+1024**3
    if shutil.disk_usage(destination).free<home_required or shutil.disk_usage(archive.parent).free<total+1024**3:
        raise ValueError('Insufficient home/recovery volume space; original home retained')
    records=[]
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as backup:
        for index,item in enumerate(files):
            if index%100==0:require_offline();print(f'Copied {index}/{len(files)} files',flush=True)
            before=item.stat();name=item.relative_to(source).as_posix();target=destination/name
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(item,target)
            value=digest(item)
            if digest(target)!=value or (before.st_size,before.st_mtime_ns)!=(item.stat().st_size,item.stat().st_mtime_ns):
                raise ValueError('Source changed; keep originals and retry only after Codex exits')
            backup.write(item,name);records.append({'path':name,'bytes':before.st_size,'sha256':value})
    require_offline()
    with zipfile.ZipFile(archive) as backup:
        if backup.testzip() is not None:raise ValueError('Recovery ZIP integrity failed')
        for row in records:
            with backup.open(row['path']) as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=row['sha256']:
                    raise ValueError('Recovery ZIP does not match the verified home')
    databases=[]
    for item in destination.rglob('*'):
        if not item.is_file() or item.suffix not in {'.sqlite','.sqlite3','.db'}:continue
        db=sqlite3.connect(item.as_uri()+'?mode=ro',uri=True)
        try:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Copied Codex database integrity failed')
        finally:db.close()
        databases.append(item.relative_to(destination).as_posix())
    report={'schema':1,'source':str(source),'destination':str(destination),'archive':str(archive),
        'files':records,'sqlite_integrity_ok':databases,'omitted_ephemeral_files':omitted,
        'omitted_rebuildable_directories':sorted(EPHEMERAL_DIRS),'copied_bytes':total,'copied_files':len(records),
        'checked_utc':datetime.now(timezone.utc).isoformat(),'original_removed':False,'account_actions':0}
    (destination.parent/'codex-migration-copy.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def redirect_home(source,target,*,set_home=None,verify_source=None):
    """Swap only the default home; restore it if junction/environment setup fails."""
    if source!=Path.home()/'.codex' or source.is_junction() or source.is_symlink():
        raise ValueError('Invalid original home for cutover')
    if not target.is_dir() or target.is_junction() or target.is_symlink():
        raise ValueError('Expected verified regular destination directory')
    require_offline()
    retired=source.with_name('.codex-before-E-'+str(time.time_ns()))
    if retired.parent!=Path.home() or retired.exists():raise ValueError('Invalid original-home retirement path')
    source.rename(retired)
    try:
        require_offline()
        if verify_source is not None:verify_source(retired)
        require_offline()
        script="New-Item -ItemType Junction -Path '"+str(source).replace("'","''")+"' -Target '"+str(target).replace("'","''")+"' | Out-Null"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=20)
        if result.returncode or source.resolve()!=target.resolve():raise RuntimeError('Codex home junction could not be verified')
        if set_home is not None:set_home(str(target))
        else:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,'Environment') as key:
                winreg.SetValueEx(key,'CODEX_HOME',0,winreg.REG_SZ,str(target))
    except BaseException:
        if source.is_junction():source.rmdir()
        if not source.exists():retired.rename(source)
        raise
    return retired


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true');parser.add_argument('--destination',type=Path,default=Path('E:/Jarvis/codex-home'))
    args=parser.parse_args();source=Path.home()/'.codex';target=args.destination.absolute()
    clients=active_clients()
    if args.check:
        print(json.dumps({'ready':not clients,'active_client_count':len(clients) if isinstance(clients,list) else 1,
            'source':str(source),'destination':str(target),'backup_root':'D:/Jarvis-Recovery/codex','originals_unchanged':True}));return
    require_offline()
    if source.is_junction() or source.is_symlink():raise ValueError('Existing home is already redirected; inspect it before proceeding')
    if target.parent!=Path('E:/Jarvis'):raise ValueError('This cutover is restricted to the owner-authorized E project root')
    if target.exists():raise FileExistsError('Final home already exists; originals retained')
    configured_home=os.environ.get('CODEX_HOME')
    if configured_home and Path(configured_home).resolve()!=source.resolve():
        raise ValueError('A different CODEX_HOME needs reconciliation first; originals retained')
    sqlite_env=os.environ.get('CODEX_SQLITE_HOME')
    if sqlite_env and not Path(sqlite_env).resolve().is_relative_to(source.resolve()):
        raise ValueError('A separate SQLite environment path needs reconciliation first; originals retained')
    import tomllib
    config=tomllib.loads((source/'config.toml').read_text(encoding='utf-8'))
    configured=config.get('sqlite_home')
    if configured and not Path(configured).resolve().is_relative_to(source.resolve()):
        raise ValueError('A separate configured SQLite home needs explicit reconciliation; original home retained')
    disks=independent_disks()
    archive=Path('D:/Jarvis-Recovery/codex')/('codex-original-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip')
    # Failed/interrupted attempts retain a unique staging tree and originals;
    # the final home is never a half-copied destination on the next retry.
    stage=target.with_name(target.name+'.pending-'+str(time.time_ns()))
    report=copy_home(source,stage,archive);require_offline()
    if independent_disks()!=disks:raise RuntimeError('Disk layout changed; keep original home')
    report['independent_disk_backup']=disks
    # Do not split an explicit, separately configured SQLite home silently.
    config=tomllib.loads((stage/'config.toml').read_text(encoding='utf-8'))
    configured=config.get('sqlite_home')
    if configured and not Path(configured).resolve().is_relative_to(source.resolve()):
        raise ValueError('A separate configured SQLite home needs explicit reconciliation; original home retained')
    if configured:
        text=(stage/'config.toml').read_text(encoding='utf-8')
        (stage/'config.toml').write_text(rebind_sqlite_config(text,source,target),encoding='utf-8')
        report['configuration_changes']=[{'path':'config.toml','field':'sqlite_home','new_sha256':digest(stage/'config.toml')}]
    if target.exists():raise FileExistsError('Final home already exists; originals retained')
    stage.rename(target);report['destination']=str(target)
    retired=redirect_home(source,target,verify_source=lambda retired:verify_home(retired,report['files']))
    report.update(original_retired=str(retired),junction_verified=True,code_home_set=str(target),
        restart_verification_required=True)
    # The raw recovery ZIP is verified before deleting only the exact retired
    # home. The new junction must resolve to the authorized E location.
    if not (retired.parent==Path.home() and retired.name.startswith('.codex-before-E-') and source.resolve()==target.resolve()
            and target.is_dir() and archive.is_file()):raise RuntimeError('Final home/archive guard failed; retired original retained')
    try:shutil.rmtree(retired);report['original_removed']=True
    except OSError as error:report['cleanup_pending']=str(error)
    (target.parent/'codex-migration-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'copied_files':report['copied_files'],'bytes':report['copied_bytes'],
        'sqlite_databases':len(report['sqlite_integrity_ok']),'memory_home':str(target),'restart_codex_now':True,
        'original_removed':report['original_removed']}))


if __name__=='__main__':main()
