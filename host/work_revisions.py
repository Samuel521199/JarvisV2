"""Host composes existing plans, immutable receipts, context and grants for rework."""
import re

from control import receipts
from control.paths import child
from control.recovery.gate import RunLock
from host import goal_context, capabilities
from modules.task_resource.plans import Plans, validate_proposal, planning_key
from modules.task_resource.work_budgets import WorkBudgets
from sdk.protocol import CoreError, canonical, decode, digest


def source(core, ident, start):
    return source_snapshot(core,ident,start)[:3]


def source_snapshot(core, ident, start):
    """Validate only a completed local pure-text chain; no model or external effects."""
    p = Plans(core.db).get(ident)
    if not p['task_id'] or p['cancel']: raise CoreError('rework_source_changed', 'A completed source task is required')
    t = core.tasks.get(p['task_id']); proposal = p['proposal']
    if (t['status'] != 'SUCCEEDED' or t['cancel'] or not proposal or not proposal['steps']
            or any(not s['capability'].startswith('plugin.') or (i and s['source'] != 'previous')
                   for i, s in enumerate(proposal['steps']))):
        raise CoreError('rework_unsupported', 'Only succeeded pure-text linear plans support linked rework')
    if type(start) is not int or not 1 <= start <= len(proposal['steps']):
        raise CoreError('rework_invalid', 'Select the first step to redo')
    goal_context.check(core, ident)
    chat_link=core.db.one('SELECT chat_id FROM chat_goals WHERE goal_id=?',(ident,))
    if chat_link:
        from host.memory_domains import chat_scope
        from modules.dialogue.store import Dialogues
        chats=Dialogues(core.root)
        try:
            ctx=goal_context.get(core,ident)
            if not ctx or chat_scope(core.root,chats.read(chat_link['chat_id']),db=core.db)!=ctx['scope']:
                raise CoreError('rework_source_changed','Source conversation changed its knowledge domain')
        finally:chats.close()
    actions = core.tasks.actions(t['id']); by_step = {a['step_id']:a for a in actions}
    bindings = t['bindings']
    for i, s in enumerate(proposal['steps']):
        a = by_step.get('step-'+str(i+1))
        if not a or a['status'] != 'CONFIRMED': raise CoreError('rework_source_changed', 'Source receipt missing')
        result = decode(a['result']); args = decode(a['arguments'])
        if result.get('redacted') or not isinstance(result.get('text'), str):
            raise CoreError('rework_source_changed', 'Source text unavailable')
        if receipts.read(core.root, receipts.binding(t['id'], a['id'], bindings[a['capability']], args)) != result:
            raise CoreError('rework_source_changed', 'Source receipt changed')
        if i < start-1:
            ref = next(r for r in p['catalog'] if r['capability'] == s['capability'])
            capabilities.require(core, ref)
    a = by_step.get('deliver')
    if not a or a['status'] != 'CONFIRMED': raise CoreError('rework_source_changed', 'Source delivery missing')
    result = decode(a['result'])
    if result.get('redacted'): raise CoreError('rework_source_changed', 'Source delivery withdrawn')
    path = child(core.root, result['relative_path'])
    import hashlib
    if not path.is_file() or path.stat().st_size > 2000000 or hashlib.sha256(path.read_bytes()).hexdigest() != result['sha256']:
        raise CoreError('rework_source_changed', 'Source artifact changed')
    feedback = core.db.one('SELECT id,digest FROM completion_feedback WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 1', (t['id'],))
    snapshot = {'goal':{k:p[k] for k in ('id','revision','request','proposal','cancel')},
                          'task':{k:t[k] for k in ('id','revision','body','bindings','status','cancel')},
                          'actions':actions, 'feedback':feedback}
    text = decode(by_step['step-'+str(start-1)]['result'])['text'] if start > 1 else proposal['input_text']
    if len(text) > 12000: raise CoreError('rework_unsupported', 'Reusable text exceeds the plan input bound')
    return p, text, digest(snapshot), snapshot


def check(core, ident, *, execution=False):
    owner = core.works.owner(ident)
    if not owner: return
    if execution and (owner['cancelled'] or owner['current_goal'] != ident
                      or owner['assistant_id'] != core.identity.describe()['assistant_id']):
        raise CoreError('work_conflict', 'Work is cancelled or this is not its current responsible version')
    if core.works.has_recovery(ident):
        from host.work_recovery import validate_path
        validate_path(core,ident);return
    link = core.works.link(ident)
    for _ in range(4):
        if not link['parent_goal']: return
        try:
            _, _, current = source(core, link['parent_goal'], link['start_step'])
            if current != link['source_digest']: raise CoreError('rework_source_changed', 'Source or feedback changed after review')
        except (CoreError, OSError, KeyError, ValueError) as exc:
            raise CoreError('rework_source_changed', 'Rework source, permission or receipt is no longer current') from exc
        link = core.works.link(link['parent_goal'])
        if not link: raise CoreError('rework_source_changed', 'Work ancestry missing')
    raise CoreError('rework_source_changed', 'Work ancestry exceeds its bound')


def validate_edit(core, ident, proposal):
    link = core.works.link(ident)
    if not link or not link['parent_goal']: return
    check(core, ident, execution=True)
    if link['kind']=='recovery':text=Plans(core.db).get(link['parent_goal'])['proposal']['input_text']
    else:_, text, _ = source(core, link['parent_goal'], link['start_step'])
    if (not proposal['steps'] or any(not s['capability'].startswith('plugin.') or (i and s['source']!='previous')
                                   for i,s in enumerate(proposal['steps']))
            or (link['start_step'] > 1 or link['kind']=='recovery') and proposal['input_text'] != text):
        raise CoreError('rework_invalid', 'Reused prefix input is fixed; edit only the pure-text suffix')


def create(core, value):
    automatic = value['action'] == 'rework_auto'
    for name in (('revision','work_revision') if automatic else ('revision','work_revision','start_step')):
        if type(value[name]) is not int or value[name] < 1: raise CoreError('rework_invalid', 'Invalid version or step')
    if (not isinstance(value['request_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',value['request_id'])
            or value['kind'] not in ('correction','new_requirement')
            or not isinstance(value['goal'],str) or not 1<=len(value['goal'].strip())<=4000
            or not isinstance(value['note'],str) or not 1<=len(value['note'].strip())<=1000):
        raise CoreError('rework_invalid', 'Describe the full revised goal and why it changes')
    request_digest = digest(value); plans = Plans(core.db)
    with RunLock(core.root), goal_context.LOCK, core.db.transaction() as tx:
        old = core.db.one('SELECT goal_id,request_digest FROM work_revisions WHERE request_id=?',(value['request_id'],))
        if old:
            if old['request_digest'] != request_digest: raise CoreError('conflict','Rework request ID changed')
            return {'id':old['goal_id'],'existing':True}
        core.gate.require_running()
        impact = None
        if automatic:
            from host.rework_impact import analyze
            impact = analyze(core, value)
            if value['analysis_digest'] != impact['analysis_digest']:
                raise CoreError('rework_analysis_changed', 'Analyze the current complete plan again')
            value = {**value, 'start_step':impact['start_step']}
        p, text, fingerprint = source(core, value['id'], value['start_step'])
        if p['revision'] != value['revision']: raise CoreError('work_conflict','Source version changed')
        check(core, p['id'], execution=True)
        core.works.register(p['id'], core.identity.describe()['assistant_id'], tx, 'followup_adoption')
        owner = core.works.owner(p['id'])
        if owner['cancelled'] or owner['current_goal'] != p['id'] or owner['revision'] != value['work_revision']:
            raise CoreError('work_conflict','Work changed before follow-up')
        ctx = goal_context.get(core, p['id'])
        catalog = [r for r in capabilities.catalog(core, ctx['scope'] if ctx else 'personal') if r['capability'].startswith('plugin.')]
        complete = value['proposal'] if automatic else p['proposal']
        if automatic and value['start_step'] == 1: text = complete['input_text']
        proposal = {**complete, 'summary':value['note'], 'input_text':text,
                    'steps':[dict(s) for s in complete['steps'][value['start_step']-1:]], 'questions':[]}
        proposal['steps'][0]['source'] = 'input'
        validate_proposal(proposal, catalog)
        req = {**p['request'], 'request_id':'work-'+digest(value['request_id'])[:40], 'goal':value['goal'], 'input_text':text}
        ident, fresh = plans.create(req,catalog,p['routes'],tx)
        if not fresh: raise CoreError('conflict','Follow-up goal request already used')
        tx.execute("UPDATE goal_plans SET proposal=?,status='REVIEW' WHERE id=?",(canonical(proposal),ident))
        if ctx:
            tx.execute('INSERT INTO goal_context(goal_id,scope,enabled,view) VALUES(?,?,?,?)',
                       (ident,ctx['scope'],ctx['enabled'],canonical(ctx['view'])))
        if value['kind'] == 'correction':
            from host.completion import refresh
            from modules.task_resource.completion import Completion
            current = refresh(core, p['task_id'], transaction=tx)
            Completion(core.db).feedback(p['task_id'],'rework-'+digest(value['request_id'])[:40],
                current['fingerprint'],'reject',value['note'],current,tx)
            _, _, fingerprint = source(core,p['id'],value['start_step'])
        core.works.append(p['id'],ident,value['work_revision'],value['kind'],value['note'],value['start_step'],
                          fingerprint,value['request_id'],request_digest,tx)
        if impact:
            core.db.event(tx,None,'work.impact_applied',{'goal_id':ident,'parent_goal':p['id'],
                'analysis':impact,'complete_proposal_sha256':digest(complete),
                'revised_goal_sha256':digest(value['goal'])})
        return {'id':ident,'existing':False}


def cancel(core, ident, revision):
    if type(revision) is not int or revision < 1: raise CoreError('work_conflict','Invalid work revision')
    with goal_context.LOCK, core.db.transaction() as tx:
        owner = core.works.owner(ident)
        if not owner: raise CoreError('work_conflict','No registered work')
        if owner['cancelled'] and owner['revision'] == revision+1: return core.works.projection(ident)
        if owner['revision'] != revision: raise CoreError('work_conflict','Work changed before cancellation')
        tx.execute('UPDATE work_owners SET cancelled=1,revision=revision+1 WHERE root_goal=?',(owner['root_goal'],))
        p = Plans(core.db).get(owner['current_goal'])
        core.grants.revoke(planning_key(p)+'-plan',transaction=tx)
        task = core.tasks.get(p['task_id']) if p['task_id'] else None
        if task: core.grants.revoke(task['body']['grant_id'],transaction=tx)
        if not task or task['status'] not in {'SUCCEEDED','FAILED','CANCELLED'}:
            if task: core.tasks.cancel(task['id'],transaction=tx)
            from host.goal_growth import cancel as cancel_growth
            cancel_growth(core,p['id'],tx)
            tx.execute("UPDATE goal_plans SET cancel=1,status='CANCELLED',revision=revision+1 WHERE id=? AND cancel=0",(p['id'],))
        core.db.event(tx,p['task_id'],'work.cancelled',{'root_goal':owner['root_goal'],'revision':revision+1})
    return core.works.projection(ident)


def review_source(core, value):
    """Explicit re-review of a draft after feedback; admitted plans stay frozen."""
    if (type(value['revision']) is not int or type(value['work_revision']) is not int
            or not isinstance(value['note'],str) or not 1<=len(value['note'].strip())<=1000):
        raise CoreError('rework_invalid','Describe why the prefix is still applicable')
    with RunLock(core.root), goal_context.LOCK, core.db.transaction() as tx:
        core.gate.require_running();p=Plans(core.db).get(value['id']);link=core.works.link(p['id']);owner=core.works.owner(p['id'])
        if (not link or not link['parent_goal'] or not owner or owner['cancelled'] or owner['current_goal']!=p['id']
                or owner['revision']!=value['work_revision'] or p['revision']!=value['revision']
                or p['task_id'] or p['cancel'] or p['status']!='REVIEW'):
            raise CoreError('work_conflict','Only the current unadmitted draft can review changed evidence')
        check(core,link['parent_goal'])
        _, text, fingerprint=source(core,link['parent_goal'],link['start_step'])
        if fingerprint==link['source_digest']:raise CoreError('rework_invalid','Source evidence has not changed')
        # Readable source, immutable receipts and its scope are still required, including past withdrawals.
        proposal=p['proposal']
        if link['start_step']>1:proposal={**proposal,'input_text':text}
        tx.execute('UPDATE goal_plans SET proposal=?,revision=revision+1 WHERE id=?',(canonical(proposal),p['id']))
        tx.execute('UPDATE work_revisions SET source_digest=? WHERE goal_id=?',(fingerprint,p['id']))
        tx.execute('UPDATE work_owners SET revision=revision+1 WHERE root_goal=?',(owner['root_goal'],))
        core.db.event(tx,None,'work.source_reviewed',{'goal_id':p['id'],'old_digest':link['source_digest'],
                      'source_digest':fingerprint,'note':value['note'],'goal_revision':p['revision']+1})
        return {'id':p['id'],'revision':p['revision']+1,'work_revision':owner['revision']+1}


def configure_budget(core, value):
    with goal_context.LOCK,core.db.transaction() as tx:
        core.gate.require_running();p=Plans(core.db).get(value['id'])
        if not core.works.owner(p['id']):
            if not p['task_id'] or p['cancel']:raise CoreError('work_budget_required','An admitted work is required')
            core.works.register(p['id'],core.identity.describe()['assistant_id'],tx,'budget_adoption')
        return WorkBudgets(core.db).configure(p['id'],value['revision'],value['request_id'],value['limit_units'],value['note'],tx)
