"""New immutable Work boundaries for proven feedback-only invalidation.

Old tasks and checkpoints are never re-signed. No model, dispatch, or grant is
created here; the new draft must pass the ordinary admission path again.
"""
import hashlib
import re
from control import receipts
from control.paths import child
from control.policy.grants import GrantStore
from control.recovery.gate import RunLock
from control.execution import admission
from host import goal_context, capabilities, work_revisions, quote_rework
from modules.task_resource.plans import Plans, validate_proposal, planning_key
from modules.task_resource import source_checks
from sdk.protocol import CoreError, canonical, decode, digest

SCHEMA='jarvis.work-recovery.v1'


def checkpoint(core,edge):
    record=core.works.recovery(edge['goal_id'])
    if (not record or record.get('schema')!=SCHEMA or record.get('parent_goal')!=edge['parent_goal']
            or digest(record)!=edge['source_digest']):
        raise CoreError('rework_source_changed','Recovery checkpoint missing or changed')
    return record


def _coverage(core,edges):
    """A later recovery may supersede earlier feedback observations, not facts."""
    latest=None;position=-1
    for i,edge in enumerate(edges):
        if edge['kind']=='recovery':latest=checkpoint(core,edge);position=i
    if latest is None:return {}
    rows=latest['sources']
    if ([r['edge_goal'] for r in rows]!=[e['goal_id'] for e in edges[:position]]
            or [r['parent_goal'] for r in rows]!=[e['parent_goal'] for e in edges[:position]]):
        raise CoreError('rework_source_changed','Recovery source coverage is incomplete')
    return {r['edge_goal']:r['current_digest'] for r in rows}


def _known_actions(core,p,t):
    actions=core.tasks.actions(t['id']);steps=t['body']['steps']
    if (any(a['status']!='CONFIRMED' for a in actions) or t['spent']!=len(actions)
            or [a['step_id'] for a in actions]!=[s['step_id'] for s in steps[:len(actions)]]
            or t['status']=='SUCCEEDED' and len(actions)!=len(steps)):
        raise CoreError('recovery_unresolved','Unconfirmed effects or inconsistent spending require reconciliation')
    for a,s in zip(actions,steps):
        result=decode(a['result']);args=decode(a['arguments'])
        if a['capability']!=s['capability'] or result.get('redacted'):
            raise CoreError('rework_source_changed','Action source withdrawn or changed')
        if a['step_id']=='deliver':
            path=child(core.root,result['relative_path'])
            if not path.is_file() or path.stat().st_size>2000000 or hashlib.sha256(path.read_bytes()).hexdigest()!=result['sha256']:
                raise CoreError('rework_source_changed','Confirmed delivery changed')
        elif not a['capability'].startswith('plugin.') or not isinstance(result.get('text'),str):
            raise CoreError('recovery_unsupported','Only known pure-text results can be retained')
        elif receipts.read(core.root,receipts.binding(t['id'],a['id'],t['bindings'][a['capability']],args))!=result:
            raise CoreError('rework_source_changed','Confirmed receipt changed')
    return actions


def _target_snapshot(core,ident,*,retired=False):
    p=Plans(core.db).get(ident);goal_context.check(core,ident)
    if not p['task_id'] or not p['proposal'] or not p['proposal']['steps']:
        raise CoreError('recovery_unsupported','An admitted complete plan is required')
    t=core.tasks.get(p['task_id'])
    if (retired and (not p['cancel'] or not t['cancel'] or t['status']!='CANCELLED')
            or not retired and (p['cancel'] or t['cancel'] or t['status'] not in {'READY','WAITING','SUCCEEDED'})):
        raise CoreError('recovery_unsupported','Running or independently cancelled work cannot be recovered')
    if any(not s['capability'].startswith('plugin.') or s['source']!=('input' if i==0 else 'previous') for i,s in enumerate(p['proposal']['steps'])):
        raise CoreError('recovery_unsupported','Recovery requires a full pure-text rerun')
    if t['status']=='WAITING' and t['error'] not in {'plan_source_changed','rework_source_changed'}:
        raise CoreError('recovery_unsupported','This wait is not a source-feedback failure')
    actions=_known_actions(core,p,t)
    grant=core.db.one('SELECT * FROM grants WHERE id=?',(t['body']['grant_id'],))
    if not grant:raise CoreError('denied','Original authority receipt is missing')
    snapshot={'goal':{k:p[k] for k in ('id','revision','request','proposal','cancel','status','task_id')},
        'task':{k:t[k] for k in ('id','revision','body','bindings','status','cancel','spent','error')},
        'actions':actions,'grant':grant,
        'feedback':core.db.one('SELECT id,digest FROM completion_feedback WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 1',(t['id'],))}
    return p,t,snapshot


def _edge_snapshot(core,edge):
    if edge['kind']=='recovery':
        r=checkpoint(core,edge);p,t,snapshot=_target_snapshot(core,edge['parent_goal'],retired=r['retired_task'])
        accepted=core.db.one('SELECT body FROM task_acceptance WHERE task_id=?',(t['id'],))
        if not accepted or digest(decode(accepted['body']))!=r['parent_acceptance']:
            raise CoreError('rework_source_changed','Retired acceptance changed')
        return snapshot,r['parent_state']
    p,_,_,snapshot=work_revisions.source_snapshot(core,edge['parent_goal'],1)
    _known_actions(core,p,core.tasks.get(p['task_id']))
    return snapshot,edge['source_digest']


def validate_path(core,ident):
    _,descending=quote_rework.lineage(core,ident);edges=list(reversed(descending));overrides=_coverage(core,edges)
    if not any(e['kind']=='recovery' for e in edges):raise CoreError('recovery_unsupported','No recovery boundary')
    for edge in edges:
        snapshot,original=_edge_snapshot(core,edge)
        if digest(snapshot)!=overrides.get(edge['goal_id'],original):
            raise CoreError('rework_source_changed','Recovery observations changed; old boundaries remain frozen')
    p=Plans(core.db).get(ident)
    if p['task_id']:
        row=core.db.one('SELECT body FROM task_acceptance WHERE task_id=?',(p['task_id'],))
        if not row or not any(r['check']=='quote_recovery' for r in decode(row['body'])['criteria']):
            raise CoreError('rework_source_changed','Recovery task requires its frozen recovery acceptance')


def _feedback_transition(core,snapshot,expected):
    current=digest(snapshot)
    if current==expected:return {'previous_digest':expected,'current_digest':current,'feedback_changed':False}
    history=core.db.all('SELECT id,digest FROM completion_feedback WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 17',(snapshot['task']['id'],))
    for prior in [None,*history]:
        if digest({**snapshot,'feedback':prior})==expected:
            return {'previous_digest':expected,'current_digest':current,'feedback_changed':True,
                'previous_feedback':prior['id'] if prior else None,'current_feedback':snapshot['feedback']['id'] if snapshot['feedback'] else None}
    raise CoreError('recovery_unprovable','Cannot prove feedback is the only changed source component')


def _accepted(core,p,review):
    row=core.db.one('SELECT body FROM task_acceptance WHERE task_id=?',(p['task_id'],))
    rules=decode(row['body']) if row else {}
    expected=review['acceptance']
    # Never silently discard additional criteria or requirements from an API client.
    if rules.get('criteria')!=expected['criteria'] or rules.get('requirements')!=expected['requirements']:
        raise CoreError('recovery_unsupported','Recovery requires the exact source-aware domain acceptance')
    body=core.tasks.get(p['task_id'])['body']
    source_checks.validate(body,rules['criteria'][0],review)
    if body['goal']!=p['request']['goal'] or body['steps'][0]['arguments'].get('text')!=p['proposal']['input_text']:
        raise CoreError('rework_source_changed','Frozen task differs from its full request')
    return rules


def analyze(core,value):
    if type(value['revision']) is not int or type(value['work_revision']) is not int:
        raise CoreError('work_conflict','Expected current Goal and Work revisions')
    core.gate.require_running();p,t,parent=_target_snapshot(core,value['id']);owner=core.works.owner(p['id'])
    if (not owner or owner['cancelled'] or owner['current_goal']!=p['id'] or owner['revision']!=value['work_revision']
            or owner['assistant_id']!=core.identity.describe()['assistant_id'] or p['revision']!=value['revision']):
        raise CoreError('work_conflict','Only the current responsible version can recover')
    if core.works.link(p['id'])['ordinal']>=4:raise CoreError('work_limit','Recovery shares the original version bound')
    for step in t['body']['steps']:GrantStore.authorize(core.db.connection,t['body'],step['capability'])
    _,descending=quote_rework.lineage(core,p['id']);edges=list(reversed(descending));overrides=_coverage(core,edges)
    sources=[];changes=[]
    for edge in edges:
        snapshot,original=_edge_snapshot(core,edge)
        transition=_feedback_transition(core,snapshot,overrides.get(edge['goal_id'],original))
        sources.append({'edge_goal':edge['goal_id'],'parent_goal':edge['parent_goal'],**transition})
        if transition['feedback_changed']:
            feedback=core.db.one('SELECT kind,note FROM completion_feedback WHERE id=?',(transition['current_feedback'],))
            changes.append({'goal_id':edge['parent_goal'],'feedback_id':transition['current_feedback'],**(feedback or {})})
    if not changes:raise CoreError('recovery_unnecessary','No proven feedback-only source invalidation')
    # Reconstruct frozen requirements only after the independent source comparison.
    # These reviews do not revalidate or rewrite the historical completion verdict.
    root=Plans(core.db).get(edges[0]['parent_goal'])
    from host.quote_sources import review as root_review
    _accepted(core,root,root_review(core,root['id'],changes=True))
    for edge in edges:
        q=Plans(core.db).get(edge['goal_id']);_accepted(core,q,quote_rework._replay(core,q['id']))
    review=quote_rework._replay(core,p['id']);accepted=_accepted(core,p,review)
    budget=core.works.projection(p['id'])['budget'];units=len(p['proposal']['steps'])+1
    if not budget['enforced'] or budget['integrity']!='complete' or budget['unresolved_tasks']:
        raise CoreError('work_budget_invalid','Recovery requires intact shared budget evidence')
    allocation=core.db.one('SELECT units FROM work_allocations WHERE task_id=?',(t['id'],))
    if not allocation:raise CoreError('work_budget_invalid','Original allocation missing')
    release=max(0,allocation['units']-t['spent']) if t['status']!='SUCCEEDED' else 0
    available=budget['limit_units']-budget['committed_units']+release
    if available<units:raise CoreError('work_budget_exhausted','Same Work budget cannot cover a full recovery')
    result={'schema':SCHEMA,'goal_id':p['id'],'revision':p['revision'],'work_revision':owner['revision'],
        'parent_state':digest(parent),'parent_acceptance':digest(accepted),'requirements_binding':review['binding'],
        'sources':sources,'feedback_changes':changes,'parent_task_status':t['status'],
        'retire_pending_task':t['status']!='SUCCEEDED','spent_units':budget['spent_units'],
        'release_units':release,'required_units':units,'available_after_retirement':available,'budget_revision':budget['revision'],
        'scope':'feedback_only_full_rerun','ready':True}
    return {**result,'analysis_digest':digest(result)}


def create(core,value):
    if (not isinstance(value['request_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',value['request_id'])
            or not isinstance(value['note'],str) or not 1<=len(value['note'].strip())<=1000
            or value['keep_requirements'] is not True):
        raise CoreError('recovery_invalid','Explicitly retain all requirements and describe the recovery')
    fingerprint=digest(value);plans=Plans(core.db)
    with admission(core.root),goal_context.LOCK,core.db.transaction() as tx:
        old=core.db.one('SELECT goal_id,request_digest FROM work_revisions WHERE request_id=?',(value['request_id'],))
        if old:
            if old['request_digest']!=fingerprint:raise CoreError('conflict','Recovery request ID changed')
            return {'id':old['goal_id'],'existing':True}
        checked=analyze(core,value)
        if value['analysis_digest']!=checked['analysis_digest']:raise CoreError('recovery_analysis_changed','Analyze current recovery evidence again')
        p,t,_=_target_snapshot(core,value['id']);ctx=goal_context.get(core,p['id'])
        catalog=[r for r in capabilities.catalog(core,ctx['scope'] if ctx else 'personal') if r['capability'].startswith('plugin.')]
        proposal={**p['proposal'],'summary':value['note'],'questions':[]};validate_proposal(proposal,catalog)
        req={**p['request'],'request_id':'work-'+digest(value['request_id'])[:40],'input_text':proposal['input_text']}
        ident,fresh=plans.create(req,catalog,p['routes'],tx)
        if not fresh:raise CoreError('conflict','Recovery Goal request already used')
        tx.execute("UPDATE goal_plans SET proposal=?,status='REVIEW' WHERE id=?",(canonical(proposal),ident))
        if ctx:tx.execute('INSERT INTO goal_context(goal_id,scope,enabled,view) VALUES(?,?,?,?)',(ident,ctx['scope'],ctx['enabled'],canonical(ctx['view'])))
        core.grants.revoke(t['body']['grant_id'],transaction=tx)
        core.grants.revoke(planning_key(p)+'-plan',transaction=tx)
        if checked['retire_pending_task']:
            core.tasks.cancel(t['id'],transaction=tx)
            tx.execute("UPDATE goal_plans SET cancel=1,status='CANCELLED',revision=revision+1 WHERE id=?",(p['id'],))
        _,_,retired=_target_snapshot(core,p['id'],retired=checked['retire_pending_task'])
        record={'schema':SCHEMA,'parent_goal':p['id'],'parent_task':t['id'],'retired_task':checked['retire_pending_task'],
            'parent_state_before':checked['parent_state'],'parent_state':digest(retired),'parent_acceptance':checked['parent_acceptance'],
            'sources':checked['sources'],'requirements_binding':checked['requirements_binding'],'analysis_digest':checked['analysis_digest']}
        core.works.save_recovery(ident,record,tx)
        core.works.append(p['id'],ident,value['work_revision'],'recovery',value['note'],1,digest(record),value['request_id'],fingerprint,tx)
        core.db.event(tx,t['id'],'work.recovery_created',{'goal_id':ident,'parent_goal':p['id'],'checkpoint':digest(record),
            'old_task_retired':record['retired_task'],'confirmed_actions_retained':len(retired['actions'])})
        return {'id':ident,'existing':False}
