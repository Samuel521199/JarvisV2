"""Owner-scoped Gmail read/check -> existing commitments -> bounded follow-up.

No model, mail writes, second mail worker or mail-content execution. All remote
reads use Mailbox's durable jobs, refresh, cancellation and original queue.
"""
from datetime import datetime,timezone
import time,uuid
from control.application_runtime import accepting,require_accepting
from control.network import NetworkGate
from control.recovery.gate import StopGate
from control.time_windows import quiet
from modules.mail.store import MailStore
from modules.mail.standing import KIND,identity,policy,present,rows
from modules.mail.provenance import fingerprint
from modules.task_resource.commitments import Commitments
from host import commitments,mail_work
from sdk.mail import classify,identifier,capabilities
from sdk.protocol import CoreError,digest

NOTE='依据主人确认的 Gmail 常设委托自动创建；邮件正文不是执行指令。'
RETRY={'mail_network','mail_google_error','mail_rate_limit','mail_busy','mail_interrupted','application_maintenance'}


def read(root):
    if not present(root):return {'schema':'jarvis.mail-standing.v1','items':[]}
    store=MailStore(root)
    try:
        account=store.get('account',True)
        return {'schema':'jarvis.mail-standing.v1','items':[{k:v for k,v in r.items() if k not in {'seen','scan'}} for r in rows(store)],
                'connected':bool(account and account.get('credentials')),'model_calls':0,'automatic_mail_writes':0}
    finally:store.close()


def notify(watch,kind,now):
    watch['notice']={'kind':kind,'new_items':watch['new_items'],'at':now}
    watch['notice_pending']=True


def save(store,watch):
    if store.get(watch['id'],True)==watch:return
    watch.update(store.put(watch,watch['revision']))


def command(root,mailbox,value,runner=None):
    fields={'create':{'request_id','title','policy'},'edit':{'id','revision','request_id','title','policy'},
            **{a:{'id','revision','request_id'} for a in ('approve','pause','resume','cancel','check_now')}}
    if (not isinstance(value,dict) or not isinstance(value.get('action'),str) or value['action'] not in fields
            or set(value)!={'action'}|fields[value['action']]):raise CoreError('mail_watch_invalid','Unexpected mailbox mandate command')
    action=value['action'];request=value['request_id'];identifier(request)
    if len(request)<8:raise CoreError('mail_watch_invalid','Provide a bounded unique request identity')
    if action not in {'pause','cancel'}:require_accepting(root);StopGate(root).require_running()
    if action!='create':identity(value['id'])
    with mailbox.lock:
        store=MailStore(root)
        try:
            operation='mail-watch-op-'+digest(request)[:40];old=store.get(operation,True);signature=digest(value)
            if old:
                if old['signature']!=signature:raise CoreError('conflict','Mailbox mandate request content changed')
                return old['result']
            account=store.get('account',True)
            if action in {'create','edit'}:
                config=policy(value['policy']);title=value['title']
                if not isinstance(title,str) or not 1<=len(title.strip())<=100:raise CoreError('mail_watch_invalid','Provide a short mandate title')
            if action=='create':
                if len(rows(store))>=5:raise CoreError('mail_watch_capacity','At most five retained mailbox mandates')
                if not account or not account.get('credentials') or not capabilities(account['credentials'].get('scope',''))['read']:
                    raise CoreError('mail_auth_required','Connect an authorized Gmail account first')
                watch={'id':'mail-watch-'+digest(request)[:32],'kind':KIND,'schema':1,'revision':0,'config_revision':1,
                    'title':title,'generation':account['generation'],'policy':config,'status':'DRAFT','granted':False,
                    'next_at':time.time(),'checks_started':0,'new_items':0,'seen':{},'entries':{},'scan':None,
                    'phase':'REVIEW','error':None,'last_checked':None,'notice':None,'notice_revision':0,'notice_pending':False,'notified_at':0}
            else:
                watch=store.get(value['id'])
                if watch['kind']!=KIND or type(value['revision']) is not int or value['revision']!=watch['config_revision']:
                    raise CoreError('conflict','Mailbox mandate changed; refresh before control')
                if action=='edit':
                    if watch['status'] not in {'PAUSED','DRAFT','NEEDS_INPUT'}:raise CoreError('mail_watch_busy','Pause before editing the mandate')
                    if watch['generation']!=(account or {}).get('generation'):raise CoreError('mail_account_changed','Create a new mandate for a different account')
                    watch.update(policy=config,title=title,status='DRAFT',granted=False,scan=None,error=None,phase='REVIEW',next_at=time.time())
                elif action in {'approve','resume','check_now'}:
                    allowed={'approve':{'DRAFT'},'resume':{'PAUSED','NEEDS_INPUT'},'check_now':{'ACTIVE'}}[action]
                    if watch['status'] not in allowed or action!='approve' and not watch['granted']:
                        raise CoreError('mail_watch_state','Explicit initial approval is required; terminal mandates cannot resume')
                    if not account or not account.get('credentials') or watch['generation']!=account['generation']:
                        raise CoreError('mail_account_changed','Reconnect the original Gmail account')
                    if watch['checks_started']>=watch['policy']['max_checks'] or watch['new_items']>=watch['policy']['max_new_items']:
                        raise CoreError('mail_watch_budget','Edit and review increased limits; previous usage is retained')
                    watch.update(status='ACTIVE',granted=True,error=None,phase='WAITING',next_at=time.time())
                elif action=='pause':
                    if watch['status']=='CANCELLED':raise CoreError('mail_watch_state','A cancelled mandate cannot resume')
                    watch.update(status='PAUSED',phase='PAUSED')
                else:watch.update(status='CANCELLED',phase='CANCELLED')
                watch['config_revision']+=1
                # Revocation is durable before cancelling a queued/in-flight read.
                if watch['scan']:
                    pending=watch['scan'].get('pending')
                    save(store,watch)
                    if pending:
                        job=store.get(pending['id'],True)
                        if job and job['status'] in {'READY','RUNNING','WAITING','WAITING_AUTH','WAITING_NETWORK','WAITING_SCOPE'}:
                            mailbox.command({'action':'cancel','id':job['id']})
                    # An enabled recheck keeps frozen already-produced task links,
                    # starts a fresh bounded scan and never resets usage counters.
                    watch['scan']=None
            with store.transaction():
                save(store,watch);result={'id':watch['id'],'revision':watch['config_revision'],'status':watch['status']}
                store.put({'id':operation,'kind':'mail_watch_operation','signature':signature,'result':result},0)
        finally:store.close()
    if runner is not None:runner.wake.set()
    return result


def eligible(message,rules):
    if set(message.get('labels',[]))&{'SPAM','TRASH'}:return False
    category=classify(message,rules)['category']
    return category not in {'spam','suspicious','promotion'} and (category=='important' or 'STARRED' in message.get('labels',[]))


def followups(root,watch,now):
    if not watch['entries'] or not commitments.exists(root):return
    with Commitments(root) as tasks:
        for entry in watch['entries'].values():
            if not entry.get('todo_id'):continue
            current=tasks.read(entry['todo_id']);status=current['status']
            if entry.get('todo_revision')!=current['revision'] or entry.get('state')!=status:
                entry.update(todo_revision=current['revision'],state=status)
                if status in {'DONE','CANCELLED'}:notify(watch,'feedback',now)
            if (status=='DUE' and entry['followups']<watch['policy']['max_followups']
                    and now>=max(entry['next_followup'],(current['due_at'] or now)+watch['policy']['followup_seconds'])
                    and not quiet(watch['policy'],now)):
                entry.update(followups=entry['followups']+1,next_followup=now+watch['policy']['followup_seconds'])
                notify(watch,'followup',now)


def queue(store,mailbox,watch,scan,operation,payload,now):
    key=digest([watch['id'],watch['config_revision'],scan['ordinal'],scan['pages'],scan['index'],operation,scan['attempt']])
    pending={'id':'job-'+digest(key)[:40],'request_id':key,'operation':operation,'payload':payload}
    scan['pending']=pending;save(store,watch)
    return mailbox.submit_read(key,operation,payload,watch={'id':watch['id'],'revision':watch['config_revision']})


def ingest(root,store,watch,message,now):
    rules=store.listing('rule',100)
    if not eligible(message,rules):return False
    generation=watch['generation'];mid=identifier(message['id']);family=digest(['gmail',generation,mid]);signature=fingerprint(message)
    entry=watch['entries'].get(family)
    if entry and entry['source_digest']!=signature:
        raise CoreError('mail_source_changed','Existing work source changed; review the original item')
    inspected=mail_work.inspect(root,{'account_generation':generation,'message_id':mid})
    if inspected['source_digest']!=signature:raise CoreError('mail_source_changed','Mail cache changed before creating work')
    if not entry:
        if len(watch['entries'])>=100:raise CoreError('mail_watch_capacity','Review retained mail task history first')
        when=datetime.fromtimestamp(now+watch['policy']['due_delay_seconds'],timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        entry={'message_id':mid,'source_digest':signature,'request_id':digest(['mail-watch-todo',generation,mid])[:32],
            'due_at':when,'todo_id':None,'followups':0,'next_followup':now+watch['policy']['followup_seconds'],'state':'PENDING'}
        watch['entries'][family]=entry;save(store,watch)
    if entry['todo_id']:return False
    if inspected['items']:
        current=inspected['items'][0];created=False
    else:
        if not entry.get('reserved_new'):
            if watch['new_items']>=watch['policy']['max_new_items']:raise CoreError('mail_watch_budget','New-task allowance exhausted')
            watch['new_items']+=1;entry['reserved_new']=True;save(store,watch)
        result=mail_work.create(root,{'account_generation':generation,'message_id':mid,'source_digest':signature,
            'title':'处理重要邮件','due_at':entry['due_at'],'request_id':entry['request_id']},authorization_note=NOTE)
        current=result['current'];created=not result['existing']
    entry.update(todo_id=current['id'],todo_revision=current['revision'],state=current['status'])
    notify(watch,'new_mail',now)
    save(store,watch);return created


def tick_one(root,mailbox,store,watch,now):
    if watch['status']=='ACTIVE':followups(root,watch,now)
    if watch['notice_pending'] and not quiet(watch['policy'],now) and now-watch['notified_at']>=watch['policy']['notification_interval_seconds']:
        watch.update(notice_pending=False,notice_revision=watch['notice_revision']+1,notified_at=now)
    if watch['status']!='ACTIVE':save(store,watch);return
    NetworkGate(root).require_online()
    account=store.get('account',True)
    if not account or not account.get('credentials') or account['generation']!=watch['generation']:
        raise CoreError('mail_account_changed','Original Gmail account disconnected or replaced')
    scan=watch['scan']
    if scan is None:
        if watch['next_at']>now:save(store,watch);return
        if watch['checks_started']>=watch['policy']['max_checks']:raise CoreError('mail_watch_budget','Check allowance exhausted')
        watch['checks_started']+=1
        lower=(watch['last_checked']-300 if watch['last_checked'] else now-watch['policy']['lookback_hours']*3600)
        scan={'ordinal':watch['checks_started'],'query':watch['policy']['query']+' after:'+str(int(lower))+' before:'+str(int(now)+1),
            'until':now,'page':'','next_page':'','pages':0,'messages':[],'index':0,'pending':None,'attempt':0,'retry_at':0}
        watch['scan']=scan;watch['phase']='CHECKING';save(store,watch)
    if scan['retry_at']>now:save(store,watch);return
    pending=scan['pending']
    if pending:
        job=store.get(pending['id'],True)
        if job is None:
            mailbox.submit_read(pending['request_id'],pending['operation'],pending['payload'],watch={'id':watch['id'],'revision':watch['config_revision']});return
        status=job['status']
        if status in {'READY','RUNNING'}:
            if job['id'] not in mailbox.active and status=='RUNNING':store.update(job['id'],status='WAITING',error='mail_interrupted')
            save(store,watch);return
        if status in {'WAITING_AUTH','WAITING_SCOPE'}:
            if watch['phase']!=status:watch['phase']=status;notify(watch,'authorization',now)
            save(store,watch);return
        if status!='SUCCEEDED':
            if job['effect_started'] or status=='UNKNOWN':raise CoreError('mail_uncertain','Unknown mail result needs reconciliation')
            if job.get('error') not in RETRY|{'network_disabled'}:raise CoreError(job.get('error') or 'mail_watch_job','Mailbox read did not succeed')
            if scan['attempt']+1>=watch['policy']['max_attempts']:raise CoreError('mail_watch_retry_exhausted','Read retry allowance exhausted')
            scan.update(pending=None,attempt=scan['attempt']+1,retry_at=now+60*2**scan['attempt']);watch['phase']='BACKOFF';save(store,watch);return
        if job.get('generation')!=watch['generation']:raise CoreError('mail_account_changed','Stale mailbox job')
        result=job['result'];watch['phase']='CHECKING';scan['pending']=None;scan['attempt']=0
        if pending['operation']=='read':
            ingest(root,store,watch,result,now)
            watch['seen'][identifier(result['id'])]=digest([fingerprint(result),result.get('labels',[]),store.listing('rule',100)])
            scan['index']+=1
        else:
            keys={'id','from','subject','date','snippet','thread_id','labels','source_digest'}
            scan.update(messages=[{k:v for k,v in m.items() if k in keys} for m in result['messages'][:10]],index=0,next_page=result.get('next_page',''),pages=scan['pages']+1)
        save(store,watch)
    rules=store.listing('rule',100)
    while scan['index']<len(scan['messages']):
        message=scan['messages'][scan['index']];mid=identifier(message['id']);mark=digest([message.get('source_digest',fingerprint(message)),message.get('labels',[]),rules])
        if mid not in watch['seen'] and len(watch['seen'])>=500:raise CoreError('mail_watch_capacity','Review retained mailbox scan history before expanding it')
        if watch['seen'].get(mid)!=mark and eligible(message,rules):
            queue(store,mailbox,watch,scan,'read',{'message_id':mid},now);return
        watch['seen'][mid]=mark;scan['index']+=1
    if scan['next_page']:
        if scan['pages']>=5:raise CoreError('mail_watch_partial','Scan page limit reached; narrow the search scope; no complete-coverage claim')
        scan.update(page=scan['next_page'],next_page='',messages=[],index=0)
    elif scan['pages']:
        watch.update(last_checked=scan['until'],scan=None,phase='WAITING',error=None,next_at=now+watch['policy']['interval_seconds']);save(store,watch);return
    queue(store,mailbox,watch,scan,'list',{'query':scan['query'],'page':scan['page']},now)


def advance(root,mailbox,*,foreground=False,now=None):
    if foreground or not accepting(root) or StopGate(root).state()!='ready' or not present(root):return
    now=time.time() if now is None else now
    with mailbox.lock:
        store=MailStore(root)
        try:
            # One bounded local state transition/watch and one shared mail lane.
            # No network operation is run synchronously on the dispatcher.
            for watch in rows(store):
                try:
                    tick_one(root,mailbox,store,watch,now)
                except CoreError as error:
                    if error.code in {'network_disabled','development_external_denied'}:
                        if watch['phase']!='WAITING_NETWORK':watch['phase']='WAITING_NETWORK';notify(watch,'network',now)
                    else:
                        watch.update(status='NEEDS_INPUT',phase='NEEDS_INPUT',error=error.code);notify(watch,'needs_input',now)
                    save(store,watch)
        finally:store.close()


def projection(root):
    result=[]
    for w in read(root)['items']:
        pending=w['notice_pending'] or quiet(w['policy'],time.time())
        state='needs_input' if w['status'] in {'DRAFT','NEEDS_INPUT'} or w['phase'] in {'WAITING_AUTH','WAITING_SCOPE'} else 'waiting'
        if w['status']=='CANCELLED':state='cancelled'
        elif w['notice'] and not pending and state!='needs_input':state='finished'
        reason=w['error'] or ('邮箱 '+w['phase']+' · 已检查 '+str(w['checks_started'])+' 轮 · 已关联待办 '+str(sum(bool(e.get('todo_id')) for e in w['entries'].values())))
        if state=='finished':reason={'new_mail':'重要邮件已关联待办','followup':'未结邮件待办需要跟进','feedback':'邮件待办反馈已更新','authorization':'邮箱需要重新授权','network':'邮箱等待网络恢复','needs_input':'邮件安排需要处理'}.get(w['notice']['kind'],'邮件持续办事有新反馈')
        result.append({'id':w['id'],'source':'mail_standing','title':w['title'],'state':state,'raw_status':w['phase'] if w['phase'] in {'WAITING_AUTH','WAITING_SCOPE'} else w['status'],
            'reason':reason,
            'revision':w['config_revision'],'result_revision':w['notice_revision'],'notification_held':pending,
            'cancelable':w['status']!='CANCELLED'})
    return result
