"""Attach a bounded observer to the existing dialogue finish, without veto power."""
from sdk.protocol import decode, digest
from modules.task_resource import delivery_review


def materialize(turn,result):
    """Explicit output formatting; the ordinary shadow observer stays nonmutating."""
    from modules.task_resource import body_document
    from modules.dialogue.document_format import FORMAT
    if decode(turn['request']).get('delivery_format')!=FORMAT:return result,None
    if result.get('status')!='SUCCEEDED' or (result.get('assistant_action') or {}).get('kind') not in (None,'chat'):
        return result,None
    try:
        text,receipt=body_document.materialize(decode(turn['delivery_basis']),result.get('text'))
        return {**result,'text':text},receipt
    except Exception:
        return result,{'version':body_document.VERSION,'state':'UNAVAILABLE','reason':'renderer_error',
                       'mode':'explicit_render','quality_score':None,'original_reply_digest':digest(result.get('text'))}


def observe(turn, result):
    if not turn.get('delivery_basis'):return None
    basis=None
    try:
        basis=decode(turn['delivery_basis'])
        return delivery_review.review(basis,result.get('text'),result['status'],result.get('assistant_action',{}).get('kind'))
    except Exception:
        return {'version':delivery_review.VERSION,'state':'UNAVAILABLE','reason':'observer_error','mode':'shadow',
                'basis_digest':basis.get('digest') if isinstance(basis,dict) else digest(turn['delivery_basis']),
                'basis_revision':basis.get('revision') if isinstance(basis,dict) else None,'reply_digest':digest(result.get('text')),
                'would_block':False,'quality_score':None,'checks':[]}
