"""Back up only existing model-library metadata; no asset migration or deletion."""
from pathlib import Path
import hashlib,json,shutil,sqlite3
from control.paths import reject_links


def location(root):
    file=Path(root)/'model-library/location.json';reject_links(file)
    repository=Path(json.loads(file.read_text(encoding='utf-8'))['repository']).resolve() if file.exists() else Path(root)/'model-library'
    reject_links(repository);return file,repository


def tables(path):
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        result={}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            values=sorted(json.dumps(list(row),ensure_ascii=False,default=lambda b:bytes(b).hex()) for row in db.execute('SELECT * FROM "'+name.replace('"','""')+'"'))
            result[name]={'rows':len(values),'sha256':hashlib.sha256('\n'.join(values).encode()).hexdigest()}
        return result
    finally:db.close()


def inventory(root):
    loc,repo=location(root);catalog=repo/'catalog.sqlite3'
    assets={p.relative_to(repo).as_posix():[p.stat().st_size,p.stat().st_mtime_ns] for p in (repo/'objects').rglob('*') if p.is_file()}
    return {'present':catalog.is_file(),'locator_sha256':hashlib.sha256(loc.read_bytes()).hexdigest() if loc.exists() else None,
        'tables':tables(catalog) if catalog.exists() else {},'assets':assets}


def backup_catalog(root,destination):
    before=inventory(root)
    if not before['present']:return before
    loc,repo=location(root);out=Path(destination)/'optional-model-library';out.mkdir(parents=True,exist_ok=False)
    if loc.exists():shutil.copyfile(loc,out/'location.json')
    source=sqlite3.connect((repo/'catalog.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);target=sqlite3.connect(out/'catalog.sqlite3')
    try:
        source.backup(target);assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:target.close();source.close()
    assert before==inventory(root),'Model library changed during metadata backup; retain backup and inspect'
    return before
