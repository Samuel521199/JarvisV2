"""Compose immutable Work receipts and accepted requirement reviews, without effects."""
from host import goal_context, work_revisions, quote_sources
from modules.task_resource import inheritance_checks, source_checks, recovery_checks
from modules.task_resource.plans import Plans
from sdk.protocol import CoreError, decode, digest


def review(core,ident,*,recovery=False):
    present=core.works.has_recovery(ident)
    if present!=recovery:raise CoreError('acceptance_invalid','Select the verifier matching the recovery lineage')
    lineage(core,ident)  # Reject unsupported partial-prefix mode before source inspection.
    work_revisions.check(core,ident)
    return _replay(core,ident)


def lineage(core,ident):
    link=core.works.link(ident)
    if not link or not link['parent_goal']:raise CoreError('acceptance_invalid','Work inheritance requires an admitted parent')
    chain=[];seen=set()
    while link and link['parent_goal']:
        if link['goal_id'] in seen or len(chain)>=3:raise CoreError('plan_source_changed','Work ancestry invalid')
        if link['start_step']!=1:raise CoreError('acceptance_invalid','Requirement inheritance requires a full rerun')
        seen.add(link['goal_id']);chain.append(link);link=core.works.link(link['parent_goal'])
    if not link or link['goal_id'] in seen:raise CoreError('plan_source_changed','Work root missing or cyclic')
    if any(e['root_goal']!=link['goal_id'] for e in chain):raise CoreError('plan_source_changed','Work roots differ')
    if link['ordinal']!=1 or [e['ordinal'] for e in reversed(chain)]!=list(range(2,len(chain)+2)):
        raise CoreError('plan_source_changed','Work revision sequence changed')
    return link,chain


def _replay(core,ident):
    """Caller must validate current sources, or prove feedback-only transitions first."""
    plans=Plans(core.db);current=plans.get(ident);goal_context.check(core,ident)
    link,chain=lineage(core,ident)
    parent=plans.get(link['goal_id']);checked=quote_sources.review(core,parent['id'],changes=True)
    expected='quote_changes'
    for edge in reversed(chain):
        accepted=core.db.one('SELECT body FROM task_acceptance WHERE task_id=?',(parent['task_id'],))
        rules=decode(accepted['body']) if accepted else {}
        candidates=[c for c in rules.get('criteria',[]) if c['check']==expected]
        if len(candidates)!=1:raise CoreError('acceptance_invalid','Parent requires its frozen source-aware acceptance')
        body=core.tasks.get(parent['task_id'])['body']
        if body['goal']!=parent['request']['goal'] or body['steps'][0]['arguments'].get('text')!=parent['proposal']['input_text']:
            raise CoreError('plan_source_changed','Parent task differs from reviewed request')
        source_checks.validate(body,candidates[0],checked)
        child=plans.get(edge['goal_id']);ctx=goal_context.get(core,child['id']);proposal=child['proposal']
        goal_context.check(core,child['id'])
        if child['generation'] or ctx and ctx['history']:
            raise CoreError('acceptance_invalid','Rework amendments require a new explicit Work version')
        if not proposal or not proposal['steps'] or any(not s['capability'].startswith('plugin.') or i and s['source']!='previous' for i,s in enumerate(proposal['steps'])):
            raise CoreError('acceptance_invalid','Rework requires a pure text serial plan')
        receipt=digest({'link':edge,'parent_acceptance':rules,'request':child['request'],'proposal':proposal})
        if edge['kind']=='recovery':
            checkpoint=core.works.recovery(edge['goal_id'])
            if not checkpoint or digest(checkpoint)!=edge['source_digest'] or child['request']['goal']!=parent['request']['goal']:
                raise CoreError('rework_source_changed','Recovery checkpoint or preserved goal changed')
            checked=recovery_checks.restored(child['request']['goal'],proposal['input_text'],checked,parent['proposal']['input_text'],edge,receipt,checkpoint)
        else:
            inherited=inheritance_checks.analyze(child['request']['goal'],proposal['input_text'],checked,parent['proposal']['input_text'],edge,receipt)
            checked=recovery_checks.seal(inherited,checked['recoveries']) if checked.get('recoveries') else inherited
        expected='quote_recovery' if checked.get('recoveries') else 'quote_rework'
        parent=child
    return {**checked,'goal_id':ident,'revision':current['revision'],
            'acceptance':(recovery_checks if checked.get('recoveries') else inheritance_checks).acceptance(checked,'step-'+str(len(current['proposal']['steps'])))}
