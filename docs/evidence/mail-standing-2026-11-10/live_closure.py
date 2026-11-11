"""Explicit real-Gmail read-only acceptance on one pre-existing self-test mail.

No email send/label change, no model, no ordinary business mail. A temporary
local classification rule is removed in finally; original rules are retained.
"""
from pathlib import Path
import hashlib,http.cookiejar,json,sqlite3,sys,time,urllib.request,uuid
from email.utils import parseaddr
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from control.local_access import read_key
from modules.mail.store import MailStore
from modules.mail.provenance import fingerprint
from sdk.protocol import canonical
from adapters.application_host import WorkbenchProcess
from modules.release_recovery.application import Applications
from host.application_installation import install
from test_mail_standing import policy


def run(root,selection_path,expected_build,out,resume=False):
    out.mkdir(parents=True,exist_ok=False);origin='http://127.0.0.1:18282'
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    report={'passed':False,'real_gmail':True,'actual_desktop_clicks':False,'model_calls':0,'remote_mail_writes':0,'steps':[]};watch_id=None;temporary_rule=None
    def save():(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def passed(case):report['steps'].append({'case':case,'passed':True});save();print(json.dumps({'passed':case}),flush=True)
    def request(path,body=None):
        h={'Origin':origin,'Content-Type':'application/json'}
        if body is not None and path!='/api/local-access':
            with client.open(origin+'/api/session',timeout=5) as r:h['X-Jarvis-Token']=json.load(r)['token']
        q=urllib.request.Request(origin+path,data=canonical(body).encode() if body is not None else None,headers=h)
        with client.open(q,timeout=20) as r:return json.load(r)
    def wait_until(fn,seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            value=fn()
            if value:return value
            time.sleep(1)
        raise TimeoutError('Real Gmail acceptance did not reach the declared condition; no blind retry')
    def mail_snapshot():
        s=MailStore(root)
        try:return {i[0]:s.get(i[0]) for i in s.db.execute('SELECT id FROM objects')}
        finally:s.close()
    def todo_snapshot():
        p=root/'state/commitments.sqlite3'
        if not p.exists():return {}
        db=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        try:return {r['id']:dict(r) for r in db.execute('SELECT * FROM commitments')}
        finally:db.close()
    def bare(value):return {k:v for k,v in value.items() if k not in {'revision','updated'}}
    request('/api/local-access',{'key':read_key(root)});assert request('/api/instance')['application_build']==expected_build
    selection=json.loads(selection_path.read_text(encoding='utf-8'));mid=selection['selected_message_id'];state=request('/api/mail');email=state['email'].lower()
    assert state['account_generation']==selection['generation'];assert not any(r['sender']==email for r in state['rules']),'Existing self-sender rule must not be overwritten by this test'
    before_mail=mail_snapshot();before_todos=todo_snapshot();configs={}
    for p in (root/'config').rglob('*'):
        if p.is_file():configs[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    selected=before_mail['message-'+mid]['message'];assert parseaddr(selected['from'])[1].lower()==email==parseaddr(selected['to'])[1].lower()
    assert 'Jarvis' in selected['subject'] and '验收' in selected['subject']
    existing=request('/api/mail-work',{'action':'inspect','account_generation':selection['generation'],'message_id':mid})['items']
    if resume:
        previous=[e['todo_id'] for w in request('/api/mail-standing')['items'] if w['title']=='【验收】真实邮件持续办事' for e in w['entries'].values() if e['message_id']==mid and e.get('todo_id')]
        assert len(set(previous))==1 and any(t['id']==previous[0] and t['status'] in {'OPEN','DUE'} for t in existing)
        resume_task=previous[0];report['continued_existing_test_item']=True
    else:assert not existing
    try:
        temporary_rule=request('/api/mail',{'action':'rule','sender':email,'category':'important'});passed('existing_unlinked_self_test_mail_and_original_account_verified')
        row=request('/api/mail-standing',{'action':'create','request_id':uuid.uuid4().hex,'title':'【验收】真实邮件持续办事','policy':policy(query=selection['query'],lookback_hours=168,max_checks=3,max_new_items=2,max_followups=1)})
        watch_id=row['id']
        def current():return next(w for w in request('/api/mail-standing')['items'] if w['id']==watch_id)
        assert current()['checks_started']==0
        # Exercise the exact final stable and compatible baseline with an inert
        # real-account mandate. No read or external effect is pending here.
        app=Applications(root);driver=WorkbenchProcess(root,18282,timeout=45)
        app.rollback(driver);baseline=app.state()['active']['build'];install(root,root.parent,Path(app.record(baseline)['path']),port=18282)
        assert current()['id']==watch_id and current()['status']=='DRAFT'
        app.adopt(expected_build,driver,expected_epoch=app.state()['epoch']);install(root,root.parent,Path(app.record(expected_build)['path']),port=18282)
        assert current()['id']==watch_id and current()['status']=='DRAFT';passed('exact_final_packages_roll_back_and_return_with_inert_real_account_mandate_preserved')
        request('/api/mail-standing',{'action':'approve','id':watch_id,'revision':row['revision'],'request_id':uuid.uuid4().hex})
        def checked():
            w=current()
            if w['status']=='NEEDS_INPUT':raise AssertionError(w['error'])
            return w if w['last_checked'] else None
        row=wait_until(checked,150);assert len(row['entries'])==1;entry=next(iter(row['entries'].values()));todo=entry['todo_id'];first=row['last_checked']
        source=request('/api/mail-work',{'action':'source','id':todo});assert source['source_status']=='available' and source['message']['id']==mid
        if resume:
            assert todo==resume_task
            item=request('/api/commitments/'+todo)['current']
            from datetime import datetime,timezone
            when=datetime.fromtimestamp(time.time()+60,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            request('/api/commitments',{'action':'reschedule','id':todo,'revision':item['revision'],'request_id':uuid.uuid4().hex,'due_at':when})
        else:assert todo not in before_todos
        passed('actual_scheduled_google_read_creates_or_reuses_one_private_source_bound_common_test_todo')
        def due():return next((i for i in request('/api/work-status')['items'] if i['id']==todo and i['raw_status']=='DUE' and i['attention']['unread']),None)
        item=wait_until(due,90);request('/api/work-status',{'action':'viewed','key':item['attention']['key'],'version':item['attention']['version']});assert request('/api/commitments/'+todo)['current']['status']=='DUE';passed('real_due_timer_and_shared_read_receipt_do_not_complete_business_work')
        draft=request('/api/mail',{'action':'draft','id':'','revision':0,'value':{'to':email,'subject':'【Jarvis 验收】本地处理草稿，不发送','body':'此草稿仅验证邮件待办的原处理通路，不会提交发送。'}})
        review=request('/api/mail-work',{'action':'review_reply','id':todo,'operation':'send','payload':{'draft_id':draft['id'],'revision':draft['revision']}});assert not review.get('job_id');passed('same_source_task_reaches_original_encrypted_draft_and_review_without_sending')
        def second():
            w=current()
            if w['status']=='NEEDS_INPUT':raise AssertionError(w['error'])
            return w if w['checks_started']>=2 and w['last_checked']>first else None
        row=wait_until(second,330);assert len(row['entries'])==1 and next(iter(row['entries'].values()))['todo_id']==todo
        assert request('/api/mail-work',{'action':'source','id':todo})['source_status']=='available';passed('second_actual_five_minute_google_check_reuses_same_todo_and_keeps_full_source')
        target=request('/api/commitments/'+todo)['current'];request('/api/commitments',{'action':'complete','id':todo,'revision':target['revision'],'request_id':uuid.uuid4().hex})
        wait_until(lambda:next(iter(current()['entries'].values()))['state']=='DONE',15);report['completion_scope']='Test operator confirmed only the synthetic acceptance item; not real business completion'
        passed('test_operator_feedback_reaches_original_task_and_stops_further_followup')
        row=current();request('/api/mail-standing',{'action':'cancel','id':watch_id,'revision':row['config_revision'],'request_id':uuid.uuid4().hex});passed('test_monitor_cancelled_without_cancelling_unrelated_work')
        request('/api/mail',{'action':'remove_rule','id':temporary_rule['id'],'revision':temporary_rule['revision']});temporary_rule=None
        after_mail=mail_snapshot();after_todos=todo_snapshot();changed=[]
        for ident,old in before_mail.items():
            new=after_mail.get(ident)
            if new is None:changed.append('missing:'+ident);continue
            if ident=='account':
                for key in ('email','generation'):
                    if old.get(key)!=new.get(key):changed.append('account:'+key)
                for key in ('scope','refresh_token','client_id','client_secret'):
                    if old['credentials'].get(key)!=new['credentials'].get(key):changed.append('credential:'+key)
            elif old['kind']=='message':
                if old['account_generation']!=new['account_generation'] or fingerprint(old['message'])!=fingerprint(new['message']) or old['message'].get('labels',[])!=new['message'].get('labels',[]):changed.append('message:'+ident)
            elif resume and ident=='mail-work-reviews-'+resume_task and old['kind']=='commitment_effects':
                if (not set(old['reviews'])<=set(new['reviews']) or len(new['reviews'])!=len(old['reviews'])+1
                        or {k:v for k,v in bare(old).items() if k!='reviews'}!={k:v for k,v in bare(new).items() if k!='reviews'}):changed.append('test_review_links:'+ident)
            elif bare(old)!=bare(new):changed.append('object:'+ident)
        config_changes=[name for name,h in configs.items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=h]
        assert not changed and not config_changes and all(after_todos.get(i)==old for i,old in before_todos.items() if not (resume and i==resume_task))
        assert len(after_todos)==len(before_todos)+(0 if resume else 1) and after_todos[todo]['status']=='DONE'
        report['preservation']={'passed':True,'original_mail_objects':len(before_mail),'original_todos':len(before_todos)-(1 if resume else 0),'original_configuration_files':len(configs),'original_changed':0,'new_completed_test_todos':0 if resume else 1,'continued_test_todo_completed':bool(resume),'temporary_rule_removed':True,'test_watch_cancelled':True,'source_content_and_remote_labels_unchanged':True}
        for path in ('/','/companion','/companion/native','/mail-standing.js','/api/mail-standing'):
            with client.open(origin+path,timeout=10) as r:assert r.status==200
        passed('old_data_config_sources_and_rules_preserved_with_shared_surface_routes');report['passed']=True;save()
    except BaseException as e:report['error']={'type':type(e).__name__,'message':str(e)};raise
    finally:
        if watch_id:
            try:
                w=next(w for w in request('/api/mail-standing')['items'] if w['id']==watch_id)
                if w['status']!='CANCELLED':request('/api/mail-standing',{'action':'cancel','id':watch_id,'revision':w['config_revision'],'request_id':uuid.uuid4().hex})
            except Exception:report['cleanup_watch_needs_attention']=True
        if temporary_rule:
            try:request('/api/mail',{'action':'remove_rule','id':temporary_rule['id'],'revision':temporary_rule['revision']})
            except Exception:report['cleanup_rule_needs_attention']=True
        save()


if __name__=='__main__':run(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve(),sys.argv[3],Path(sys.argv[4]).resolve(),resume='--resume-test' in sys.argv[5:])
