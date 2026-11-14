"""Source-bound conditional advice. A matching card never grants execution or truth."""
import hashlib
import math
import re
import time
from sdk.protocol import CoreError,canonical,decode,digest

SCHEMA='jarvis.method-card.v1'
VERSION='conditional-advice-1'
FIELDS={'schema','id','revision','status','recipe','requires','summary','counterexamples','evidence','expires'}


def text_digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()


def context(value,*,rule=False):
    if (not isinstance(value,dict) or len(value)>20
        or any(not isinstance(k,str) or not re.fullmatch('[a-z][a-z0-9_]{0,39}',k) for k in value)):
        raise CoreError('method_invalid','Invalid applicability context')
    for item in value.values():
        if item is None and not rule:continue
        if type(item) not in (str,int,bool):raise CoreError('method_invalid','Use scalar known applicability values')
        if isinstance(item,str) and (not 1<=len(item)<=120 or any(ord(c)<32 for c in item)):
            raise CoreError('method_invalid','Invalid applicability text')
        if type(item) is int and not -(2**53)<item<2**53:raise CoreError('method_invalid','Invalid applicability number')
    return value


def parse(text):
    if len(text.encode('utf-8'))>6000:raise CoreError('method_invalid','Method card exceeds its bound')
    value=decode(text)
    if not isinstance(value,dict) or set(value)!=FIELDS or value['schema']!=SCHEMA:
        raise CoreError('method_invalid','Invalid method card fields')
    if (not isinstance(value['id'],str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}',value['id'])
        or type(value['revision']) is not int or value['revision']<1
        or value['status'] not in ('CANDIDATE','QUARANTINED')
        or not isinstance(value['recipe'],str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}',value['recipe'])):
        raise CoreError('method_invalid','Invalid method identity or status')
    context(value['requires'],rule=True)
    if not value['requires']:raise CoreError('method_invalid','A method needs explicit applicability')
    if not isinstance(value['summary'],str) or not 1<=len(value['summary'].strip())<=1600:
        raise CoreError('method_invalid','Invalid method summary')
    examples=value['counterexamples']
    if not isinstance(examples,list) or not 1<=len(examples)<=8 or any(not isinstance(s,str) or not 1<=len(s.strip())<=400 for s in examples):
        raise CoreError('method_invalid','Retain bounded counterexamples')
    expiry=value['expires']
    if type(expiry) not in (int,float) or not math.isfinite(expiry) or not 0<expiry<4102444800:
        raise CoreError('method_invalid','Invalid method expiry')
    refs=value['evidence'];seen=set()
    if not isinstance(refs,list) or not 1<=len(refs)<=8:raise CoreError('method_invalid','Method evidence bound')
    for ref in refs:
        if (not isinstance(ref,dict) or set(ref)!={'source_id','revision','sha256'}
            or not isinstance(ref['source_id'],str) or not re.fullmatch('source-[a-f0-9]{32}',ref['source_id'])
            or ref['source_id'] in seen or type(ref['revision']) is not int or ref['revision']<1
            or not isinstance(ref['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',ref['sha256'])):
            raise CoreError('method_invalid','Invalid or duplicate evidence reference')
        seen.add(ref['source_id'])
    return value


def select(sources,selectors,resolve,*,limit=4,max_bytes=5000,now=None):
    """resolve returns only currently authorized sources, or None; no authority widening.

    Caller-declared selectors are a filter, not verified task facts. Repeated
    citations share a lineage group and never become independent support votes.
    """
    context(selectors)
    if type(limit) is not int or not 1<=limit<=6 or type(max_bytes) is not int or not 512<=max_bytes<=5000:
        raise CoreError('method_invalid','Invalid method retrieval budget')
    if not isinstance(sources,list) or len(sources)>12:raise CoreError('method_invalid','Method candidate bound')
    current=time.time() if now is None else now;accepted=[];rejected=[];seen=set();used=0;groups={};copies={}
    for source in sources:
        ident=source['id']
        if ident in seen:continue
        seen.add(ident)
        try:card=parse(source['text'])
        except CoreError:
            rejected.append({'source_id':ident,'reason':'not_a_valid_method_card'});continue
        reason=None
        if card['status']!='CANDIDATE':reason='quarantined'
        elif card['expires']<=current:reason='expired'
        else:
            unknown=[k for k in card['requires'] if selectors.get(k) is None]
            different=[k for k,v in card['requires'].items() if k not in unknown and (type(selectors[k]) is not type(v) or selectors[k]!=v)]
            if unknown:reason='unknown_precondition'
            elif different:reason='precondition_mismatch'
        evidence=[]
        if reason is None:
            for ref in card['evidence']:
                row=resolve(ref['source_id']) if ref['source_id']!=ident else None
                if not row or row['revision']!=ref['revision'] or text_digest(row['text'])!=ref['sha256']:
                    reason='evidence_changed_missing_or_disallowed';break
                # Method cards cannot corroborate one another or form a cycle.
                try:is_method=isinstance((body:=decode(row['text'])),dict) and isinstance(body.get('schema'),str) and body['schema'].startswith('jarvis.method-card.')
                except CoreError:is_method=False
                if is_method:reason='method_as_evidence';break
                evidence.append(ref)
        if reason:
            rejected.append({'source_id':ident,'id':card['id'],'reason':reason});continue
        lineage=digest(sorted(evidence,key=lambda r:r['source_id']))
        equivalence=digest({k:card[k] for k in ('recipe','requires','summary','counterexamples','evidence','expires')})
        if equivalence in copies:
            rejected.append({'source_id':ident,'id':card['id'],'reason':'duplicate_method_same_evidence','duplicate_of_source':copies[equivalence]});continue
        result={k:card[k] for k in ('id','revision','recipe','requires','summary','counterexamples','expires')}
        result.update(source_id=ident,source_revision=source['revision'],source_digest=text_digest(source['text']),
            evidence=evidence,lineage_group=lineage,advisory_only=True,verified=False,execution_authorized=False)
        size=len(canonical(result).encode('utf-8'))
        if len(accepted)>=limit or used+size>max_bytes:
            rejected.append({'source_id':ident,'id':card['id'],'reason':'context_budget'});continue
        accepted.append(result);used+=size;groups.setdefault(lineage,[]).append(ident);copies[equivalence]=ident
    receipt={'version':VERSION,'context_digest':digest(selectors),'methods':[
        {'source_id':m['source_id'],'source_revision':m['source_revision'],'source_digest':m['source_digest'],'method_digest':digest(m)} for m in accepted]}
    return {'version':VERSION,'methods':accepted,'rejected':rejected,'bytes':used,'receipt':receipt,
        'context_digest':digest(selectors),'lineage_groups':len(groups),'independent_successes':None,
        'execution_authorized':False,'automatic_promotion':False,'context_authority':'caller_declared_advice_only'}
