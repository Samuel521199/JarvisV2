"""Explicit per-chat user declarations, never inferred facts or execution grants."""
from sdk.protocol import CoreError, digest
from datetime import datetime,timezone


def update(value, text, turn_id, current, source_created=None):
    if (not isinstance(value,dict) or set(value)!={'expected_revision','facts','plans'}
            or type(value['expected_revision']) is not int or value['expected_revision']<0):
        raise CoreError('delivery_basis_invalid','Expected current revision and explicit facts/plans')
    if value['expected_revision']!=current['revision']:
        raise CoreError('delivery_basis_conflict','Delivery basis changed; review the current version before resending')
    entries=[];seen=set()
    for kind,prefix in [('facts','F'),('plans','P')]:
        values=value[kind]
        if not isinstance(values,list) or len(values)>15:raise CoreError('delivery_basis_invalid','At most fifteen lines in each group')
        for index,quote in enumerate(values,1):
            if (not isinstance(quote,str) or not quote.strip() or quote!=quote.strip() or len(quote)>1200
                    or any(c in quote for c in '\r\n\x00') or quote in seen or quote not in text):
                raise CoreError('delivery_basis_invalid','Each unique source line must appear verbatim in this user message')
            seen.add(quote);start=text.index(quote)
            entries.append({'id':prefix+str(index),'kind':kind,'quote':quote,'source_turn':turn_id,'start':start,'end':start+len(quote)})
    result={'revision':current['revision']+1,'entries':entries,'source_turn':turn_id,
            'source_time_utc':datetime.fromtimestamp(source_created,timezone.utc).isoformat() if source_created is not None else None,
            'relative_time_resolution':'UNVERIFIED'}
    if sum(len(x['quote']) for x in entries)>6000:raise CoreError('delivery_basis_invalid','Delivery basis exceeds the bounded text allowance')
    return {**result,'digest':digest(result)}


def empty():
    value={'revision':0,'entries':[],'source_turn':None}
    return {**value,'digest':digest(value)}
