"""Conservative clause grammar, with uncovered text preserved for review."""
import re
from decimal import Decimal
from modules.task_resource import quote_checks as quotes
from sdk.protocol import CoreError, digest

VERSION = 'quote-request-1'
REQUIREMENT = '对照当前目标原文中受支持的报价条件及冻结输入核验结果，未覆盖内容须另行处理'
NUMBER = r'([0-9]{1,12}(?:\.[0-9]{1,2})?)'
BUDGET = re.compile(r'(?:请)?(?:预算|总预算)(?:不超过|不高于|最多|至多|上限为?|为)' + r'(?:人民币)?' + NUMBER + r'(元|万元)')
DEADLINE = re.compile(r'(?:请)?(?:交期|交货期)(?:不超过|最多|至多)([0-9]{1,4})天')
DELIVERY = re.compile(r'(?:请)?(?:在)?([0-9]{1,4})天内(?:交货|交付|送达)')
CONTROL = re.compile(r'不要|禁止|不得|不能|不允许|不选|未经|除非|或者|否则|忽略|例外|如果|只有|并非')
LITERALS = {
    '选择最低价报价': 'selection', '选择最低价方案': 'selection', '选出最低价方案': 'selection',
    '选择符合条件的最低价报价': 'selection', '在合格报价中选择最低价': 'selection',
    '保留来源引用': 'source', '附上来源引用': 'source', '保存结果': 'save', '保存报告': 'save',
    '比较以下报价': 'intro', '比较报价': 'intro', '谢谢': 'courtesy',
}


def analyze(goal, input_text):
    if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 2000 or len(goal)>2000:
        raise CoreError('acceptance_invalid', 'Quote request review requires the full goal within 2000 characters')
    source=quotes.parse_source(input_text)
    clauses=[];values={};issues=[]
    for match in re.finditer(r'[^，,；;。\r\n]+',goal):
        raw=match.group();clause=raw.strip()
        if not clause:continue
        start=match.start()+len(raw)-len(raw.lstrip());end=start+len(clause)
        kind='uncovered';value=None
        budget=BUDGET.fullmatch(clause);days=DEADLINE.fullmatch(clause) or DELIVERY.fullmatch(clause)
        if budget:
            kind='budget';value=int(Decimal(budget[1])*(1000000 if budget[2]=='万元' else 100))
        elif days:kind='delivery';value=int(days[1])
        else:kind=LITERALS.get(clause.removeprefix('请'),'uncovered')
        item={'start':start,'end':end,'text':clause,'kind':kind}
        if value is not None:item['value']=value
        clauses.append(item)
        if kind in {'budget','delivery','selection'}:
            if kind in values:issues.append({'code':'duplicate_'+kind,'blocking':True,'span':[start,end]})
            else:values[kind]=value if value is not None else True
    if len(clauses)>32:
        raise CoreError('acceptance_invalid','Quote request review supports at most 32 clauses')
    for kind in ('budget','delivery','selection'):
        if kind not in values:issues.append({'code':'missing_'+kind,'blocking':False})
    for kind,key in [('budget','max_price_minor'),('delivery','max_delivery_days')]:
        if kind in values and values[kind]!=source[key]:issues.append({'code':kind+'_mismatch','blocking':True,'requested':values[kind],'input':source[key]})
    if 'budget' in values and source['currency']!='CNY':issues.append({'code':'currency_mismatch','blocking':True})
    uncovered=[i for i in clauses if i['kind']=='uncovered']
    if any(CONTROL.search(i['text']) for i in uncovered):
        issues.append({'code':'unsupported_control','blocking':True})
    if uncovered:issues.append({'code':'uncovered_text','blocking':False,'count':len(uncovered)})
    binding=digest({'parser':VERSION,'goal':quotes.source_digest(goal),'input':quotes.source_digest(input_text)})
    return {'version':VERSION,'binding':binding,'goal_digest':quotes.source_digest(goal),'input_digest':quotes.source_digest(input_text),
            'clauses':clauses,'extracted':values,'issues':issues,'blocking':any(i['blocking'] for i in issues),
            'ready':not issues,'semantic_goal_verified':False,'scope':'finite_chinese_quote_clauses','source_scope':'stored_goal_only'}


def acceptance(review, step_id):
    return {'coverage':'recipe','criteria':[{'id':'quote-request','step_id':step_id,'check':'quote_request','expected':review['binding']}],
            'requirements':[{'id':'request-domain','text':REQUIREMENT,'kind':'quote_request','criterion_ids':['quote-request']}]}


def bound_review(body, rule):
    text=body['steps'][0]['arguments'].get('text')
    review=analyze(body['goal'],text)
    if review['binding']!=rule['expected'] or review['blocking']:
        raise CoreError('acceptance_invalid','Quote request review changed or conflicts with the frozen input')
    quotes.bound_source(body,{**rule,'expected':review['input_digest']})
    return review


def verify(body, rule, text):
    try:review=bound_review(body,rule)
    except CoreError:return {'status':'invalid','reason':'quote_request_changed','request_verifier':VERSION,'request_binding':rule['expected']}
    checked=quotes.verify(body,{**rule,'expected':review['input_digest']},text)
    evidence={**checked,'request_verifier':VERSION,'request_binding':review['binding'],'request_goal_digest':review['goal_digest'],
              'unresolved_count':len(review['issues']),'semantic_goal_verified':False,'request_scope':'stored_goal_only'}
    if checked['status']=='passed' and not review['ready']:
        evidence.update(status='unknown',reason='quote_request_unresolved')
    return evidence
