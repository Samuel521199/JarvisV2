"""Standing mandates coordinate the original goal admission, scheduler and receipts.

No model is called here. Only frozen, reviewed, local pure-text tool plans may
repeat; requests for a new capability return to existing goal/growth review.
"""
import re
import threading
import time
from control.application_runtime import require_accepting, accepting
from control.execution import admission
from control.paths import child
from host.core import Core
from host import goals, goal_context
from host.capabilities import require
from modules.task_resource.plans import Plans
from modules.task_resource.standing import Standing,policy,quiet,timestamp,acceptance
from sdk.protocol import CoreError,canonical,decode,digest

LOCK=threading.RLock()
TERMINAL={'DONE','CANCELLED'}


def exists(core):return core.db.one("SELECT 1 FROM meta WHERE key='standing_schema'") is not None


def snapshot(core,ident):
    if not isinstance(ident,str) or not re.fullmatch('goal-[a-f0-9]{32}',ident):raise CoreError('standing_plan','Expected an existing source goal')
    p=Plans(core.db).get(ident);proposal=p['proposal']
    goal_context.check(core,ident)
    from host.work_revisions import check as check_source_work
    check_source_work(core,ident,execution=True)
    if p['task_id']:
        feedback=core.db.one('SELECT kind FROM completion_feedback WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 1',(p['task_id'],))
        if feedback and feedback['kind']=='reject':raise CoreError('experience_changed','Source work feedback was rejected or withdrawn')
    if p['cancel'] or not proposal or proposal['questions'] or not proposal['steps']:
        raise CoreError('standing_plan','Resolve and review the source plan first')
    if any(not step['capability'].startswith('plugin.') for step in proposal['steps']):
        raise CoreError('standing_scope','Only local pure-text tools may run under a standing mandate')
    used={s['capability'] for s in proposal['steps']};refs=[r for r in p['catalog'] if r['capability'] in used]
    if {r['capability'] for r in refs}!=used:raise CoreError('standing_plan','Plan references an unavailable capability')
    for ref in refs:require(core,ref)
    owner=core.works.owner(ident);origin=owner['root_goal'] if owner else ident
    link=core.db.one('SELECT chat_id FROM chat_goals WHERE goal_id=?',(origin,))
    return {'id':ident,'root_goal':origin,'request':p['request'],'proposal':proposal,'catalog':refs,'chat_id':link['chat_id'] if link else None}


def templates(core,value):
    if not isinstance(value,list) or not 1<=len(value)<=8 or any(not isinstance(i,dict) or set(i)!={'goal_id','acceptance'} for i in value):
        raise CoreError('standing_plan','Choose one to eight ordered source goals and acceptance rules')
    result=[]
    for item in value:
        snap=snapshot(core,item['goal_id']);rules=item['acceptance']
        if not isinstance(rules,dict) or rules.get('coverage')!='complete' or not rules.get('criteria') or not rules.get('requirements'):
            raise CoreError('standing_acceptance','Declare requirements and checks; tool success alone is not completion')
        # The original Completion validator is the authority at admission.
        acceptance(rules,snap['proposal']['steps'])
        result.append({**snap,'acceptance':rules,'fingerprint':digest(snap)})
    return result


def read(root):
    core=Core(root)
    try:
        if not exists(core):return {'schema':'jarvis.standing-work.v1','items':[],'cloud_model_calls':0}
        store=Standing(core.db)
        return {'schema':'jarvis.standing-work.v1','items':[{**r,'runs':store.runs(r['id'])[:5]} for r in store.listing()],
                'cloud_model_calls':0,'scope':'reviewed local text plans; fixed inputs, not live source polling'}
    finally:core.close()


def command(root,value):
    fields={'create':{'request_id','title','plans','policy'},'edit':{'request_id','id','revision','title','plans','policy'},
            'approve':{'request_id','id','revision'},'pause':{'request_id','id','revision'},'resume':{'request_id','id','revision'},
            'cancel':{'request_id','id','revision'},'feedback':{'request_id','id','revision','run_id','kind','note'}}
    fields['abandon_run']={'request_id','id','revision'}
    if not isinstance(value,dict) or not isinstance(value.get('action'),str) or value['action'] not in fields or set(value)!={'action'}|fields[value['action']]:raise CoreError('standing_invalid','Unexpected standing-work command')
    request=value['request_id']
    if not isinstance(request,str) or not re.fullmatch('[A-Za-z0-9_-]{8,80}',request):raise CoreError('standing_invalid','Provide a bounded request ID')
    if value['action']!='create' and (not isinstance(value.get('id'),str) or not re.fullmatch('standing-[a-f0-9]{32}',value['id'])):
        raise CoreError('standing_invalid','Expected an existing standing-work identity')
    with LOCK,admission(root):
        if value['action'] not in {'cancel','pause'}:require_accepting(root)
        core=Core(root)
        try:
            if value['action'] not in {'cancel','pause'}:core.gate.require_running()
            store=Standing(core.db) if exists(core) else None;signature=digest(value);old=store.operation(request,signature) if store else None
            if old:return old
            action=value['action'];now=time.time()
            if action in {'create','edit'}:
                title=value['title']
                if not isinstance(title,str) or not 1<=len(title.strip())<=200:raise CoreError('standing_invalid','A short title is required')
                config=policy(value['policy']);plans=templates(core,value['plans'])
            if store is None:
                if action!='create':raise CoreError('standing_missing','No standing work exists')
                store=Standing(core.db)
            if action=='create':
                if len(store.listing())>=100:raise CoreError('standing_capacity','Standing work limit reached')
                row={'id':'standing-'+digest(request)[:32],'revision':1,'status':'DRAFT','granted':False,'title':title,'plans':plans,'policy':config,
                     'next_at':timestamp(config['start_at']),'runs_started':0,'reserved_units':0,'current_run':None,
                     'notice':None,'notice_revision':0,'notified_at':0,'notice_pending':False,'error':None,'created':now}
            else:
                row=store.get(value['id'])
                if type(value['revision']) is not int or row['revision']!=value['revision']:raise CoreError('conflict','Standing work changed; refresh before editing')
                if action=='feedback':
                    if value['kind'] not in {'accept','reject','withdraw'} or not isinstance(value['note'],str) or not 1<=len(value['note'].strip())<=1000:
                        raise CoreError('standing_invalid','Provide explicit feedback and a note')
                    run=next((r for r in store.runs(row['id']) if r['id']==value['run_id']),None)
                    if not run or run['status'] not in {'VERIFIED','NEEDS_REVIEW'}:raise CoreError('standing_feedback','Only a completed result may receive feedback')
                    if value['kind']=='accept' and run['status']!='VERIFIED':raise CoreError('standing_feedback','Feedback cannot override failed acceptance')
                    if value['kind']!='accept':
                        # Durable revocation precedes optional feedback projection.
                        # A crash cannot leave dependent mandates automatically active.
                        if row['status']!='CANCELLED':row.update(status='PAUSED',error='standing_feedback_review')
                        run['withdrawal_requested']={'kind':value['kind'],'note':value['note'],'request_id':request}
                        invalid={p['fingerprint'] for p in row['plans']}
                        with core.db.transaction():
                            store.put(row);store.run(run)
                            for dependent in store.listing():
                                if (dependent['id']!=row['id'] and dependent['status'] not in {'CANCELLED','DRAFT'}
                                    and dependent.get('error')!='standing_feedback_review' and any(p['fingerprint'] in invalid for p in dependent['plans'])):
                                    dependent.update(status='PAUSED',error='standing_feedback_review',revision=dependent['revision']+1)
                                    store.put(dependent)
                    from host.completion import command as completion_command,projection as completion_projection
                    for goal_id in run['goals']:
                        goal=Plans(core.db).get(goal_id)
                        if not goal['task_id']:continue
                        checked=completion_projection(core,goal['task_id'])
                        if value['kind']=='accept' and checked['state'] not in {'VERIFIED','ACCEPTED'}:
                            raise CoreError('standing_feedback','The result evidence changed; acceptance must be checked again')
                        completion_command(core,{'action':'completion_feedback','id':goal['task_id'],'request_id':request,
                            'fingerprint':checked['fingerprint'],'kind':'reject' if value['kind']=='withdraw' else value['kind'],
                            'note':value['note']})
                    run['feedback']={'kind':value['kind'],'note':value['note'],'at':now};run['updated']=now
                    # Candidate only, source-bound and never written as a personal fact.
                    run['learning_candidate']={'state':'PENDING' if value['kind']=='accept' else 'WITHDRAWN','scope':'work-method',
                        'source_run':run['id'],'note':value['note'],'automatic_use':False,
                        'conditions':[{'source_goal':p['id'],'fingerprint':p['fingerprint'],'tool_versions':p['catalog'],'acceptance':p['acceptance']} for p in row['plans']]}
                    store.run(run)
                elif action=='edit':
                    if row['status'] not in {'DRAFT','PAUSED'} or row['current_run']:raise CoreError('standing_busy','Pause and finish the current occurrence before replacing its plan')
                    row.update(title=title,plans=plans,policy=config,status='DRAFT',granted=False,next_at=timestamp(config['start_at']),error=None)
                elif action in {'approve','resume'}:
                    if row['status'] not in ({'DRAFT','PAUSED'} if action=='approve' else {'PAUSED','NEEDS_INPUT'}):raise CoreError('standing_state','This work cannot be enabled in its current state')
                    if action=='approve' and row['granted'] or action=='resume' and not row['granted']:
                        raise CoreError('standing_state','Use explicit initial approval or resume an existing grant')
                    if action=='resume' and row['error']=='standing_feedback_review':raise CoreError('standing_review_required','Rejected or withdrawn experience needs an edited plan and renewed approval')
                    for p in row['plans']:
                        if digest(snapshot(core,p['id']))!=p['fingerprint']:raise CoreError('standing_source_changed','Source plan, permission or context changed; review an edited mandate')
                    row.update(status='ACTIVE',error=None,granted=True)
                elif action=='pause':
                    if row['status'] in TERMINAL:raise CoreError('standing_state','Terminal standing work cannot be paused')
                    row['status']='PAUSED'
                elif action=='cancel':
                    row['status']='CANCELLED';store.save(row)
                    for run in store.runs(row['id']):
                        if run['status']=='RUNNING':
                            for attempt in run['attempts'].values():
                                if attempt['goal_id']:goals.command(root,{'action':'cancel','id':attempt['goal_id']})
                            run.update(status='CANCELLED',updated=now);store.run(run)
                elif action=='abandon_run':
                    if row['status'] not in {'PAUSED','NEEDS_INPUT'} or not row['current_run']:raise CoreError('standing_state','Pause an unfinished occurrence first')
                    run=next(r for r in store.runs(row['id']) if r['id']==row['current_run'])
                    for attempt in run['attempts'].values():
                        if attempt['task_id'] and any(a['status']=='UNKNOWN' for a in core.tasks.actions(attempt['task_id'])):
                            raise CoreError('unknown_effect','Reconcile unknown effects before replacing the occurrence')
                        if attempt['goal_id']:goals.command(root,{'action':'cancel','id':attempt['goal_id']})
                    run.update(status='CANCELLED',updated=now);store.run(run);row.update(status='PAUSED',current_run=None,error='standing_feedback_review')
                row['revision']+=1
            with core.db.transaction():
                store.put(row);result={'id':row['id'],'revision':row['revision'],'status':row['status']};store.record(request,signature,result)
                core.db.event(core.db.connection,None,'standing.'+action,{'id':row['id'],'revision':row['revision'],'status':row['status'],'request_id':request})
            return result
        finally:core.close()


def _finish(store,row,run,status,reason,now):
    run.update(status=status,error=reason,updated=now);row.update(current_run=None,error=reason,
        notice={'run_id':run['id'],'status':status,'reason':reason},notice_pending=True)
    interval=row['policy']['interval_seconds']
    # Coalesce sleep/offline missed intervals. Never replay a catch-up burst.
    row['next_at']=row['next_at']+max(1,int((now-row['next_at'])//interval)+1)*interval if interval else now
    if status=='NEEDS_REVIEW':row['status']='NEEDS_INPUT'
    elif not interval or row['runs_started']>=row['policy']['max_runs']:row['status']='DONE'
    store.save(row,run)


def _tick(root,core,store,row,now):
    if row['notice_pending'] and not quiet(row['policy'],now) and now-row['notified_at']>=row['policy']['notification_interval_seconds']:
        row.update(notice_pending=False,notified_at=now,notice_revision=row['notice_revision']+1);store.save(row)
    if row['status']!='ACTIVE':return
    if row['error'] is not None: return
    for plan in row['plans']:
        if digest(snapshot(core,plan['id']))!=plan['fingerprint']:raise CoreError('standing_source_changed','Source changed; review before continuing')
    if quiet(row['policy'],now):return
    runs=store.runs(row['id']);run=next((r for r in runs if r['id']==row['current_run']),None)
    if run is None:
        if row['next_at']>now:return
        if row['runs_started']>=row['policy']['max_runs']:row['status']='DONE';store.save(row);return
        run=store.begin(row,now)
    if run['next_at']>now:return
    plan=row['plans'][run['cursor']];key=str(run['cursor'])+'-'+str(run['attempt']);units=len(plan['proposal']['steps'])+1
    store.reserve(row,run,key,units,now);attempt=run['attempts'][key]
    if not attempt['goal_id']:
        request={**plan['request'],'request_id':'standing-'+digest([run['id'],key])[:40]}
        goal=goals.command(root,{'action':'create','request':request})['id'];attempt['goal_id']=goal
        with core.db.transaction() as tx:
            tx.execute('INSERT OR IGNORE INTO standing_children VALUES(?,?,?,?)',(goal,row['id'],run['id'],plan['id']))
            context=goal_context.get(core,plan['id'])
            if context:
                tx.execute('INSERT OR IGNORE INTO goal_context VALUES(?,?,?,?,?)',(goal,context['scope'],int(context['enabled']),canonical(context['view']),canonical(context['history'])))
        if goal not in run['goals']:run['goals'].append(goal)
        store.save(row,run)
    ident=attempt['goal_id'];p=Plans(core.db).get(ident)
    if p['status']=='NEW':goals.command(root,{'action':'edit','id':ident,'revision':p['revision'],'proposal':plan['proposal']});p=Plans(core.db).get(ident)
    if not p['task_id']:
        accepted=goals.command(root,{'action':'approve_and_run','id':ident,'revision':p['revision'],'acceptance':plan['acceptance'],'budget_limit':units})
        attempt['task_id']=accepted['task_id'];store.save(row,run)
    else:attempt['task_id']=p['task_id']
    task=core.tasks.get(attempt['task_id']);actions=core.tasks.actions(task['id'])
    if any(a['status'] in {'UNKNOWN','DISPATCHING'} for a in actions) and task['status']!='RUNNING':
        raise CoreError('unknown_effect','Unknown task effect must be reconciled; no replay')
    if task['status'] in {'READY','RUNNING'}:return
    if task['status']=='SUCCEEDED':
        from host.session_workspace import deliver_task
        deliver_task(core,task['id'])
        from host.completion import projection
        checked=projection(core,task['id'])
        if checked['state'] not in {'VERIFIED','ACCEPTED'} or not checked.get('requirement_coverage',{}).get('complete'):
            _finish(store,row,run,'NEEDS_REVIEW','Result needs correction; use original goal analysis/rework',now);return
        run['cursor']+=1;run['attempt']=0;run['retries_used']=0;run['updated']=now
        if run['cursor']==len(row['plans']):_finish(store,row,run,'VERIFIED',None,now)
        else:store.save(row,run)
    elif task['status'] in {'FAILED','WAITING'}:
        if any(a['status']=='UNKNOWN' for a in actions):raise CoreError('unknown_effect','Reconcile unknown effect before retry')
        if task.get('error') in {'denied','revoked','stopped','goal_context_changed','experience_changed'}:raise CoreError('standing_permission','Original task permission/source changed')
        if (task['status']=='WAITING' and task.get('error') in {'module_disabled','package_unavailable'} and task['deadline']>now
                and run.get('retries_used',0)+1<row['policy']['max_attempts']):
            core.tasks.resume(task['id'])
            from modules.task_resource.scheduling import Scheduling
            Scheduling(core.db).enqueue([task['id']]);run.update(next_at=now+5,updated=now,retries_used=run.get('retries_used',0)+1);store.save(row,run)
        elif run.get('retries_used',0)+1<row['policy']['max_attempts']:
            run.update(attempt=run['attempt']+1,retries_used=run.get('retries_used',0)+1,next_at=now+5*2**run['attempt'],error=task.get('error'),updated=now);store.save(row,run)
        else:_finish(store,row,run,'NEEDS_REVIEW',task.get('error') or 'retry_exhausted',now)
    else:raise CoreError('standing_task_stopped','Original task stopped; explicit review required')


def advance(root,*,foreground=False,now=None):
    if foreground or not accepting(root):return
    now=time.time() if now is None else now
    with LOCK:
        core=Core(root)
        try:
            if core.gate.state()!='ready' or not exists(core):return
            store=Standing(core.db)
            # One cursor per mandate, at most two admissions per pump. Existing
            # TaskRunner owns execution slots, conflicts and memory reserves.
            candidates=sorted(store.listing(),key=lambda r:(r.get('checked_at',0),r['next_at']))
            processed=0
            for row in candidates[:100]:
                if processed>=2:break
                if row['status']=='ACTIVE' and (row['current_run'] or row['next_at']<=now):
                    processed+=1;row['checked_at']=now;store.save(row)
                try:_tick(root,core,store,row,now)
                except CoreError as error:
                    row.update(status='NEEDS_INPUT',error=error.code,notice_pending=True,
                               notice={'status':'NEEDS_REVIEW','reason':error.code,'run_id':row['current_run']})
                    store.save(row)
        finally:core.close()


def projection(root):
    core=Core(root);items=[];hidden=set()
    try:
        if not exists(core):return items,hidden
        rows=Standing(core.db).listing()
        hidden={r['task_id'] for r in core.db.all('SELECT p.task_id FROM standing_children c JOIN goal_plans p ON p.id=c.goal_id WHERE p.task_id IS NOT NULL')}
    finally:core.close()
    for row in rows:
        state=({'ACTIVE':'running' if row['current_run'] else 'waiting','PAUSED':'waiting','NEEDS_INPUT':'needs_input','DRAFT':'needs_input','DONE':'finished','CANCELLED':'cancelled'})[row['status']]
        if row['notice'] and not row['notice_pending'] and row['status']=='ACTIVE' and not row['current_run']:state='finished'
        items.append({'id':row['id'],'source':'standing','title':row['title'],'state':state,'raw_status':row['status'],
            'reason':row['error'] or ('等待明确核对并启用' if row['status']=='DRAFT' else '固定计划；已执行 '+str(row['runs_started'])+' 次；授权状态 '+row['status']),
            'result_revision':row['notice_revision'],'notification_held':row['notice_pending'] or quiet(row['policy'],time.time()),
            'chat_id':next((p['chat_id'] for p in row['plans'] if p['chat_id']),None),
            'revision':row['revision'],'next_at':row['next_at'],'cancelable':row['status'] not in TERMINAL})
    return items,hidden
