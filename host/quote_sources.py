"""Compose bounded chat provenance without copying raw sources into audit storage."""
from host import goal_context
from host.memory_domains import chat_scope
from modules.dialogue.store import Dialogues
from modules.task_resource.plans import Plans
from modules.task_resource import source_checks, change_checks
from sdk.protocol import CoreError, decode, digest


def review(core, ident, *, changes=False):
    plans=Plans(core.db);p=plans.get(ident);goal_context.check(core,ident)
    proposal=p['proposal']
    if (not proposal or not proposal['steps'] or proposal['questions']
            or any(not s['capability'].startswith('plugin.') or s['source']!=('input' if i==0 else 'previous') for i,s in enumerate(proposal['steps']))):
        raise CoreError('acceptance_invalid','Source review requires a reviewed pure text chain')
    chain=[p];seen={ident};link=core.works.link(ident)
    if p['request_id'].startswith('work-') and not link:
        raise CoreError('plan_source_changed','Work source ancestry is missing')
    while link and link['parent_goal']:
        parent=link['parent_goal']
        if parent in seen or len(chain)>=4:raise CoreError('plan_source_changed','Source ancestry invalid')
        seen.add(parent);chain.append(plans.get(parent));link=core.works.link(parent)
        if not link:raise CoreError('plan_source_changed','Source ancestry missing')
    root=chain[-1];goal_context.check(core,root['id'])
    parts=[];issues=[];receipts=[];stages=[];stage_receipts=[]
    lineage=[]
    for entry in reversed(chain):
        ctx=goal_context.get(core,entry['id'])
        lineage.append({'id':entry['id'],'generation':entry['generation'],'request':digest(entry['request']),
                        'history':digest(ctx['history'] if ctx else [])})
    if changes and len(chain)>1:raise CoreError('acceptance_invalid','Change replay does not merge Work rework chains')
    if not changes and (len(chain)>1 or any(e['generation'] for e in chain)):
        issues.append({'code':'revisions_unreviewed','blocking':False})
    source_link=core.db.one('SELECT chat_id,turn_id FROM chat_goals WHERE goal_id=?',(root['id'],))
    if root['request_id'].startswith('chat-goal-') and not source_link:
        raise CoreError('plan_source_changed','Original conversation source link is missing')
    scope='direct_goal_only'
    if source_link:
        scope='linked_chat_sources';store=Dialogues(core.root)
        try:
            header=store.header(source_link['chat_id']);ctx=goal_context.get(core,root['id'])
            if header['archived'] or header['removed'] or not ctx or chat_scope(core.root,header)!=ctx['scope']:
                raise CoreError('plan_source_changed','Chat source scope is unavailable')
            turns=[(source_link['turn_id'],'goal',root['id'],0)]
            for entry in reversed(chain):
                amendments=core.db.all("SELECT turn_id,result FROM assistant_operations WHERE goal_id=? AND kind='amend' ORDER BY turn_id LIMIT 5",(entry['id'],))
                if len(amendments)>3:raise CoreError('plan_source_changed','Source amendment bound exceeded')
                for r in amendments:
                    result=decode(r['result']) if changes else {}
                    if changes and (result.get('id')!=ident or type(result.get('generation')) is not int):
                        raise CoreError('plan_source_changed','Accepted change generation is missing')
                    turns.append((r['turn_id'],'amend',entry['id'],result.get('generation',0)))
            if changes:
                if (len(ctx['history'])!=p['generation'] or [h['generation'] for h in ctx['history']]!=list(range(p['generation']))
                        or sorted(t[3] for t in turns)!=list(range(p['generation']+1))):
                    raise CoreError('acceptance_invalid','Every generation needs an accepted chat source')
                turns.sort(key=lambda t:t[3])
                requests=[h['request'] for h in ctx['history']]+[p['request']]
            seen_turns=[];last_created=None
            for turn_id,kind,target,generation in turns:
                t=store.turn(turn_id);request=decode(t['request']);action=decode(t['assistant_action']) if t['assistant_action'] else {}
                if digest(request)!=t['digest']:
                    raise CoreError('plan_source_changed','Conversation request integrity changed')
                view=decode(t['memory_context']) if t['memory_context'] else {}
                if (t['chat_id']!=header['id'] or t['status']!='SUCCEEDED' or t['cancel'] or view.get('redacted')
                        or action.get('kind')!=kind or kind=='amend' and action.get('target')!=target):
                    raise CoreError('plan_source_changed','Linked source turn is no longer valid')
                if kind=='goal':
                    initial=ctx['history'][0]['request'] if ctx['history'] else root['request']
                    if action.get('goal')!=initial['goal'] or action.get('input_text')!=initial['input_text']:
                        raise CoreError('plan_source_changed','Initial source action changed')
                prior=bool(store.db.execute("SELECT 1 FROM turns WHERE chat_id=? AND created<? AND status='SUCCEEDED' LIMIT 1",(header['id'],t['created'])).fetchone())
                if changes:
                    expected=requests[generation]
                    if action.get('goal')!=expected['goal'] or action.get('input_text')!=expected['input_text']:
                        raise CoreError('plan_source_changed','Accepted change action differs from recorded generation')
                    if last_created is not None and t['created']<=last_created:raise CoreError('plan_source_changed','Change source order is inconsistent')
                    prior_ids=sorted(r['id'] for r in store.db.execute("SELECT id FROM turns WHERE chat_id=? AND created<=? AND id!=? AND status='SUCCEEDED' LIMIT 6",(header['id'],t['created'],turn_id)).fetchall())
                    if prior_ids!=sorted(seen_turns) or t['context_count']!=2*len(seen_turns)+1:
                        issues.append({'code':'prior_context_unreviewed','blocking':False,'source':turn_id})
                    stages.append({'generation':generation,'turn_id':turn_id,'request':request,'goal':expected['goal'],'input_text':expected['input_text']})
                    stage_receipts.append({'generation':generation,'turn_id':turn_id,'prior_ids':prior_ids,'reply':digest(t['reply'])})
                    seen_turns.append(turn_id);last_created=t['created']
                elif prior or t['context_count']>1:issues.append({'code':'prior_context_unreviewed','blocking':False,'source':turn_id})
                if view.get('dependencies') or view.get('facts') or t['guidance']:
                    issues.append({'code':'background_unreviewed','blocking':False,'source':turn_id})
                if request.get('reference_image') or request.get('reference_images'):
                    issues.append({'code':'image_unreviewed','blocking':False,'source':turn_id})
                parts.append({'id':turn_id+':text','kind':'user','name':'用户原话','text':request['text']})
                if request.get('requirements','').strip():
                    parts.append({'id':turn_id+':requirements','kind':'requirements','name':'会话要求','text':request['requirements']})
                for i,item in enumerate(request.get('attachments',[])):
                    parts.append({'id':turn_id+':attachment:'+str(i),'kind':'reference','name':item['name'],'text':item['text']})
                if changes:
                    for part in parts:
                        if 'turn_id' not in part:part['turn_id']=turn_id
                receipts.append({'id':turn_id,'kind':kind,'request':digest(request),'action':digest(action),
                                 'view':digest(view),'guidance':t['guidance'],'context_count':t['context_count'],'prior':prior})
        finally:store.close()
    elif any(core.db.one("SELECT 1 FROM assistant_operations WHERE goal_id=? AND kind='amend'",(e['id'],)) for e in chain):
        raise CoreError('plan_source_changed','Amended conversation source link is missing')
    receipt=digest({'lineage':lineage,'link':source_link,'turns':receipts})
    policy=change_checks if changes else source_checks
    if changes:
        if not source_link:raise CoreError('acceptance_invalid','Explicit change review requires linked chat sources')
        result=policy.analyze(p['request']['goal'],proposal['input_text'],stages,parts,digest({'source':receipt,'stages':stage_receipts}),issues)
    else:result=policy.analyze(p['request']['goal'],proposal['input_text'],parts,receipt,issues,scope)
    return {**result,'goal_id':ident,'revision':p['revision'],
            'acceptance':policy.acceptance(result,'step-'+str(len(proposal['steps'])))}


def provider(core, ident=None, *, changes=False, rework=False, recovery=False):
    def fetch(task_id, body):
        row=core.db.one('SELECT id FROM goal_plans WHERE task_id=?',(task_id,)) if ident is None else {'id':ident}
        if not row:raise CoreError('plan_source_changed','Source checked task must have a goal')
        if rework or recovery:
            from host.quote_rework import review as rework_review
            result=rework_review(core,row['id'],recovery=recovery)
        else:result=review(core,row['id'],changes=changes)
        p=Plans(core.db).get(row['id'])
        if p['request']['goal']!=body['goal'] or p['proposal']['input_text']!=body['steps'][0]['arguments'].get('text'):
            raise CoreError('plan_source_changed','Frozen task differs from source-reviewed goal')
        return result
    return fetch


def check_task(core, task_id):
    if not core.db.one("SELECT 1 FROM sqlite_master WHERE type='table' AND name='task_acceptance'"):return
    accepted=core.db.one('SELECT body FROM task_acceptance WHERE task_id=?',(task_id,))
    rules=decode(accepted['body']) if accepted else {}
    conditions=[c for c in rules.get('criteria',[]) if c['check'] in {'quote_sources','quote_changes','quote_rework','quote_recovery'}]
    if not conditions:return
    body=core.tasks.get(task_id)['body']
    try:
        for check in {c['check'] for c in conditions}:
            checked=provider(core,changes=check=='quote_changes',rework=check=='quote_rework',recovery=check=='quote_recovery')(task_id,body)
            for rule in conditions:
                if rule['check']==check:source_checks.validate(body,rule,checked)
    except CoreError as exc:raise CoreError('plan_source_changed','Source review changed before execution') from exc
