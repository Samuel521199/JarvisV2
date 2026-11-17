"""Account-bound display choices and metadata-only filing rules; no remote authority."""
import re,uuid
from sdk.protocol import CoreError


def preferences(store,generation):
    old=store.get('mail-view',True)
    return {'revision':old['revision'] if old else 0,'mark_read_on_open':bool(old and old.get('generation')==generation and old.get('mark_read_on_open'))}


def save_preferences(store,body,generation):
    if type(body['revision']) is not int or type(body['mark_read_on_open']) is not bool:raise CoreError('mail_invalid','Invalid reading preference')
    with store.transaction():
        store.put({'id':'mail-view','kind':'mail_view','generation':generation,'mark_read_on_open':body['mark_read_on_open']},body['revision'])
    return preferences(store,generation)


def rules(store,generation):
    return store.listing('rule',100)+[r for r in store.listing('folder_rule',100) if r.get('generation')==generation]


def save_rule(store,body,generation):
    if (body['field'] not in {'subject','sender','domain'} or not isinstance(body['pattern'],str)
            or not 1<=len(body['pattern'].strip())<=160 or not isinstance(body['folder'],str) or not 1<=len(body['folder'].strip())<=40
            or type(body['priority']) is not int or not 0<=body['priority']<=100 or type(body['enabled']) is not bool):
        raise CoreError('mail_invalid','Invalid local folder rule')
    ident=body['id'] or 'folder-'+uuid.uuid4().hex
    if not re.fullmatch('folder-[a-f0-9]{32}',ident) or type(body['revision']) is not int:raise CoreError('mail_invalid','Invalid folder rule revision')
    with store.transaction():
        old=store.get(ident,True)
        if old and (old['kind']!='folder_rule' or old.get('generation')!=generation):raise CoreError('mail_account_changed','Rule belongs to another mailbox')
        return store.put({'id':ident,'kind':'folder_rule','generation':generation,**{k:body[k] for k in ('field','pattern','folder','priority','enabled')}},body['revision'])
