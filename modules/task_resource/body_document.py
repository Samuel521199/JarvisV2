"""Opt-in deterministic document rendering from checked user-declared excerpts."""
from sdk.protocol import CoreError,canonical,decode,digest
from modules.task_resource import body_evidence

VERSION='body-document-1'


def materialize(basis,reply):
    receipt={'version':VERSION,'basis_digest':basis['digest'],'basis_revision':basis['revision'],
        'original_reply_digest':digest(reply),'quality_score':None,'mode':'explicit_render'}
    if not basis['entries'] or not isinstance(reply,str) or len(reply)>30000:
        return reply,{**receipt,'state':'DECLINED','reason':'missing_basis_or_reply_bound'}
    try:
        raw=reply.strip()
        if raw.startswith('```json') and raw.endswith('```'):raw=raw[7:-3].strip()
        value=decode(raw)
        if not isinstance(value,dict) or not isinstance(value.get('document'),str):raise ValueError('document shape')
        reference={'sources':{x['id']:x['quote'] for x in basis['entries']},
            **{k:[x['id'] for x in basis['entries'] if x['kind']==k] for k in ('facts','plans')}}
        body_evidence.validate(reference)
        checks=body_evidence.assess(reference,value)
        content=[c for c in checks if c['id']!='body_document_parity']
        if not content or any(c['status']!='passed' for c in content):
            return reply,{**receipt,'state':'DECLINED','reason':'source_or_scope_mismatch','checks':checks}
        document=body_evidence.render(value['evidence'])
        changed=value['document']!=document
        if changed:
            value['document']=document;rendered=canonical(value)
            if len(rendered)>30000:return reply,{**receipt,'state':'DECLINED','reason':'rendered_reply_bound'}
            reply=rendered
        return reply,{**receipt,'state':'RENDERED' if changed else 'UNCHANGED',
            'reason':'current_source_structure_only','original_checks':checks,
            'reply_digest':digest(reply),'document_digest':digest(document),'model_calls':0}
    except (CoreError,ValueError,KeyError,TypeError,RecursionError):
        return reply,{**receipt,'state':'DECLINED','reason':'invalid_structured_reply'}
