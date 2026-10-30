"""Small, account-bound mailbox projection. Reading it never contacts Google or an LLM."""
import time

from sdk.mail import capabilities,classify


def project(account,configured,jobs,rules,messages,authorization,network_blocked,*,now=None):
    now=time.time() if now is None else now
    account=account or {};generation=account.get('generation')
    candidates=[j for j in jobs if generation and j.get('generation')==generation
                and j.get('status')=='SUCCEEDED' and j.get('operation') in {'list','sync'}
                and j.get('result') is not None and j.get('payload',{}).get('query','in:inbox')=='in:inbox'
                and not j.get('payload',{}).get('page')]
    latest=max(candidates,key=lambda j:j.get('updated',0),default=None)
    source=(latest or {}).get('result') or {};cached={m['message']['id']:m['message'] for m in messages
        if m.get('account_generation')==generation and isinstance(m.get('message'),dict)}
    rows=[]
    for original in source.get('messages',[])[:10]:
        mail=cached.get(original['id'],original)
        if 'INBOX' not in mail.get('labels',[]):continue
        classification=classify(mail,rules)
        rows.append({k:mail.get(k,'') for k in ('id','thread_id','from','subject','date','snippet')}
                    | {'unread':'UNREAD' in mail.get('labels',[]),'classification':classification})
    counts=source.get('counts') if latest and latest['operation']=='sync' else None
    unread=counts.get('messagesUnread') if isinstance(counts,dict) else None
    if type(unread) is not int or unread<0:unread=None
    checked=account.get('checked_at') or 0
    status=('offline' if network_blocked or account.get('health')=='offline' else
            'auth_required' if account.get('health')=='auth_required' else
            'disconnected' if not account.get('credentials') else
            'connected' if account.get('health')=='connected' and now-checked<300 else 'unchecked')
    return {'version':'1.0.0','status':status,'configured':bool(configured),'email':account.get('email',''),
            'account_generation':generation or '', 'checked_at':checked or None,
            'capabilities':capabilities(account.get('credentials',{}).get('scope','')),
            'authorization':{k:authorization.get(k) for k in ('status','error') if k in authorization},
            'items':rows,'unread_count':unread,'sample_unread_count':sum(m['unread'] for m in rows),
            'attention_count':sum(m['unread'] and m['classification']['category'] in {'important','suspicious'} for m in rows),
            'snapshot_at':latest.get('updated') if latest else None,'has_more':bool(source.get('next_page')),
            'count_scope':'inbox_messages' if unread is not None else 'cached_sample',
            'network_blocked':bool(network_blocked),'remote_calls_on_projection':0,'model_calls_on_projection':0}
