"""Bounded source reconciliation policy; source access is supplied by Host."""
from modules.task_resource import quote_request
from sdk.protocol import CoreError, digest

VERSION='quote-sources-1'
REQUIREMENT='对账已关联聊天原话、会话要求与参考资料范围，再核验当前目标的报价结果'


def signature(clause):
    return (clause['kind'],clause.get('value')) if clause['kind']!='uncovered' else ('uncovered',clause['text'])


def analyze(goal, text, parts, receipt, context_issues, scope):
    if len(parts)>16 or sum(len(p['text']) for p in parts)>32000:
        raise CoreError('acceptance_invalid','Source review window exceeded; sources must not be silently truncated')
    review=quote_request.analyze(goal,text)
    issues=[*review['issues'],*context_issues];source_rows=[]
    target={signature(c) for c in review['clauses']}
    for part in parts:
        row={**part,'status':'unreviewed','clauses':[]}
        if part['kind']=='reference':
            if part['text']==text:row['status']='input_identical'
            else:issues.append({'code':'reference_unreviewed','blocking':False,'source':part['id']})
        else:
            try:original=quote_request.analyze(part['text'],text)
            except CoreError:
                issues.append({'code':'source_text_outside_bounds','blocking':True,'source':part['id']})
            else:
                row['clauses']=original['clauses'];row['status']='compared'
                for item in original['issues']:
                    if not item['code'].startswith('missing_'):
                        issues.append({**item,'code':'source_'+item['code'],'source':part['id']})
                for clause in original['clauses']:
                    if clause['kind'] not in {'intro','courtesy'} and signature(clause) not in target:
                        issues.append({'code':'source_clause_missing','blocking':False,'source':part['id'],
                                       'span':[clause['start'],clause['end']]})
        source_rows.append(row)
    binding=digest({'verifier':VERSION,'request':review['binding'],'receipt':receipt,'scope':scope})
    return {**review,'version':VERSION,'binding':binding,'request_binding':review['binding'],
            'source_scope':scope,'sources':source_rows,'source_count':len(source_rows),'issues':issues,
            'blocking':any(i['blocking'] for i in issues),'ready':not issues}


def acceptance(review, step_id):
    return {'coverage':'recipe','criteria':[{'id':'quote-sources','step_id':step_id,'check':'quote_sources','expected':review['binding']}],
            'requirements':[{'id':'source-domain','text':REQUIREMENT,'kind':'quote_sources','criterion_ids':['quote-sources']}]}


def validate(body, rule, review):
    if not review or review['binding']!=rule['expected'] or review['blocking']:
        raise CoreError('acceptance_invalid','Source review unavailable, changed, or conflicting')
    quote_request.bound_review(body,{**rule,'expected':review['request_binding']})


def verify(body, rule, text, review):
    try:validate(body,rule,review)
    except CoreError:return {'status':'invalid','reason':'quote_sources_changed','source_verifier':VERSION,'source_binding':rule['expected']}
    checked=quote_request.verify(body,{**rule,'expected':review['request_binding']},text)
    checked.update(source_verifier=VERSION,source_binding=review['binding'],source_scope=review['source_scope'],
                   source_count=review['source_count'],unresolved_count=len(review['issues']))
    if checked['status'] in {'passed','unknown'} and not review['ready']:
        checked.update(status='unknown',reason='quote_sources_unresolved')
    return checked
