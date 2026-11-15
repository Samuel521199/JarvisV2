"""Synthetic repair specifications; no user input or old implementation is copied."""
from modules.task_resource import lesson_checks
from sdk.protocol import CoreError,canonical,decode

CONTRACTS={
 'notes-excerpt-v1':('修复原文摘录工具',
  'Input JSON schema jarvis.notes-input.v1 contains sources [{id,text}]. Return schema jarvis.notes-result.v1 with excerpts equal to sources: preserve exact text, uncertainty, source IDs and input order. No summary or added facts.'),
 'practice-product-v1':('修复乘法练习工具',
  'Input JSON schema jarvis.practice-input.v1 contains pairs [[a,b],...]. Return schema jarvis.practice-result.v1 with exercises [{a,b,answer:a*b},...] in input order, including zero, negative and large integers. Do not claim learning mastery.'),
 'quote-lowest-v1':('修复报价比较工具',
  'Input JSON schema jarvis.quote-input.v1 contains currency, max_price_minor, max_delivery_days, offers [{id,price_minor,delivery_days,source}]. Eligible means price <= budget AND delivery <= limit. Return schema jarvis.quote-result.v1, eligible_ids in input order, selected_id and selected_source of the cheapest eligible offer. For ties select the first in input order; if none, both selected fields are null.')}

def description(purpose):
    if purpose not in CONTRACTS:raise CoreError('lesson_unsupported','No repair contract for this purpose')
    title,body=CONTRACTS[purpose]
    return title,body+' Implement pure run(text)->str for valid structured inputs. Return JSON exactly as json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(\",\",\":\")); no extra keys, prose or side effects. Generalize over inputs, never hardcode examples. This contract does not cover arbitrary language or real business delivery.'

def examples(purpose,seed):
    values=[]
    for case in lesson_checks.challenges(purpose,seed):
        v=decode(case['input'])
        if purpose=='notes-excerpt-v1':result={'schema':'jarvis.notes-result.v1','excerpts':v['sources']}
        elif purpose=='practice-product-v1':result={'schema':'jarvis.practice-result.v1','exercises':[{'a':a,'b':b,'answer':a*b} for a,b in v['pairs']]}
        else:
            offers=[o for o in v['offers'] if o['price_minor']<=v['max_price_minor'] and o['delivery_days']<=v['max_delivery_days']]
            chosen=min(offers,key=lambda o:o['price_minor']) if offers else None
            result={'schema':'jarvis.quote-result.v1','eligible_ids':[o['id'] for o in offers],
                'selected_id':chosen['id'] if chosen else None,'selected_source':chosen['source'] if chosen else None}
        expected=canonical(result)
        if not lesson_checks.score(purpose,case['input'],expected)['passed']:
            raise CoreError('lesson_oracle','Repair reference disagrees with the current oracle')
        values.append({'input':case['input'],'expected':expected})
    return values
