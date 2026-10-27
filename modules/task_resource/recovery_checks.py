"""Recovery retains requirements; it cannot upgrade old evidence or change authority."""
from modules.task_resource import inheritance_checks, source_checks, quote_request
from sdk.protocol import CoreError, digest

VERSION='quote-recovery-1'
REQUIREMENT='按明确复核的反馈恢复边界保留有效要求与旧事实，独立核验新版本报价结果'


def seal(review, recoveries):
    return {**review,'version':VERSION,'binding':digest({'verifier':VERSION,'inheritance':review['binding'],'recoveries':recoveries}),
            'source_scope':'explicit_feedback_recovery','recoveries':recoveries}


def restored(goal,text,parent,parent_text,edge,receipt,checkpoint):
    review=inheritance_checks.analyze(goal,text,parent,parent_text,
        {**edge,'kind':'correction','note':inheritance_checks.KEEP},receipt)
    review['sources'][-1].update(name='恢复复核说明',text=edge['note'],status='inherited')
    review['rework_versions'][-1].update(kind='recovery',note=edge['note'])
    if text!=parent_text:review['issues'].append({'code':'recovery_input_changed','blocking':True})
    review.update(blocking=any(i['blocking'] for i in review['issues']),ready=not review['issues'])
    return seal(review,parent.get('recoveries',[])+[{'goal_id':edge['goal_id'],'parent_goal':edge['parent_goal'],
        'checkpoint':edge['source_digest'],'changed_sources':sum(r['feedback_changed'] for r in checkpoint['sources']),
        'retired_task':checkpoint['retired_task']}])


def acceptance(review,step_id):
    return {'coverage':'recipe','criteria':[{'id':'quote-recovery','step_id':step_id,'check':'quote_recovery','expected':review['binding']}],
            'requirements':[{'id':'recovery-domain','text':REQUIREMENT,'kind':'quote_recovery','criterion_ids':['quote-recovery']}]}


def verify(body,rule,text,review):
    try:source_checks.validate(body,rule,review)
    except CoreError:return {'status':'invalid','reason':'quote_recovery_changed','recovery_verifier':VERSION,'recovery_binding':rule['expected']}
    checked=quote_request.verify(body,{**rule,'expected':review['request_binding']},text)
    checked.update(recovery_verifier=VERSION,recovery_binding=review['binding'],source_scope=review['source_scope'],
        recovery_count=len(review['recoveries']),active_count=review['active_count'],unresolved_count=len(review['issues']))
    if checked['status'] in {'passed','unknown'} and not review['ready']:checked.update(status='unknown',reason='quote_recovery_unresolved')
    return checked
