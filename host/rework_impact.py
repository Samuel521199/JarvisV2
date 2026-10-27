"""Deterministic change analysis of complete pure-text plans; never authorizes work."""
from host import capabilities, goal_context, work_revisions
from modules.task_resource.plans import validate_proposal
from sdk.protocol import CoreError, digest


def analyze(core, value):
    for key in ('revision', 'work_revision'):
        if type(value[key]) is not int or value[key] < 1:
            raise CoreError('rework_invalid', 'Invalid source revision')
    if not isinstance(value['goal'], str) or not 1 <= len(value['goal'].strip()) <= 4000:
        raise CoreError('rework_invalid', 'Describe the complete revised goal')
    p, _, source_digest = work_revisions.source(core, value['id'], 1)
    work_revisions.check(core, p['id'], execution=True)
    owner = core.works.owner(p['id'])
    if (p['revision'] != value['revision'] or
            (owner and (owner['revision'] != value['work_revision'] or owner['current_goal'] != p['id']
                        or owner['cancelled'])) or (not owner and value['work_revision'] != 1)):
        raise CoreError('work_conflict', 'Source work changed')
    if owner and core.works.link(p['id'])['ordinal'] >= 4:
        raise CoreError('work_limit', 'At most three reviewed follow-ups per work')
    link=core.works.link(p['id']);ancestor_prefix=False
    for _ in range(4):
        if not link or not link['parent_goal']:break
        ancestor_prefix=ancestor_prefix or link['start_step']>1
        link=core.works.link(link['parent_goal'])
    ctx = goal_context.get(core, p['id'])
    catalog = [r for r in capabilities.catalog(core, ctx['scope'] if ctx else 'personal')
               if r['capability'].startswith('plugin.')]
    new = validate_proposal(value['proposal'], catalog)
    if (not new['steps'] or new['questions'] or
            any(not s['capability'].startswith('plugin.') or (i and s['source'] != 'previous')
                for i, s in enumerate(new['steps']))):
        raise CoreError('rework_unsupported', 'Supply a resolved complete pure-text linear plan')
    old = p['proposal']; reasons = []; start = None
    if ancestor_prefix and (value['goal'] != p['request']['goal'] or new['input_text'] != old['input_text']):
        raise CoreError('rework_full_plan_required', 'A prior version retained upstream steps; a new full plan is required for changed goal or input')
    if value['goal'] != p['request']['goal']:
        reasons.append('goal_changed'); start = 1
    if new['input_text'] != old['input_text']:
        reasons.append('input_changed'); start = 1
    refs = {r['capability']:r for r in catalog}
    old_refs = {r['capability']:r for r in p['catalog']}
    prefix = 0
    for before, after in zip(old['steps'], new['steps']):
        ref = refs[after['capability']]; prior = old_refs[before['capability']]
        if before != after or any(prior[k] != ref[k] for k in ('capability','active','revision')):
            break
        prefix += 1
    if prefix < max(len(old['steps']), len(new['steps'])):
        reasons.append('step_or_binding_changed')
        # Removing a tail still needs a new delivery of the new last step.
        start = start or min(prefix + 1, len(new['steps']), len(old['steps']))
    if start is None:
        raise CoreError('rework_no_change', 'No execution-relevant change; existing output remains available')
    for step in new['steps']:
        capabilities.require(core, refs[step['capability']])
    # The original guard validates every receipt and every reused capability.
    _, _, checked_digest = work_revisions.source(core, p['id'], start)
    if checked_digest != source_digest:
        raise CoreError('rework_analysis_changed', 'Source changed during analysis')
    result = {'version':'rework-impact-1.4.0', 'goal_id':p['id'], 'start_step':start,
              'reused_steps':list(range(1,start)),
              'rerun_steps':list(range(start,len(new['steps'])+1)), 'reasons':reasons,
              'planned_cost_units':len(new['steps'])-start+2,
              'scope':'structural_current_plan_only','ancestor_prefix_reused':ancestor_prefix,
              'semantic_impact_verified':False}
    result['analysis_digest'] = digest({'result':result, 'source':source_digest,
        'goal':value['goal'], 'proposal':new, 'revision':p['revision'],
        'work_revision':owner['revision'] if owner else 1,
        'bindings':[refs[s['capability']] for s in new['steps']]})
    return result
