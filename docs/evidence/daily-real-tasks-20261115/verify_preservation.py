"""Verify old business rows, settings, immutable runtime and actual delivery receipts."""
from pathlib import Path
import collections,hashlib,json,sqlite3,sys,time
from session import DATA,OUT,write
from tools.workstation import state,instance
from control.controller_pin import read
from control.credentials import load_envelope
from control.local_access import read_key,SESSION_SECONDS

def rows(db,table):
    return collections.Counter(tuple(row) for row in db.execute('SELECT * FROM "'+table.replace('"','""')+'"'))

def main():
    old=Path('D:/Jarvis-Recovery/controllers/2026-11-15-r3/user-data/state/core.sqlite3')
    before=sqlite3.connect(old.as_uri()+'?mode=ro&immutable=1',uri=True);after=sqlite3.connect((DATA/'state/core.sqlite3').as_uri()+'?mode=ro',uri=True)
    checks={}
    try:
        for table in ('tasks','grants','facts','knowledge_sources','release_slots','goal_plans','goal_context','work_revisions','model_calls'):
            prior=rows(before,table);current=rows(after,table);lost=prior-current
            checks[table]={'original_rows':sum(prior.values()),'changed_or_missing_original_rows':sum(lost.values()),'passed':not lost}
        integrity=after.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        returns=after.execute("SELECT count(*) FROM events WHERE kind='learning.repair_return'").fetchone()[0]
    finally:before.close();after.close()
    artifacts={}
    for label in ('english','materials'):
        result=json.loads((OUT/(label+'-task-result.json')).read_text());r=result['delivery_receipt'];path=(DATA/r['relative_path']).resolve()
        assert path.is_relative_to((DATA/'artifacts').resolve());raw=path.read_bytes();payload=json.loads(raw)
        exports=json.loads((OUT/'raw-text-exports.json').read_text(encoding='utf-8'))['exports']
        actual=exports[label+'-delivered.txt']['original_utf8'].replace('\r\n','\n')
        artifacts[label]={'file_sha256_matches_receipt':hashlib.sha256(raw).hexdigest()==r['sha256'],
            'bytes_match_receipt':len(raw)==r['bytes'],'saved_text_matches_export':payload['text']==actual,
            'text_sha256':hashlib.sha256(payload['text'].encode()).hexdigest()}
        assert all(v for k,v in artifacts[label].items() if k!='text_sha256')
    application=state(DATA);package=DATA/'deployment/packages'/application['active']['build'];manifest=json.loads((package/'application.json').read_text())
    runtime_unchanged=all(hashlib.sha256((package/name).read_bytes()).hexdigest()==meta['sha256'] for name,meta in manifest['files'].items())
    baseline=Path('D:/Jarvis-Recovery/jarvis/2026-11-15-upgrade-r1/snapshot/daily');config={}
    for parent in ('config','private'):
        for p in (baseline/parent).rglob('*'):
            if p.is_file() and not p.name.endswith(('.sqlite3','-wal','-shm','.lock')):
                target=DATA/p.relative_to(baseline);config[p.relative_to(baseline).as_posix()]=target.exists() and hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(p.read_bytes()).digest()
    pin=read(DATA)
    # A successful authenticated client legitimately creates/slides a session.
    # Keep the failed byte-identity check; verify the narrow exception instead.
    session_name='private/workbench-sessions.dpapi';now=time.time()
    prior=load_envelope(baseline/session_name);current=load_envelope(DATA/session_name)
    old_sessions=prior['sessions'];new_sessions=current['sessions']
    auth_checks={
        'same_key_binding':prior['key_hash']==current['key_hash']==hashlib.sha256(read_key(DATA).encode()).hexdigest(),
        'live_original_sessions_preserved':all(token in new_sessions and new_sessions[token]>=expiry for token,expiry in old_sessions.items() if expiry>now),
        'session_shape_and_max_lifetime_valid':all(isinstance(token,str) and token.isascii() and 32<=len(token)<=128 and type(expiry) in (int,float) and expiry<=now+SESSION_SECONDS for token,expiry in new_sessions.items()),
        'only_session_file_changed':all(value for name,value in config.items() if name!=session_name)}
    auth={'checks':auth_checks,'old_count':len(old_sessions),'new_count':len(new_sessions),'added_count':len(new_sessions.keys()-old_sessions.keys()),
          'scope':'Authorized API authentication changes session tokens/expiry; no tokens or hashes disclosed. This checks format, key binding and original live sessions, not attribution of every new session.'}
    result={'passed':all(c['passed'] for c in checks.values()) and integrity and runtime_unchanged and all(auth_checks.values()),
       'preexisting_rows':checks,'database_integrity_ok':integrity,'original_config_and_private_files':len(config),'original_config_and_private_files_unchanged':all(config.values()),
       'adopted_runtime_unchanged':runtime_unchanged,'runtime_files_checked':len(manifest['files']),'application':application,'instance':instance(18282),
       'controller_protocol':pin['controller_protocol'],'controller_policy_sha256':pin['policy_sha256'],'actual_artifacts':artifacts,
       'automatic_repair_return_event_count':returns,'scope':'Old business rows and grants, settings, immutable runtime and delivery files. New authorized tasks and tool release are expected additions.'}
    result['expected_authentication_change']=auth
    filename=sys.argv[1] if len(sys.argv)>1 else 'preservation-r2.json'
    assert Path(filename).name==filename and filename.startswith('preservation-') and filename.endswith('.json')
    assert not (OUT/filename).exists(),'Preserve previous observation'
    write(OUT/filename,result);print(json.dumps({'passed':result['passed'],'file':filename,'runtime_unchanged':runtime_unchanged,'repair_return_events':returns}),flush=True)
    assert result['passed']

if __name__=='__main__':main()
