"""Replay explicit user clause edits; never infer that a later sentence wins."""
from collections import Counter
import re
from modules.task_resource import quote_request, quote_checks, source_checks
from sdk.protocol import CoreError, digest

VERSION='quote-changes-1'
REQUIREMENT='按已接受原话的明确新增、替换和撤销重放要求，核对当前目标、输入与报价结果'
COMMAND=re.compile(r'(?:新增要求「([^「」\r\n]+)」|撤销要求「([^「」\r\n]+)」|将要求「([^「」\r\n]+)」替换为「([^「」\r\n]+)」)')


def commands(text, input_text):
    if not isinstance(text,str) or not 1<=len(text)<=2000:raise CoreError('acceptance_invalid','Change text outside bounds')
    result=[];pos=0
    while pos<len(text):
        while pos<len(text) and text[pos].isspace():pos+=1
        if pos==len(text):break
        m=COMMAND.match(text,pos)
        if not m:raise CoreError('acceptance_invalid','Explicit quoted change required')
        old=m[2] or m[3];new=m[1] or m[4]
        for value in (old,new):
            if value is None:continue
            parsed=quote_request.analyze(value,input_text)['clauses']
            if (value!=value.strip() or len(parsed)!=1 or parsed[0]['text']!=value
                    or parsed[0]['kind'] in {'intro','courtesy'}):
                raise CoreError('acceptance_invalid','Each quoted target must be one substantive clause')
        result.append({'operation':'add' if m[1] else 'remove' if m[2] else 'replace','old':old,'new':new,'span':[pos,m.end()]})
        if len(result)>8:raise CoreError('acceptance_invalid','Too many changes in one turn')
        pos=m.end()
        while pos<len(text) and text[pos] in ' \t':pos+=1
        if pos<len(text):
            if text[pos] not in '；;\r\n':raise CoreError('acceptance_invalid','Unparsed text after change')
            pos+=1
    if not result:raise CoreError('acceptance_invalid','No explicit changes')
    return result


def signature_set(clauses):
    return Counter(source_checks.signature(c) for c in clauses if c['kind'] not in {'intro','courtesy'})


def apply_operations(nodes, operations, text, turn, generation):
    """Apply already parsed exact edits; caller owns bounds and transaction validity."""
    events=[];issues=[]
    def active():return [n for n in nodes if n['state']=='active']
    for number,op in enumerate(operations):
        found=[n for n in active() if n['text']==op['old']]
        if op['operation']!='add' and len(found)!=1:
            issues.append({'code':'change_target_ambiguous' if found else 'change_target_missing','blocking':True,'source':turn});continue
        if op['new'] and any(n['text']==op['new'] for n in active()):
            issues.append({'code':'change_duplicate','blocking':True,'source':turn});continue
        old=found[0] if found else None;new=None
        if old:old.update(state='withdrawn' if op['operation']=='remove' else 'replaced',changed_by=turn)
        if op['new']:
            clause=quote_request.analyze(op['new'],text)['clauses'][0]
            new={**clause,'id':turn+':change:'+str(number),'source':turn+':text','state':'active'};nodes.append(new)
        events.append({**op,'source':turn,'generation':generation,'old_id':old['id'] if old else None,'new_id':new['id'] if new else None})
    return events,issues


def analyze(goal, text, stages, parts, receipt, issues):
    if not 1<=len(stages)<=4 or len(parts)>16 or sum(len(p['text']) for p in parts)>32000:
        raise CoreError('acceptance_invalid','Bounded change window exceeded')
    current=quote_request.analyze(goal,text);issues=list(issues);nodes=[];events=[];source_rows=[]
    original=quote_checks.parse_source(stages[0]['input_text'])
    base_session=stages[0]['request'].get('requirements','')
    def add_clause(clause,source,ident):
        node={**clause,'id':ident,'source':source,'state':'active'};nodes.append(node);return node
    def active():return [n for n in nodes if n['state']=='active']
    for index,stage in enumerate(stages):
        turn=stage['turn_id'];request=stage['request']
        stage_input=quote_checks.parse_source(stage['input_text'])
        if {k:v for k,v in stage_input.items() if k not in {'max_price_minor','max_delivery_days'}}!={k:v for k,v in original.items() if k not in {'max_price_minor','max_delivery_days'}}:
            issues.append({'code':'change_data_modified','blocking':True,'source':turn})
        if index==0:
            for kind,value in [('text',request['text']),('requirements',base_session)]:
                if not value.strip():continue
                for clause in quote_request.analyze(value,stage['input_text'])['clauses']:
                    if clause['kind'] not in {'intro','courtesy'}:add_clause(clause,turn+':'+kind,turn+':'+kind+':'+str(clause['start']))
        else:
            if request.get('requirements','') and request['requirements']!=base_session:
                issues.append({'code':'change_session_unreviewed','blocking':True,'source':turn})
            try:operations=commands(request['text'],text)
            except CoreError:
                issues.append({'code':'change_expression_unsupported','blocking':True,'source':turn});operations=[]
            changed,problems=apply_operations(nodes,operations,text,turn,index)
            events.extend(changed);issues.extend(problems)
        if len(nodes)>56 or len(active())>32:raise CoreError('acceptance_invalid','Clause history bound exceeded')
    effective='，'.join(n['text'] for n in active())
    if not effective:raise CoreError('acceptance_invalid','Changes removed every requirement')
    checked=quote_request.analyze(effective,text);issues.extend(checked['issues'])
    if signature_set(current['clauses'])!=signature_set(checked['clauses']):
        issues.append({'code':'change_goal_mismatch','blocking':True})
    if quote_checks.parse_source(text)!=quote_checks.parse_source(stages[-1]['input_text']):
        issues.append({'code':'change_plan_input_mismatch','blocking':True})
    stage_map={s['turn_id']:s for s in stages}
    for part in parts:
        stage=stage_map[part['turn_id']]
        row={**part,'status':'change_replayed' if stage['generation'] and part['kind']=='user' else 'compared'}
        if part['kind']=='reference':
            row['status']='input_identical' if part['text']==text else 'historical_input_identical' if part['text']==stage['input_text'] else 'unreviewed'
            if row['status']=='unreviewed':issues.append({'code':'reference_unreviewed','blocking':False,'source':part['id']})
        source_rows.append(row)
    binding=digest({'verifier':VERSION,'request':current['binding'],'receipt':receipt,'replay':{'nodes':nodes,'events':events}})
    return {**current,'version':VERSION,'binding':binding,'request_binding':current['binding'],'source_scope':'explicit_chat_changes',
            'sources':source_rows,'source_count':len(source_rows),'clauses':checked['clauses'],'requirements_history':nodes,'changes':events,
            'issues':issues,'blocking':any(i['blocking'] for i in issues),'ready':not issues,'active_count':len(active())}


def acceptance(review, step_id):
    return {'coverage':'recipe','criteria':[{'id':'quote-changes','step_id':step_id,'check':'quote_changes','expected':review['binding']}],
            'requirements':[{'id':'change-domain','text':REQUIREMENT,'kind':'quote_changes','criterion_ids':['quote-changes']}]}


def validate(body,rule,review):source_checks.validate(body,rule,review)


def verify(body,rule,text,review):
    try:validate(body,rule,review)
    except CoreError:return {'status':'invalid','reason':'quote_changes_changed','change_verifier':VERSION,'change_binding':rule['expected']}
    checked=quote_request.verify(body,{**rule,'expected':review['request_binding']},text)
    checked.update(change_verifier=VERSION,change_binding=review['binding'],source_scope=review['source_scope'],
                   source_count=review['source_count'],change_count=len(review['changes']),active_count=review['active_count'],unresolved_count=len(review['issues']))
    if checked['status'] in {'passed','unknown'} and not review['ready']:checked.update(status='unknown',reason='quote_changes_unresolved')
    return checked
