"""Attach a bounded observer to the existing dialogue finish, without veto power."""
from sdk.protocol import decode, digest
from modules.task_resource import delivery_review


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
