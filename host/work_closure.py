"""A read model of current work closure, composed from the original evidence."""
from contextlib import nullcontext
from host.completion import projection
from modules.task_resource.plans import Plans


def current(core, ident):
    with (nullcontext() if core.db.connection.in_transaction else core.db.transaction()):
        work = core.works.projection(ident)
        if not work: return None
        p = Plans(core.db).get(work['current_goal'])
        t = core.tasks.get(p['task_id']) if p['task_id'] else None
        result = projection(core,t['id']) if t else None
        budget = work['budget']; reasons = []
        if work['cancelled'] or p['cancel'] or (t and t['cancel']):
            state = 'STOPPED'; reasons.append('work_or_version_stopped')
        elif not t:
            state = 'NEEDS_REVIEW'; reasons.append('current_version_not_admitted')
        elif t['status'] not in {'SUCCEEDED','FAILED','CANCELLED'}:
            state = 'IN_PROGRESS'; reasons.append(t.get('error') or 'current_execution_pending')
        elif not result or result['state'] not in {'VERIFIED','ACCEPTED'} or not result.get('requirement_coverage',{}).get('complete'):
            state = 'NEEDS_EVIDENCE'; reasons.append(result['state'] if result else 'UNAVAILABLE')
        else:
            state = 'COMPLETE'
        if not budget['enforced']:
            reasons.append('shared_budget_not_adopted')
        if budget['integrity'] != 'complete': reasons.append('budget_evidence_invalid')
        if budget['enforced'] and budget['committed_units'] > budget['limit_units']:
            reasons.append('budget_overcommitted')
        if budget['unresolved_tasks']: reasons.append('unresolved_effects')
        if state == 'COMPLETE' and reasons: state = 'NEEDS_EVIDENCE'
        return {'version':'work-closure-1.4.0','root_goal':work['root_goal'],
                'current_goal':p['id'],'current_task':p['task_id'],'state':state,
                'complete':state=='COMPLETE','reasons':reasons,
                'completion_state':result['state'] if result else None,
                'condition_score':result.get('condition_score') if result else None,
                'score_scope':'current_declared_conditions_only','quality_score':None,
                'requirement_coverage':result.get('requirement_coverage') if result else None,
                'assessment_fingerprint':result.get('fingerprint') if result else None,
                'spent_cost_units':budget['spent_units'],'reserved_cost_units':budget['reserved_units']}
