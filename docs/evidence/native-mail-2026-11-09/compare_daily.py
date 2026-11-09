"""Compare existing business tables/credentials against the stopped backup.

Only row counts and hashes are emitted; no mail, chat, key or private value.
"""
from pathlib import Path
import hashlib,json,sqlite3,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from backup_daily import digest,table_hashes
from control.credentials import load_envelope
from control.local_access import SESSION_SECONDS,read_key


def without_checked(path):
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        columns=[row[1] for row in db.execute('PRAGMA table_info(task_completion)') if row[1]!='checked']
        selection=','.join('"'+name.replace('"','""')+'"' for name in columns)
        rows=[json.dumps(list(row),ensure_ascii=False,separators=(',',':')) for row in db.execute('SELECT '+selection+' FROM task_completion')]
        return hashlib.sha256('\n'.join(sorted(rows)).encode()).hexdigest()
    finally:db.close()


def browser_sessions(root,backup,expected_new):
    name='private/workbench-sessions.dpapi';old_path=backup/name;new_path=root/name
    if not old_path.exists():
        return {'passed':not new_path.exists() and expected_new==0,'scope':'no pre-existing browser session file'}
    old=load_envelope(old_path);new=load_envelope(new_path)
    now=time.time();reference=(backup/'inventory.json').stat().st_mtime
    before=old['sessions'];after=new['sessions'];created=set(after)-set(before)
    key_match=old['key_hash']==new['key_hash']==hashlib.sha256(read_key(root).encode()).hexdigest()
    valid_preserved=all(token in after and after[token]>=expiry for token,expiry in before.items() if expiry>now)
    expired_revived=any(token in after and after[token]>now for token,expiry in before.items() if expiry<=reference)
    valid_bounds=all(isinstance(expiry,(int,float)) and expiry<=now+SESSION_SECONDS for expiry in after.values())
    expected_creation=len(created)==expected_new and all(reference<after[token]<=now+SESSION_SECONDS for token in created)
    return {'passed':key_match and valid_preserved and not expired_revived and valid_bounds and expected_creation,
        'key_binding_unchanged':key_match,'previous_valid_sessions_preserved':valid_preserved,
        'previous_valid_session_count':sum(expiry>now for expiry in before.values()),
        'previous_expired_session_count':sum(expiry<=reference for expiry in before.values()),
        'expired_sessions_revived':expired_revived,'bounded_expiry':valid_bounds,'new_sessions':len(created),
        'expected_new_sessions':expected_new,'scope':'semantic DPAPI payload check; never prints session tokens'}


def compare(root,backup,*,expected_new_sessions=0):
    before=json.loads((backup/'inventory.json').read_text(encoding='utf-8'));changed=[];derived=[];checked=0
    for name,tables in before['databases'].items():
        current=table_hashes(root/name)
        for table,meta in tables.items():
            checked+=1
            if current.get(table)==meta:continue
            if table=='task_completion' and without_checked(root/name)==without_checked(backup/name):
                derived.append({'database':name,'table':table,'only_changed_column':'checked'});continue
            changed.append({'database':name,'table':table,'before':meta,'after':current.get(table)})
    session_name='private/workbench-sessions.dpapi'
    private_changed=[name for name,meta in before['files'].items() if name.endswith('.dpapi') and name!=session_name and
        (not (root/name).is_file() or digest(root/name)!=meta['sha256'])]
    unchanged_names=[name for name in before['files'] if
        (name.startswith(('config/','sessions/')) and not name.endswith('.sqlite3')) or name in {'state/STOP','state/LATCH'}]
    unchanged_files=[name for name in unchanged_names if
        not (root/name).is_file() or digest(root/name)!=before['files'][name]['sha256']]
    control_match=all((name in before['files'])==(root/name).is_file() for name in ('state/STOP','state/LATCH'))
    assets_changed=[]
    for name,meta in before.get('assets_metadata',{}).items():
        path=root/name
        if not path.is_file() or [path.stat().st_size,path.stat().st_mtime_ns]!=meta:assets_changed.append(name)
    sessions=browser_sessions(root,backup,expected_new_sessions)
    result={'passed':not changed and not private_changed and not assets_changed and not unchanged_files and control_match and sessions['passed'],'existing_tables_checked':checked,
            'business_table_changes':changed,'derived_only_changes':derived,'dpapi_files_changed':private_changed,
            'dpapi_credential_files_checked':sum(name.endswith('.dpapi') and name!=session_name for name in before['files']),
            'browser_sessions':sessions,
            'config_session_files_checked':len(unchanged_names),'config_session_files_changed':unchanged_files,
            'stop_and_latch_presence_unchanged':control_match,
            'asset_metadata_files_checked':len(before.get('assets_metadata',{})),'assets_metadata_changed':assets_changed,
            'scope':'all backed-up existing tables; encrypted DPAPI files; no claim of full asset-byte hashing'}
    print(json.dumps(result,ensure_ascii=False,indent=2));return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);parser.add_argument('backup',type=Path)
    parser.add_argument('--expected-new-browser-sessions',type=int,default=0);args=parser.parse_args()
    value=compare(args.root.resolve(),args.backup.resolve(),expected_new_sessions=args.expected_new_browser_sessions);sys.exit(not value['passed'])
