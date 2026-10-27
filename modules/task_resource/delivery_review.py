"""Nonblocking delivery observations; literal absence is not a semantic verdict."""
import json
from sdk.protocol import digest
from modules.task_resource import body_evidence

VERSION='delivery-shadow-1'


def review(basis, reply, status, action=None):
    result={'version':VERSION,'basis_digest':basis['digest'],'basis_revision':basis['revision'],
            'reply_digest':digest(reply),'mode':'shadow','would_block':False,'quality_score':None,'checks':[]}
    if status!='SUCCEEDED' or action not in (None,'chat'):
        return {**result,'state':'NOT_APPLICABLE','reason':'response_not_delivered_as_chat'}
    if not basis['entries']:return {**result,'state':'NO_BASIS','reason':'no_explicit_user_basis'}
    if not isinstance(reply,str) or len(reply)>100000:
        return {**result,'state':'UNAVAILABLE','reason':'reply_outside_review_bound'}
    value=None
    try:
        raw=reply.strip()
        if raw.startswith('```json') and raw.endswith('```'):raw=raw[7:-3].strip()
        def pairs(items):
            out={}
            for k,v in items:
                if k in out:raise ValueError('duplicate key')
                out[k]=v
            return out
        def invalid(_):raise ValueError('non-finite value')
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    except (ValueError,RecursionError):pass
    if isinstance(value,dict) and 'evidence' in value:
        ref={'sources':{x['id']:x['quote'] for x in basis['entries']},
             **{k:[x['id'] for x in basis['entries'] if x['kind']==k] for k in ('facts','plans')}}
        checks=body_evidence.assess(ref,value)
        return {**result,'state':'EXCERPT_MATCH' if all(c['status']=='passed' for c in checks) else 'REVIEW',
                'method':'source_excerpt','checks':checks,'reason':'bounded_document_check_only'}
    text=value.get('document') if isinstance(value,dict) and isinstance(value.get('document'),str) else reply
    checks=[{'id':x['id'],'kind':x['kind'],'status':'literal_found' if x['quote'] in text else 'literal_not_found'} for x in basis['entries']]
    return {**result,'state':'REVIEW' if any(c['status']=='literal_not_found' for c in checks) else 'PROSE_UNVERIFIED',
            'method':'literal_presence','checks':checks,'reason':'missing_quote_may_be_paraphrase_or_omission; additions_and_semantics_unverified'}
