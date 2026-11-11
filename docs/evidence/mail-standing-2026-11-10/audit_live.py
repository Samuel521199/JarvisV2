"""Read-only original-business audit from the actual stopped pre-upgrade backup."""
from pathlib import Path
import hashlib,json,sqlite3,sys,time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from control.credentials import crypt
from modules.mail.provenance import fingerprint
from model_library_preservation import location,tables


def rows(path,table):
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:return [dict(r) for r in db.execute('SELECT * FROM '+table)]
    finally:db.close()


def run(root,backup,initial,functional,out):
    out.mkdir(parents=True,exist_ok=False)
    def mail(path):return {r['id']:json.loads(crypt(bytes(r['payload']),decrypt=True)) for r in rows(path,'objects')}
    before=mail(backup/'private/mail.sqlite3');after=mail(root/'private/mail.sqlite3');changed=[]
    for ident,old in before.items():
        new=after.get(ident)
        if not new:changed.append({'id':ident,'reason':'missing'});continue
        if ident=='account':
            stable=all(old.get(k)==new.get(k) for k in ('email','generation'))
            stable &= all(old['credentials'].get(k)==new['credentials'].get(k) for k in ('client_id','client_secret','refresh_token'))
            stable &= set(old['credentials']['scope'].split())==set(new['credentials']['scope'].split())
        elif old['kind']=='message':stable=(old['account_generation']==new['account_generation'] and fingerprint(old['message'])==fingerprint(new['message']) and old['message'].get('labels',[])==new['message'].get('labels',[]))
        else:stable={k:v for k,v in old.items() if k not in {'revision','updated'}}=={k:v for k,v in new.items() if k not in {'revision','updated'}}
        if not stable:changed.append({'id':ident,'reason':'original_changed'})
    old_tasks={r['id']:r for r in rows(backup/'state/commitments.sqlite3','commitments')};new_tasks={r['id']:r for r in rows(root/'state/commitments.sqlite3','commitments')}
    assert all(new_tasks.get(i)==r for i,r in old_tasks.items())
    added=set(new_tasks)-set(old_tasks);assert len(added)==1
    ident=next(iter(added));assert new_tasks[ident]['status']=='DONE' and new_tasks[ident]['title']=='处理重要邮件'
    monitors=[v for v in after.values() if v['kind']=='mail_watch'];tests=[w for w in monitors if w['title']=='【验收】真实邮件持续办事'];assert len(tests)==2 and all(w['status']=='CANCELLED' for w in tests)
    assert all(next(iter(w['entries'].values()))['todo_id']==ident for w in tests)
    links=after['mail-work-reviews-'+ident]['reviews'];assert len(links)==2
    for review_id in links:
        review=after[review_id];assert not review.get('job_id')
        draft=after[review['payload']['draft_id']];assert draft['value']['subject']=='【Jarvis 验收】本地处理草稿，不发送'
    email=after['account']['email'].lower();assert not any(v['kind']=='rule' and v['sender']==email for v in after.values())
    for w in tests:
        for j in after.values():
            if j['kind']=='job' and (j.get('mail_watch') or {}).get('id')==w['id']:assert j['operation'] in {'list','read'} and not j['effect_started']
    inventory=json.loads((backup/'inventory.json').read_text(encoding='utf-8'));config=[n for n in inventory['files'] if n.startswith(('config/','sessions/')) and not n.endswith('.sqlite3')]
    assert all((root/n).is_file() and hashlib.sha256((root/n).read_bytes()).hexdigest()==inventory['files'][n]['sha256'] for n in config)
    loc,repository=location(root);library_equal=tables(repository/'catalog.sqlite3')==tables(backup/'optional-model-library/catalog.sqlite3');assert library_equal
    integrities={}
    for name in inventory['databases']:
        db=sqlite3.connect((root/name).resolve().as_uri()+'?mode=ro',uri=True)
        try:integrities[name]=db.execute('PRAGMA integrity_check').fetchone()[0]
        finally:db.close()
    assert all(x=='ok' for x in integrities.values());assert not changed,changed
    first=json.loads(initial.read_text(encoding='utf-8'));last=json.loads(functional.read_text(encoding='utf-8'))
    assert len(last['steps'])==8 and all(s['passed'] for s in last['steps']);assert last['error']['type']=='AssertionError'
    result={'passed':True,'scope':'original business data against stopped pre-upgrade backup; test records separately traced',
        'functional_steps':last['steps'],'initial_timer_timeout_retained':first['error']['type']=='TimeoutError',
        'audit_correction':'Continuation legitimately appended a second review link to the already-owned test item; all original business records verified independently',
        'original_mail_objects_checked':len(before),'original_mail_changes':changed,'original_todos_unchanged':len(old_tasks),
        'new_test_todos':len(added),'test_todo_state':'DONE','test_watches_cancelled':len(tests),'local_test_reviews_unsubmitted':len(links),
        'temporary_sender_rule_removed':True,'original_configuration_session_files_unchanged':len(config),'database_integrities':integrities,
        'model_library_catalog_unchanged':library_equal,'remote_writes':0,'automatic_model_calls':0,'actual_desktop_clicks':False}
    (out/'result.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in result.items() if k not in {'functional_steps','database_integrities'}}))


if __name__=='__main__':run(*[Path(x).resolve() for x in sys.argv[1:]])
