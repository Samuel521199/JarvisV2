"""Independent mailbox lane; browser consent and email never block foreground chat."""
from concurrent.futures import ThreadPoolExecutor
from email.utils import parseaddr
import re
import threading
import time
import uuid

from adapters.mail.google import Gmail
from adapters.mail.oauth import authorize
from control.network import NetworkGate
from control.recovery.gate import StopGate,RunLock
from modules.mail.store import MailStore
from sdk.mail import CHANGES,LEVELS,address,capabilities,classify,client_configuration,draft,encoded_message,identifier
from sdk.protocol import CoreError,digest

WRITES={'send','remote_draft','change','undo'}
OPERATIONS={'check','list','read','analyze','send','remote_draft','change','undo','reconcile'}


def public_job(row):
    return {k:row.get(k) for k in ('id','operation','status','error','result','effect_started','cancel','created','updated')}


class Mailbox:
    def __init__(self,root,*,gmail_factory=Gmail,oauth=authorize):
        self.root=root;self.gmail_factory=gmail_factory;self.oauth=oauth
        self.lease=RunLock(root,'mail');self.lease.__enter__()
        self.lock=threading.RLock();self.closed=threading.Event();self.active=set();self.auth=None
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='jarvis-mail')
        self.auth_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='jarvis-mail-auth')
        store=MailStore(root)
        try:store.recover()
        finally:store.close()
    def close(self):
        self.closed.set();self.pool.shutdown(wait=True);self.auth_pool.shutdown(wait=True);self.lease.__exit__(None,None,None)
    def account(self):
        store=MailStore(self.root)
        try:return store.get('account',True)
        finally:store.close()
    def state(self):
        store=MailStore(self.root)
        try:
            a=store.get('account',True);client=store.get('client',True)
            return {'version':'1.0.0','provider':'gmail','configured':bool(client),'connected':bool(a and a.get('credentials')),
                    'email':a.get('email','') if a else '', 'health':a.get('health','unchecked') if a else 'disconnected',
                    'checked_at':a.get('checked_at') if a else None,'capabilities':capabilities(a.get('credentials',{}).get('scope','')) if a else capabilities(''),
                    'authorization':{k:v for k,v in (self.auth or {}).items() if k!='future'},
                    'jobs':[public_job(j) for j in store.listing('job',40)],'drafts':store.listing('draft',30),
                    'rules':store.listing('rule',100),'network_blocked':NetworkGate(self.root).read()['blocked']}
        finally:store.close()
    def guard(self,job_id=None,generation=None):
        if self.closed.is_set():raise CoreError('mail_cancelled','Mailbox service is closing')
        StopGate(self.root).require_running();NetworkGate(self.root).require_online()
        store=MailStore(self.root)
        try:
            if job_id and store.get(job_id)['cancel']:raise CoreError('mail_cancelled','Mail operation was cancelled')
            if generation:
                a=store.get('account',True)
                if not a or a.get('generation')!=generation or not a.get('credentials'):raise CoreError('mail_account_changed','Mailbox connection changed')
        finally:store.close()
    def save_account(self,store,generation,**patch):
        with self.lock,store.transaction():
            a=store.get('account')
            if a.get('generation')!=generation or not a.get('credentials'):
                raise CoreError('mail_account_changed','Connection changed; stale credentials were not restored')
            return store.put({**a,**patch},a['revision'])
    def command(self,value):
        fields={'configure':{'client'},'authorize':{'level'},'cancel_authorization':set(),'disconnect':set(),'job':{'request_id','operation','payload'},
                'detail':{'id'},'cancel':{'id'},'resume':{'id'},'draft':{'value','id','revision'},'review':{'operation','payload'},
                'approve':{'review_id','request_id'},'rule':{'sender','category'},'remove_rule':{'id','revision'}}
        if not isinstance(value,dict) or not isinstance(value.get('action'),str) or value['action'] not in fields or set(value)!={'action'}|fields[value['action']]:
            raise CoreError('mail_invalid','Unexpected mailbox command')
        action=value['action'];store=MailStore(self.root)
        try:
            if action=='configure':
                client=client_configuration(value['client'])
                with store.transaction():
                    old=store.get('client',True);store.put({'id':'client','kind':'client','configuration':client},old['revision'] if old else 0)
                return {'configured':True}
            if action=='authorize':return self.start_authorization(value['level'])
            if action=='cancel_authorization':
                if self.auth:self.auth['cancel']=True
                return {'ok':True}
            if action=='disconnect':
                with self.lock:
                    a=store.get('account',True)
                    if a:store.update('account',credentials={},health='disconnected',generation=uuid.uuid4().hex)
                    if self.auth:self.auth['cancel']=True
                return {'ok':True,'server_authorization_revoked':False}
            if action=='detail':
                row=store.get(value['id'])
                if row['kind']!='job':raise CoreError('mail_invalid','Expected a mail job')
                return public_job(row)
            if action=='cancel':
                row=store.get(value['id'])
                if row['kind']!='job':raise CoreError('mail_invalid','Expected a mail job')
                if row['status'] in {'READY','WAITING','WAITING_AUTH','WAITING_NETWORK','WAITING_SCOPE'}:store.update(row['id'],cancel=True,status='CANCELLED')
                elif row['status']=='RUNNING':store.update(row['id'],cancel=True)
                return public_job(store.get(row['id']))
            if action=='resume':
                row=store.get(value['id'])
                if row['kind']!='job' or row['status'] not in {'WAITING','WAITING_AUTH','WAITING_NETWORK','WAITING_SCOPE'} or row['cancel'] or row['effect_started']:
                    raise CoreError('mail_uncertain','Unknown writes cannot be replayed; reconcile first')
                store.update(row['id'],status='READY',error=None);self.schedule(row['id']);return public_job(store.get(row['id']))
            if action=='draft':
                data=draft(value['value']);ident=value['id'] or 'draft-'+uuid.uuid4().hex
                if not re.fullmatch(r'draft-[0-9a-f]{32}',ident) or type(value['revision']) is not int:raise CoreError('mail_invalid','Invalid local draft reference')
                with store.transaction():
                    old=store.get(ident,True)
                    if old and old['kind']!='draft':raise CoreError('mail_invalid','Expected a local draft')
                    return store.put({'id':ident,'kind':'draft','value':data},value['revision'])
            if action in {'rule','remove_rule'}:
                with store.transaction():
                    if action=='remove_rule':
                        old=store.get(value['id'])
                        if old['kind']!='rule' or old['revision']!=value['revision']:raise CoreError('conflict','Rule changed')
                        store.db.execute('DELETE FROM objects WHERE id=?',(old['id'],));return {'ok':True}
                    sender=address(value['sender']).lower()
                    if value['category'] not in {'important','normal','promotion','spam','suspicious'}:raise CoreError('mail_invalid','Unknown category')
                    ident='rule-'+digest(sender)[:32];old=store.get(ident,True)
                    return store.put({'id':ident,'kind':'rule','sender':sender,'category':value['category']},old['revision'] if old else 0)
            if action=='review':return self.review(value['operation'],value['payload'])
            if action=='approve':
                with store.transaction():
                    review=store.get(value['review_id'])
                    if review['kind']!='review' or review['expires_at']<time.time():raise CoreError('mail_review_expired','Review this exact operation again')
                    a=store.get('account',True)
                    if not a or a['generation']!=review['generation']:raise CoreError('mail_account_changed','Mailbox changed after review')
                    if review.get('job_id'):
                        return public_job(store.get(review['job_id']))
                    row,_=store.job(value['request_id'],review['operation'],review['payload'],approved=True)
                    row=store.put({**row,'generation':review['generation']},row['revision'])
                    store.put({**review,'job_id':row['id']},review['revision'])
                self.schedule(row['id']);return public_job(row)
            operation=value['operation'];payload=value['payload']
            if operation not in OPERATIONS-WRITES:raise CoreError('mail_review_required','External writes need an exact reviewed operation')
            payload=self.validate(operation,payload)
            row,fresh=store.job(value['request_id'],operation,payload)
            if fresh:
                a=store.get('account',True)
                if a:row=store.update(row['id'],generation=a['generation'])
                self.schedule(row['id'])
            return public_job(row)
        finally:store.close()

    def start_authorization(self,level):
        if not isinstance(level,str) or level not in LEVELS:raise CoreError('mail_scope','Unknown authorization level')
        self.guard();store=MailStore(self.root)
        try:
            client=store.get('client')['configuration'];previous=store.get('account',True)
        finally:store.close()
        with self.lock:
            if self.auth and self.auth['status'] in {'RUNNING','WAITING_BROWSER'}:raise CoreError('mail_busy','Google authorization is already waiting')
            op={'status':'RUNNING','level':level,'cancel':False,'error':None};self.auth=op
            self.auth_pool.submit(self._authorize,op,client,previous)
            return {'status':op['status']}

    def _authorize(self,op,client,previous):
        store=MailStore(self.root)
        try:
            def guard():
                self.guard()
                if op['cancel']:raise CoreError('mail_cancelled','Authorization was cancelled')
                current=store.get('client')['configuration']
                if current!=client:raise CoreError('mail_account_changed','OAuth configuration changed')
            def ready(url):op.update(status='WAITING_BROWSER',url=url)
            credentials=self.oauth(client,op['level'],guard,login_hint=(previous or {}).get('email',''),ready=ready)
            profile=self.gmail_factory(credentials,guard).profile();guard()
            if previous and previous.get('email') and previous['email'].lower()!=profile['email'].lower():
                raise CoreError('mail_account_changed','Google signed into another mailbox; original account was preserved')
            with self.lock,store.transaction():
                a=store.get('account',True)
                if (a or {}).get('generation')!=(previous or {}).get('generation'):raise CoreError('mail_account_changed','Mailbox changed during authorization')
                generation=(previous or {}).get('generation') or uuid.uuid4().hex
                store.put({'id':'account','kind':'account','credentials':credentials,'email':profile['email'],'generation':generation,
                           'health':'connected','checked_at':time.time()},a['revision'] if a else 0)
            op.update(status='SUCCEEDED',error=None);op.pop('url',None)
            for row in store.listing('job',100):
                if row['status']=='WAITING_AUTH' and not row['cancel'] and not row['effect_started'] and row.get('generation',generation)==generation:
                    store.update(row['id'],status='READY',error=None);self.schedule(row['id'])
        except Exception as exc:op.update(status='CANCELLED' if isinstance(exc,CoreError) and exc.code=='mail_cancelled' else 'FAILED',error=exc.code if isinstance(exc,CoreError) else 'mail_authorization_failed');op.pop('url',None)
        finally:store.close()

    def schedule(self,ident):
        with self.lock:
            if self.closed.is_set():raise CoreError('mail_cancelled','Mailbox is closing')
            if ident in self.active:return
            if len(self.active)>=20:
                store=MailStore(self.root)
                try:store.update(ident,status='WAITING',error='mail_busy')
                finally:store.close()
                raise CoreError('mail_busy','Mailbox queue is full')
            self.active.add(ident);self.pool.submit(self.run,ident)

    def run(self,ident):
        store=MailStore(self.root)
        try:
            row=store.get(ident)
            if row['status']!='READY' or row['cancel']:return
            row=store.update(ident,status='RUNNING',error=None)
            a=store.get('account',True)
            if not a or not a.get('credentials'):raise CoreError('mail_auth_required','Gmail is not connected')
            generation=a['generation']
            if row.get('generation',generation)!=generation:raise CoreError('mail_account_changed','This operation belongs to the prior connection')
            store.update(ident,generation=generation)
            guard=lambda:self.guard(ident,generation)
            guard();api=self.gmail_factory(a['credentials'],guard);credentials=api.refresh()
            if credentials!=a['credentials']:
                guard();a=self.save_account(store,generation,credentials=credentials)
            operation=row['operation'];payload=row['payload']
            def cache(m):
                key='message-'+m['id'];old=store.get(key,True)
                with store.transaction():store.put({'id':key,'kind':'message','message':m,'account_generation':generation},old['revision'] if old else 0)
                return {**m,'classification':classify(m,store.listing('rule'))}
            if operation=='check':result=api.profile()
            elif operation=='list':
                result=api.listing(payload['query'],payload['page']);result['messages']=[cache(m) for m in result['messages']]
            elif operation=='read':result=cache(api.read(payload['message_id']))
            elif operation=='analyze':
                m=api.read(payload['message_id']);cache(m)
                from host.mail_ai import analyze
                result=analyze(self.root,m,payload['instruction'],guard)
            elif operation=='reconcile':result=self.reconcile(store,api,payload['job_id'],generation)
            else:
                if not row['approved']:raise CoreError('mail_review_required','Write review is missing')
                if operation in {'send','remote_draft'}:
                    d=store.get(payload['draft_id'])
                    if d['revision']!=payload['revision'] or d['value']!=payload['value']:raise CoreError('conflict','Reviewed draft changed')
                    raw=encoded_message(payload['value'],a['email'],payload['rfc_id']);guard();store.update(ident,effect_started=True)
                    result={**api.send(raw,operation=='remote_draft'),'rfc_id':payload['rfc_id']}
                else:
                    if operation=='change':
                        message_id=payload['message_id'];change=payload['change'];remove,add=CHANGES[change]
                    else:
                        original=store.get(payload['job_id'])
                        if original.get('generation')!=generation or original['status']!='SUCCEEDED' or original['operation']!='change':raise CoreError('mail_account_changed','Original operation is unavailable')
                        message_id=original['payload']['message_id'];change='undo'
                        before=set(original['before_labels']);after=set(original['result']['message']['labels'])
                        remove=list(after-before);add=list(before-after)
                    current=api.read(message_id,False)
                    if operation=='undo' and (set(current['labels']) & (set(remove)|set(add)))!=(after & (set(remove)|set(add))):raise CoreError('conflict','Affected labels changed since the original operation')
                    guard();store.update(ident,before_labels=current['labels'],effect_started=True)
                    if operation=='undo' and original['payload']['change'] in {'trash','untrash'}:
                        m=api.trash(message_id,original['payload']['change']=='trash')
                        remaining_remove=[x for x in remove if x!='TRASH'];remaining_add=[x for x in add if x!='TRASH']
                        if remaining_remove or remaining_add:m=api.modify(message_id,remaining_remove,remaining_add)
                    else:m=api.trash(message_id,change=='untrash') if change in {'trash','untrash'} else api.modify(message_id,remove,add)
                    result={'message':cache(m),'change':change}
            guard();store.update(ident,status='SUCCEEDED',result=result,error=None)
            self.save_account(store,generation,health='connected',checked_at=time.time(),credentials=api.credentials)
        except Exception as exc:
            code=exc.code if isinstance(exc,CoreError) else 'mail_operation_failed';current=store.get(ident)
            rejected=code in {'mail_auth_required','mail_scope','mail_api_disabled','mail_rate_limit','mail_google_rejected'} and not (row['operation']=='undo' and current['effect_started'])
            if current['effect_started'] and not rejected:status='UNKNOWN'
            else:status={'mail_auth_required':'WAITING_AUTH','mail_scope':'WAITING_SCOPE','network_disabled':'WAITING_NETWORK','stopped':'WAITING','mail_cancelled':'CANCELLED'}.get(code,'FAILED')
            store.update(ident,status=status,error=code,effect_started=current['effect_started'] and not rejected)
            if code=='mail_auth_required':
                a=store.get('account',True)
                if a and a.get('credentials'):
                    try:self.save_account(store,a['generation'],health='auth_required')
                    except CoreError:pass
            elif code in {'mail_network','network_disabled'}:
                a=store.get('account',True)
                if a and a.get('credentials'):
                    try:self.save_account(store,a['generation'],health='offline')
                    except CoreError:pass
        finally:
            store.close()
            with self.lock:self.active.discard(ident)

    def reconcile(self,store,api,job_id,generation):
        original=store.get(job_id)
        if original['kind']!='job' or original['status']!='UNKNOWN' or original.get('generation')!=generation:
            raise CoreError('mail_uncertain','Only unknown operations on this mailbox can be reconciled')
        if original['operation'] in {'send','remote_draft'}:
            query=('in:sent ' if original['operation']=='send' else 'in:drafts ')+'rfc822msgid:'+original['payload']['rfc_id'].strip('<>')
            found=api.listing(query,'')['messages']
            if len(found)!=1:return {'original_job':job_id,'status':'UNKNOWN','reason':'No unique matching Google message; nothing was resent'}
            result={'message_id':found[0]['id'],'reconciled':True,'rfc_id':original['payload']['rfc_id']}
        elif original['operation']=='change':
            m=api.read(original['payload']['message_id'],False);remove,add=CHANGES[original['payload']['change']]
            if set(remove)&set(m['labels']) or not set(add)<=set(m['labels']):return {'original_job':job_id,'status':'UNKNOWN','reason':'Observed labels do not confirm the requested result'}
            result={'message':m,'change':original['payload']['change'],'reconciled_observed_state':True}
        else:raise CoreError('mail_uncertain','Manual Google inspection is required')
        store.update(job_id,status='SUCCEEDED',result=result,error=None)
        return {'original_job':job_id,'status':'SUCCEEDED','result':result}
    def validate(self,operation,payload):
        if not isinstance(payload,dict):raise CoreError('mail_invalid','Expected mail parameters')
        expected={'check':set(),'list':{'query','page'},'read':{'message_id'},'analyze':{'message_id','instruction'},
                  'send':{'draft_id','revision'},'remote_draft':{'draft_id','revision'},'change':{'message_id','change'},'undo':{'job_id'},'reconcile':{'job_id'}}
        if operation not in expected or set(payload)!=expected[operation]:raise CoreError('mail_invalid','Unexpected operation parameters')
        if 'message_id' in payload:identifier(payload['message_id'])
        if operation=='list' and any(not isinstance(v,str) or len(v)>1000 for v in payload.values()):raise CoreError('mail_invalid','Invalid search')
        if operation=='analyze' and (not isinstance(payload['instruction'],str) or len(payload['instruction'])>2000):raise CoreError('mail_invalid','Instruction is too long')
        if operation=='change' and payload['change'] not in CHANGES:raise CoreError('mail_invalid','Unknown label change')
        return payload
    def review(self,operation,payload):
        if operation not in WRITES:raise CoreError('mail_invalid','Not a reviewable operation')
        payload=self.validate(operation,payload);a=self.account()
        if not a or not a.get('credentials'):raise CoreError('mail_auth_required','Connect Gmail first')
        needed='send' if operation=='send' else 'draft' if operation=='remote_draft' else 'modify'
        if not capabilities(a['credentials'].get('scope',''))[needed]:raise CoreError('mail_scope','Grant the corresponding Google permission first')
        store=MailStore(self.root)
        try:
            resolved={**payload};summary={'operation':operation,'account':a['email']}
            if operation in {'send','remote_draft'}:
                d=store.get(payload['draft_id'])
                if d['kind']!='draft' or d['revision']!=payload['revision']:raise CoreError('conflict','Local draft changed')
                resolved={'draft_id':d['id'],'revision':d['revision'],'value':d['value'],'rfc_id':'<jarvis-'+uuid.uuid4().hex+'@local.jarvis>'};summary.update(d['value'])
            elif operation=='change':
                m=store.get('message-'+payload['message_id'])
                if m.get('account_generation')!=a['generation']:raise CoreError('mail_account_changed','Cached message belongs to an earlier connection')
                summary.update(subject=m['message']['subject'],sender=m['message']['from'],change=payload['change'])
            else:
                old=store.get(payload['job_id'])
                if old['operation']!='change' or old['status']!='SUCCEEDED':raise CoreError('mail_invalid','Only completed label changes can be undone')
                summary.update(change='undo',original_job=old['id'],original_change=old['payload']['change'],subject=old['result']['message']['subject'],sender=old['result']['message']['from'])
            ident='review-'+uuid.uuid4().hex
            with store.transaction():store.put({'id':ident,'kind':'review','operation':operation,'payload':resolved,'generation':a['generation'],'expires_at':time.time()+600,'summary':summary},0)
            return {'id':ident,'summary':summary,'expires_at':time.time()+600}
        finally:store.close()
