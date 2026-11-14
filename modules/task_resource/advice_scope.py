"""Finite input/purpose checks for optional planning advice, never permission.

Uncovered goal clauses deliberately produce no purpose. Textual counterexamples
remain model-visible; this parser does not claim to understand arbitrary prose.
"""
import re
from sdk.protocol import CoreError,decode

SCHEMAS={'jarvis.notes-input.v1':'notes-excerpt-v1','jarvis.practice-input.v1':'practice-product-v1'}
CLAUSES={
    'notes-excerpt-v1':{
        '整理资料','整理当前资料','原样摘录每条原文','保留来源ID和顺序',
        '不概括','不要概括','不把草稿估价写成确认结论','保存报告'},
    'practice-product-v1':{
        '用当前给出的数生成乘法练习和正确答案','生成当前乘法练习和正确答案',
        '保留题目顺序','保存练习表','不要评价学习者是否掌握','不得声称已经掌握'},
}
REQUIRED={
    'notes-excerpt-v1':[{'整理资料','整理当前资料'},{'原样摘录每条原文'},{'保留来源ID和顺序'}],
    'practice-product-v1':[{'用当前给出的数生成乘法练习和正确答案','生成当前乘法练习和正确答案'},{'保留题目顺序'}],
}


def inspect(goal,text):
    if not isinstance(text,str) or len(text)>12000:return {}
    try:value=decode(text)
    except CoreError:return {}
    if not isinstance(value,dict):return {}
    schema=value.get('schema')
    if not isinstance(schema,str) or schema not in SCHEMAS:return {}
    if schema=='jarvis.notes-input.v1':
        if set(value)!={'schema','sources'}:return {}
        rows=value['sources']
        if not isinstance(rows,list) or not 1<=len(rows)<=64:return {}
        ids=set()
        for row in rows:
            if (not isinstance(row,dict) or set(row)!={'id','text'} or not isinstance(row['id'],str)
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',row['id']) or row['id'] in ids
                or not isinstance(row['text'],str) or not 1<=len(row['text'])<=6000):return {}
            ids.add(row['id'])
    else:
        if set(value)!={'schema','pairs'}:return {}
        rows=value['pairs']
        if (not isinstance(rows,list) or not 1<=len(rows)<=64
            or any(not isinstance(row,list) or len(row)!=2 or any(type(n) is not int or abs(n)>10**6 for n in row) for row in rows)):return {}
    result={'input_schema':schema}
    if not isinstance(goal,str) or not 1<=len(goal)<=2000:return result
    clauses=[s.strip().removeprefix('请') for s in re.split(r'[，,；;。\r\n]+',goal) if s.strip()]
    purpose=SCHEMAS[schema]
    if (clauses and len(clauses)<=32 and all(s in CLAUSES[purpose] for s in clauses)
        and all(any(s in group for s in clauses) for group in REQUIRED[purpose])):
        result['task_purpose']=purpose
    return result


def eligible(requirements,selectors):
    """Domain advice must name both verified shape and covered current purpose."""
    return bool(selectors.get('task_purpose') and selectors.get('input_schema')
        and requirements.get('task_purpose')==selectors['task_purpose']
        and requirements.get('input_schema')==selectors['input_schema'])


def selectors(plan,version=2):
    selectors={'channel':'task','planner':'goal-plan-v1','input_kind':'text' if plan['request']['input_text'] else 'empty'}
    from modules.task_resource import quote_checks,quote_request
    try:source=quote_checks.parse_source(plan['request']['input_text'])
    except CoreError:
        if version==3:
            selectors.update(inspect(plan['request']['goal'],plan['request']['input_text']))
        return selectors
    selectors.update(input_schema=source['schema'],currency=source['currency'],
        max_price_minor=source['max_price_minor'],max_delivery_days=source['max_delivery_days'])
    try:selectors['quote_requirements_ready']=quote_request.analyze(plan['request']['goal'],plan['request']['input_text'])['ready']
    except CoreError:selectors['quote_requirements_ready']=False
    if version==3 and selectors['quote_requirements_ready']:selectors['task_purpose']='quote-lowest-v1'
    return selectors
