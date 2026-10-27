"""Typed applicability. An unknown context never satisfies a condition."""
import math
import re
import time
from sdk.protocol import CoreError, canonical, decode

KEYS={'channel','activity','language','audience'}


def validate(value):
    if not isinstance(value,dict) or set(value)!={'valid_from','conditions'}:
        raise CoreError('memory_invalid','Invalid applicability')
    start=value['valid_from'];conditions=value['conditions']
    if start is not None and (type(start) not in (int,float) or not math.isfinite(start) or not 0<start<4102444800):
        raise CoreError('memory_invalid','Invalid effective time')
    context(conditions)
    return value


def context(value):
    if not isinstance(value,dict) or not set(value)<=KEYS or any(not isinstance(v,str) or not re.fullmatch(r'[\w .:-]{1,80}',v) for v in value.values()):
        raise CoreError('memory_invalid','Invalid context selectors')
    if 'channel' in value and value['channel'] not in {'chat','task','preview'}:
        raise CoreError('memory_invalid','Invalid channel')
    return value


def get(db,ident):
    row=db.one('SELECT valid_from,conditions FROM memory_conditions WHERE fact_id=?',(ident,))
    return {'valid_from':row['valid_from'],'conditions':decode(row['conditions'])} if row else {'valid_from':None,'conditions':{}}


def save(tx,ident,value):
    validate(value)
    tx.execute('INSERT INTO memory_conditions VALUES(?,?,?) ON CONFLICT(fact_id) DO UPDATE SET valid_from=excluded.valid_from,conditions=excluded.conditions',
               (ident,value['valid_from'],canonical(value['conditions'])))


def matches(rule,selectors=None,now=None):
    selectors=context(selectors or {})
    return ((rule['valid_from'] is None or rule['valid_from']<=(time.time() if now is None else now))
            and all(selectors.get(k)==v for k,v in rule['conditions'].items()))
