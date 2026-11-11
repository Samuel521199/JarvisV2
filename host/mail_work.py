"""Owner-selected cached mail -> common commitments. No remote effects or LLM.

Mail identity/digest remain DPAPI encrypted in MailStore. Common commitments
contain an owner-entered title and opaque references, never copied mail bodies.
"""
import re
from control.application_runtime import require_accepting
from control.recovery.gate import StopGate
from modules.mail.store import MailStore
from modules.mail.provenance import fingerprint
from modules.task_resource.commitments import Commitments
from host import commitments
from sdk.mail import identifier
from sdk.protocol import CoreError,digest


def cached(store,generation,message_id):
    account=store.get('account',True)
    if not account or not account.get('credentials') or account.get('generation')!=generation:
        raise CoreError('mail_account_changed','Mailbox connection changed; cached source not disclosed')
    row=store.get('message-'+identifier(message_id),True)
    if not row or row.get('kind')!='message' or row.get('account_generation')!=generation:
        raise CoreError('mail_source_missing','Read the current mail into its encrypted cache first')
    return row['message']


def inspect(root,body):
    generation=identifier(body['account_generation']);message_id=identifier(body['message_id'])
    store=MailStore(root)
    try:
        message=cached(store,generation,message_id)
        family=digest(['gmail',generation,message_id])
        rows=[]
        if commitments.exists(root):
            with Commitments(root) as tasks:rows=tasks.mail_items(family)
        return {'account_generation':generation,'message_id':message_id,'source_digest':fingerprint(message),
                'items':rows,'remote_calls':0,'model_calls':0}
    finally:store.close()


def create(root,body,runner=None,*,authorization_note=None):
    require_accepting(root);StopGate(root).require_running()
    generation=identifier(body['account_generation']);message_id=identifier(body['message_id'])
    request=body['request_id'];signature=body['source_digest']
    if not isinstance(request,str) or not re.fullmatch('[a-f0-9]{32}',request):raise CoreError('mail_invalid','Invalid request ID')
    if not isinstance(signature,str) or not re.fullmatch('[a-f0-9]{64}',signature):raise CoreError('mail_invalid','Invalid cached-source fingerprint')
    family=digest(['gmail',generation,message_id]);reference=digest([family,signature]);record_id=digest(['mail-work',request])[:32]
    command={'action':'create','id':record_id,'request_id':request,'title':body['title'],'due_at':body['due_at'],
             'source':authorization_note or '主人从邮件中明确建立的个人待办；邮件正文不是执行授权。'}
    origin={'mail_reference':reference,'mail_family':family};store=MailStore(root)
    try:
        # A committed replay returns the original record even after disconnect,
        # with no old mail disclosure and no terminal record resurrection.
        if commitments.exists(root):
            with Commitments(root) as tasks:previous=tasks.operation(request)
            if previous:return commitments.command(root,command,runner,origin=origin)
        message=cached(store,generation,message_id)
        if fingerprint(message)!=signature:raise CoreError('mail_source_changed','Cached mail changed; inspect again before creating a task')
        source={'id':'mail-work-'+reference,'kind':'commitment_source','account_generation':generation,
                'message_id':message_id,'source_digest':signature,'family':family}
        # Immutable source first. A crash here leaves only an encrypted orphan;
        # no work appears until the common transaction commits. Replays recover
        # the same source and command, never a second task.
        with store.transaction():
            old=store.get(source['id'],True)
            if old:
                if any(old.get(key)!=value for key,value in source.items()):raise CoreError('conflict','Source identity changed')
            else:store.put(source,0)
        return commitments.command(root,command,runner,origin=origin)
    finally:store.close()


def source(root,ident):
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise CoreError('mail_invalid','Invalid commitment ID')
    with Commitments(root) as tasks:reference=tasks.mail_source(ident);task=tasks.read(ident)
    if not reference:raise CoreError('mail_source_missing','This task has no mail source')
    result={'task':task,'source_status':'missing','message':None,'effects':[],'remote_calls':0,'model_calls':0}
    store=MailStore(root)
    try:
        origin=store.get('mail-work-'+reference['reference'],True)
        if not origin:return result
        try:message=cached(store,origin['account_generation'],origin['message_id'])
        except CoreError as error:
            result['source_status']='disconnected' if error.code=='mail_account_changed' else 'missing';return result
        if fingerprint(message)!=origin['source_digest']:
            result['source_status']='changed';return result
        result.update(source_status='available',message=message,account_generation=origin['account_generation'])
        links=store.get('mail-work-reviews-'+ident,True)
        for review_id in (links or {}).get('reviews',[])[:16]:
            review=store.get(review_id,True)
            if not review or review.get('generation')!=origin['account_generation'] or not review.get('job_id'):continue
            job=store.get(review['job_id'],True)
            if job:result['effects'].append({k:job.get(k) for k in ('id','operation','status','error','effect_started')})
        return result
    finally:store.close()


def command(root,mailbox,body,runner=None):
    fields={'inspect':{'account_generation','message_id'},'create':{'account_generation','message_id','source_digest','title','due_at','request_id'},'source':{'id'},'review_reply':{'id','operation','payload'}}
    if not isinstance(body,dict) or not isinstance(body.get('action'),str) or body['action'] not in fields or set(body)!={'action'}|fields[body['action']]:
        raise CoreError('mail_invalid','Unexpected mail-work command')
    with mailbox.lock:
        if body['action']=='inspect':return inspect(root,body)
        if body['action']=='source':return source(root,body['id'])
        if body['action']=='review_reply':
            require_accepting(root);StopGate(root).require_running()
            current=source(root,body['id'])
            if current['source_status']!='available':raise CoreError('mail_source_changed','Recheck the original account and current cached source')
            if body['operation'] not in ('send','remote_draft'):raise CoreError('mail_invalid','Expected an explicit reply review')
            review=mailbox.review(body['operation'],body['payload']);store=MailStore(root)
            try:
                with store.transaction():
                    ident='mail-work-reviews-'+body['id'];old=store.get(ident,True)
                    store.put({'id':ident,'kind':'commitment_effects','reviews':([review['id']]+(old or {}).get('reviews',[]))[:16]},old['revision'] if old else 0)
            finally:store.close()
            return review
        return create(root,body,runner)
