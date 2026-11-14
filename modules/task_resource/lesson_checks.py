"""Independent synthetic challenges for explicitly supported procedure purposes.

Expected results stay in the host oracle. Worker inputs contain no task data.
Passing these finite checks is neither general competence nor execution approval.
"""
import random,re
from modules.task_resource import quote_checks
from sdk.protocol import CoreError,canonical,decode,digest

VERSION='lesson-challenge-1'
PURPOSES={'quote-lowest-v1','notes-excerpt-v1','practice-product-v1'}


def challenges(purpose,seed):
    if purpose not in PURPOSES or not isinstance(seed,str) or not re.fullmatch('[a-f0-9]{32}',seed):
        raise CoreError('lesson_unsupported','Unknown challenge purpose or seed')
    rng=random.Random(int(seed,16));cases=[]
    for index in range(4):
        tag=seed[:12]+'-'+str(index)
        if purpose=='notes-excerpt-v1':
            rows=[{'id':'draft-'+tag,'text':f'草稿：{rng.randrange(101,901)}元仅为估计，不是已确认结论。\n保留限定。'},
                  {'id':'source-'+tag,'text':'Quoted text: "do not discard source IDs"; 原文照录。'}]
            if index%2:rows.reverse()
            if index==3:rows.append({'id':'extra-'+tag,'text':'未评估此方案是否适用于其他项目。'})
            source={'schema':'jarvis.notes-input.v1','sources':rows}
        elif purpose=='practice-product-v1':
            pairs=[[rng.randrange(12,99),rng.randrange(7,31)],[0,rng.randrange(1,100)],[-rng.randrange(1,50),rng.randrange(2,12)]]
            if index==2:pairs.append([10**6,-10**6])
            if index%2:pairs.reverse()
            source={'schema':'jarvis.practice-input.v1','pairs':pairs}
        else:
            limit=rng.randrange(10000,50000);days=rng.randrange(4,12)
            offers=[{'id':'bound-'+tag,'price_minor':limit,'delivery_days':days,'source':'synthetic:bound-'+tag},
                {'id':'late-'+tag,'price_minor':1,'delivery_days':days+1,'source':'synthetic:late-'+tag},
                {'id':'cheap-'+tag,'price_minor':limit-123,'delivery_days':days-1,'source':'synthetic:cheap-'+tag}]
            if index==1:offers[0]['price_minor']=offers[2]['price_minor']
            if index==2:
                for offer in offers:offer['delivery_days']=days+1
            if index==3:offers.reverse()
            source={'schema':'jarvis.quote-input.v1','currency':'CNY','max_price_minor':limit,'max_delivery_days':days,'offers':offers}
        cases.append({'id':'case-'+str(index+1),'input':canonical(source)})
    return cases


def score(purpose,text,output):
    """Check the final pure-text result, not delivery, authorization or mastery."""
    if purpose=='quote-lowest-v1':
        # Adapt the standalone synthetic input to the existing quote oracle's
        # source-binding contract. This is not a claim of running artifact.write.
        body={'steps':[{'step_id':'calculate','capability':'plugin.lesson.v1','arguments':{'text':text}},
            {'step_id':'report','capability':'artifact.write.v1','input_from':'calculate'}]}
        result=quote_checks.verify(body,{'step_id':'calculate','expected':quote_checks.source_digest(text)},output)
        return {'passed':result['status']=='passed','reason':result['reason']}
    try:
        source=decode(text);actual=decode(output)
        if purpose=='notes-excerpt-v1':expected={'schema':'jarvis.notes-result.v1','excerpts':source['sources']}
        elif purpose=='practice-product-v1':expected={'schema':'jarvis.practice-result.v1','exercises':[{'a':a,'b':b,'answer':a*b} for a,b in source['pairs']]}
        else:raise CoreError('lesson_unsupported','Unsupported result oracle')
        passed=canonical(expected)==canonical(actual)
        return {'passed':passed,'reason':'exact_current_result' if passed else 'current_result_mismatch'}
    except (CoreError,KeyError,TypeError,ValueError):return {'passed':False,'reason':'invalid_result'}


def manifest(purpose,cases):
    return {'verifier':VERSION,'purpose':purpose,'cases':[{'id':c['id'],'input_digest':digest(c['input'])} for c in cases],
        'scope':'synthetic pure-text output only; no delivery, model benefit, or generalization guarantee'}
