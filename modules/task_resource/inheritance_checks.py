"""Finite Work requirement inheritance; result correctness remains independent."""
from copy import deepcopy
from modules.task_resource import change_checks, quote_checks, quote_request, source_checks
from sdk.protocol import CoreError, digest

VERSION='quote-rework-1'
REQUIREMENT='继承已核对版本的全部有效要求，仅按明确变更修订，独立核对本次报价结果'
KEEP='保持全部要求'
# Only these clause-local unknowns can be resolved by explicit edits. All source
# uncertainty survives, including future issue codes unknown to this verifier.
RECOMPUTED={'uncovered_text','missing_budget','missing_delivery','missing_selection'}


def analyze(goal, text, parent, parent_text, link, receipt):
    current=quote_request.analyze(goal,text)
    nodes=deepcopy(parent['requirements_history']);events=deepcopy(parent['changes'])
    issues=[dict(i) for i in parent['issues'] if i['code'] not in RECOMPUTED]
    turn=link['goal_id'];note=link['note']
    old=quote_checks.parse_source(parent_text);new=quote_checks.parse_source(text)
    if {k:v for k,v in old.items() if k not in {'max_price_minor','max_delivery_days'}}!={k:v for k,v in new.items() if k not in {'max_price_minor','max_delivery_days'}}:
        issues.append({'code':'change_data_modified','blocking':True,'source':turn})
    if link['kind']=='correction':
        if note!=KEEP:issues.append({'code':'rework_correction_must_keep','blocking':True,'source':turn})
    elif link['kind']=='new_requirement':
        try:operations=change_checks.commands(note,text)
        except CoreError:
            issues.append({'code':'change_expression_unsupported','blocking':True,'source':turn});operations=[]
        changed,problems=change_checks.apply_operations(nodes,operations,text,turn,link['ordinal']-1)
        events.extend(changed);issues.extend(problems)
    else:raise CoreError('acceptance_invalid','Unknown rework kind')
    active=[n for n in nodes if n['state']=='active']
    if not active or len(nodes)>80 or len(active)>32:raise CoreError('acceptance_invalid','Rework clause history outside bounds')
    checked=quote_request.analyze('，'.join(n['text'] for n in active),text);issues.extend(checked['issues'])
    if change_checks.signature_set(current['clauses'])!=change_checks.signature_set(checked['clauses']):
        issues.append({'code':'change_goal_mismatch','blocking':True})
    sources=deepcopy(parent['sources'])
    for row in sources:
        if row['kind']=='reference' and row['status'] in {'input_identical','historical_input_identical'}:
            row['status']='input_identical' if row['text']==text else 'historical_input_identical'
    sources.append({'id':turn+':text','kind':'user','name':'返工要求','text':note,'status':'inherited' if note==KEEP else 'change_replayed'})
    versions=deepcopy(parent.get('rework_versions',[]))+[{'goal_id':turn,'parent_goal':link['parent_goal'],'ordinal':link['ordinal'],'kind':link['kind'],'note':note,'active_count':len(active)}]
    binding=digest({'verifier':VERSION,'request':current['binding'],'receipt':receipt,'parent':parent['binding'],'nodes':nodes,'events':events})
    return {**current,'version':VERSION,'binding':binding,'request_binding':current['binding'],'source_scope':'explicit_work_inheritance',
            'sources':sources,'source_count':len(sources),'clauses':checked['clauses'],'requirements_history':nodes,'changes':events,
            'rework_versions':versions,'issues':issues,'blocking':any(i['blocking'] for i in issues),'ready':not issues,'active_count':len(active)}


def acceptance(review,step_id):
    return {'coverage':'recipe','criteria':[{'id':'quote-rework','step_id':step_id,'check':'quote_rework','expected':review['binding']}],
            'requirements':[{'id':'rework-domain','text':REQUIREMENT,'kind':'quote_rework','criterion_ids':['quote-rework']}]}


def verify(body,rule,text,review):
    try:source_checks.validate(body,rule,review)
    except CoreError:return {'status':'invalid','reason':'quote_rework_changed','rework_verifier':VERSION,'rework_binding':rule['expected']}
    checked=quote_request.verify(body,{**rule,'expected':review['request_binding']},text)
    checked.update(rework_verifier=VERSION,rework_binding=review['binding'],source_scope=review['source_scope'],
                   source_count=review['source_count'],rework_count=len(review['rework_versions']),active_count=review['active_count'],unresolved_count=len(review['issues']))
    if checked['status'] in {'passed','unknown'} and not review['ready']:checked.update(status='unknown',reason='quote_rework_unresolved')
    return checked
