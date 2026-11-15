"""One authorized repair returns through the existing work, budget and receipt ledgers."""
import time
from control.application_runtime import require_accepting
from control.policy.grants import GrantStore
from control.recovery.gate import RunLock
from host.core import Core
from host import work_revisions, rework_impact, goals
from host.completion import refresh
from modules.task_resource import repair_returns as records, lesson_checks, quote_checks, quote_request, coverage
from modules.task_resource.completion import Completion
from modules.task_resource.plans import Plans
from modules.task_resource.work_budgets import WorkBudgets
from sdk.protocol import CoreError, decode, digest


def authorize(core, source_task, ident, draft, tx):
    old=records.get(core.db,ident)
    if old:return old  # Never renew a deadline, cancellation or one-shot allowance.
    assessment=refresh(core,source_task,transaction=tx)
    p,text,fingerprint,_=work_revisions.source_snapshot(core,assessment['learning_candidate']['goal_id'],1)
    rules=Completion(core.db).criteria(source_task)['rules']
    if (len(p['proposal']['steps'])!=1 or not rules or rules['coverage']!='complete' or not rules.get('requirements')
        or any(r['step_id']!='step-1' or r['check'] not in {'text_equals','text_contains','quote_selection','quote_request'} for r in rules['criteria'])
        or not coverage.evaluate(rules,[{'id':r['id'],'status':'passed'} for r in rules['criteria']])['complete']):
        raise CoreError('repair_return_unsupported','Automatic return requires a single pure stage and fully inheritable acceptance')
    run=core.development.get(ident)
    if run['cancel'] or run['status'] not in {'READY','WAITING'} or run['deadline']<=time.time():
        raise CoreError('repair_return_state','Repair is no longer eligible for a new mandate')
    value={'development_id':ident,'source_task':source_task,'source_goal':p['id'],'source_digest':fingerprint,
           'acceptance_digest':digest(rules),'purpose':draft['purpose'],'capability':draft['capability'],
           'deadline':run['deadline'],'status':'AUTHORIZED','child_goal':None,'child_task':None,
           'before_score':assessment['condition_score'],'max_returns':1,'error':None}
    check(core,value)
    return records.save(core.db,value,tx)


def check(core,value,*,closed=False):
    require_accepting(core.root);core.gate.require_running()
    current=records.get(core.db,value['development_id'])
    if current and current['status'] in {'CANCELLED','FAILED','REGRESSED','UNSUPPORTED'}:
        raise CoreError('cancelled','Repair return mandate is terminal')
    if not closed and value['deadline']<=time.time():raise CoreError('deadline','Repair return deadline expired')
    if digest(Completion(core.db).criteria(value['source_task'])['rules'])!=value['acceptance_digest']:
        raise CoreError('repair_source_changed','Original requirements changed')
    context=core.db.one('SELECT enabled FROM goal_context WHERE goal_id=?',(value['source_goal'],))
    if not context or not context['enabled']:raise CoreError('repair_source_changed','Source learning consent was withdrawn')
    if value.get('child_goal'):
        work_revisions.check(core,value['child_goal'],execution=not closed)
        owner=core.works.owner(value['child_goal'])
        if not owner or owner['cancelled']:raise CoreError('work_conflict','The returned work was cancelled')
        child=Plans(core.db).get(value['child_goal']);frozen=value['rework_request']
        if (child['request']['goal']!=frozen['goal'] or child['proposal']['input_text']!=frozen['proposal']['input_text']
            or child['proposal']['steps']!=frozen['proposal']['steps']):
            raise CoreError('repair_source_changed','Returned proposal changed after authorization')
        if child['task_id'] and core.tasks.get(child['task_id'])['bindings'].get(value['capability'])!=value['package_id']:
            raise CoreError('repair_source_changed','Returned task is not bound to the shadow-reviewed package')
        for tid in (value['source_task'],value.get('child_task')):
            if tid:
                grant=core.db.one('SELECT revoked FROM grants WHERE id=?',(core.tasks.get(tid)['body']['grant_id'],))
                if not grant or grant['revoked']:raise CoreError('denied','Business authority was revoked')
    else:
        _,_,fingerprint=work_revisions.source(core,value['source_goal'],1)
        if fingerprint!=value['source_digest']:raise CoreError('repair_source_changed','Original evidence changed')
        core._goal_memory_check(value['source_task'])
        task=core.tasks.get(value['source_task'])
        GrantStore.authorize(core.db.connection,task['body'],task['body']['steps'][0]['capability'])
        budget=WorkBudgets(core.db).projection(value['source_goal'])
        if not budget or not budget['enforced'] or budget['integrity']!='complete' or budget['available_units']<2:
            raise CoreError('work_budget_exhausted','An existing shared work budget must cover the return')
    if not closed and value.get('package_id') and core.development.get(value['development_id'])['status']=='SUCCEEDED':
        core.packages.require(value['capability'],value['package_id'])


def save(core,value,**changes):
    with core.db.transaction() as tx:return records.save(core.db,{**value,**changes},tx)


def verify_text(core,value,text):
    task=core.tasks.get(value['source_task']);rules=Completion(core.db).criteria(value['source_task'])['rules']
    oracle=lesson_checks.score(value['purpose'],task['body']['steps'][0]['arguments']['text'],text)
    checks=[]
    for rule in rules['criteria']:
        kind=rule['check']
        passed=(text==rule['expected']) if kind=='text_equals' else (rule['expected'] in text) if kind=='text_contains' else (
            (quote_request if kind=='quote_request' else quote_checks).verify(task['body'],rule,text)['status']=='passed')
        checks.append({'id':rule['id'],'passed':passed})
    if not oracle['passed'] or not all(c['passed'] for c in checks):
        raise CoreError('repair_actual_failed','Candidate failed the original input or frozen acceptance')
    return {'oracle':oracle,'checks':checks,'output_digest':digest(text),'acceptance_digest':value['acceptance_digest']}


def stop(core,value,error,status='FAILED'):
    # Retain original tools, work ancestry, failed evidence and spent budget.
    latest=records.get(core.db,value['development_id'])
    if latest and latest['status']=='CANCELLED':value=latest;status='CANCELLED';error='cancelled'
    run=core.development.get(value['development_id'])
    core.grants.revoke(run['spec']['grant_id'])
    if value.get('child_task'):core.grants.revoke(core.tasks.get(value['child_task'])['body']['grant_id'])
    package=value.get('package_id')
    if package:core.packages.quarantine(value['capability'],package)
    return save(core,value,status=status,error=error)


def evaluate(core,value):
    check(core,value,closed=True)
    p,_,_,snapshot=work_revisions.source_snapshot(core,value['child_goal'],1)
    if p['task_id']!=value['child_task']:raise CoreError('repair_source_changed','Child task changed')
    task=core.tasks.get(p['task_id'])
    if task['bindings'].get(value['capability'])!=value['package_id']:
        raise CoreError('repair_source_changed','Child package changed')
    result=refresh(core,p['task_id'])
    if (digest(result['acceptance']['rules'])!=value['acceptance_digest'] or not result['requirement_coverage']['complete']
        or not result['evidence_ready'] or result['state'] not in {'VERIFIED','ACCEPTED'}):
        raise CoreError('repair_actual_failed','Returned business task did not satisfy all original requirements')
    action=next(a for a in snapshot['actions'] if a['step_id']=='step-1')
    proof=verify_text(core,value,decode(action['result'])['text'])
    return {**proof,'task_id':p['task_id'],'fingerprint':result['fingerprint'],
            'condition_score':result['condition_score'],'score_delta':result['condition_score']-value['before_score'] if value['before_score'] is not None else None,
            'scope':'original_declared_conditions_and_local_oracle','general_intelligence_gain_proven':False}


def run(root,ident,*,interrupted=lambda:False):
    core=Core(root);value=None
    try:
        with RunLock(core.root,'repair-return'):
            value=records.get(core.db,ident)
            if not value:raise CoreError('repair_return_missing','No automatic return mandate')
            if value['status'] in records.TERMINAL-{'CLOSED'}:return value
            # A crash after standard rework creation is recovered by its durable request ID.
            if not value.get('child_goal') and value.get('rework_request'):
                row=core.db.one('SELECT goal_id FROM work_revisions WHERE request_id=?',(value['rework_request']['request_id'],))
                if row:value=save(core,value,child_goal=row['goal_id'],status='RETURNING')
            if value['status']=='CLOSED':
                evaluate(core,value);return value
            def checkpoint():
                if interrupted():raise CoreError('repair_yielded','Foreground work has priority')
                check(core,value)
            checkpoint()
            if not value.get('child_goal'):
                dev=core.development.get(ident)
                if dev['status']!='SUCCEEDED':
                    dev=core.develop(ident,True,False)
                    checkpoint()
                    if dev['status']=='WAITING' and dev['phase']=='verified' and dev['error']=='review_required':
                        if value.get('shadow_started'):
                            return save(core,value,status='WAITING',error='shadow_reconciliation_required')
                        package=dev['release_id'];bundle=core.packages.get(package)
                        source=Plans(core.db).get(value['source_goal'])['proposal']['input_text']
                        value=save(core,value,status='SHADOW_RUNNING',shadow_started=True)
                        with RunLock(core.root):
                            outputs,worker=core.worker.run(bundle['bundle']['files'],[source],checkpoint,seconds=8)
                        if not isinstance(outputs,list) or len(outputs)!=1 or not isinstance(outputs[0],str):
                            raise CoreError('repair_actual_failed','Missing original-input shadow receipt')
                        proof=verify_text(core,value,outputs[0]);checkpoint()
                        with RunLock(core.root,'development'):
                            core.development.checkpoint(ident,'release.activate.v1')
                            current=core.development.get(ident)
                            if current['release_id']!=package or current['phase']!='verified':raise CoreError('conflict','Candidate changed')
                            with core.db.transaction() as tx:
                                checkpoint()
                                tx.execute('UPDATE development_controls SET approved_package=? WHERE run_id=?',(package,ident))
                                value=records.save(core.db,{**value,'status':'ADOPTING','package_id':package,'shadow':{**proof,'worker':worker}},tx)
                                core.db.event(tx,value['source_task'],'development.automatically_reviewed',{'run_id':ident,'package_id':package,'mandate_revision':value['revision']})
                        dev=core.develop(ident,False,False)
                    if dev['status']!='SUCCEEDED':
                        if dev['status'] in {'FAILED','CANCELLED'}:raise CoreError(dev['error'] or 'repair_failed','Repair development failed')
                        return save(core,value,status='WAITING',error=dev['error'])
                if not value.get('package_id') or dev['release_id']!=value['package_id']:
                    raise CoreError('repair_not_reviewed','Only the exact shadow-reviewed package may return')
                checkpoint()
                if not value.get('rework_request'):
                    p=Plans(core.db).get(value['source_goal']);owner=core.works.owner(p['id'])
                    proposal={**p['proposal'],'steps':[{**p['proposal']['steps'][0],'capability':value['capability']}]}
                    request={'action':'rework_auto','id':p['id'],'revision':p['revision'],'work_revision':owner['revision'],
                        'request_id':'repair-return-'+digest(ident)[:40],'kind':'new_requirement' if value['before_score']==100 else 'correction','goal':p['request']['goal'],
                        'note':'已授权修复：保留原要求、输入和失败记录，使用经原输入影子验收的候选返工。','proposal':proposal}
                    request['analysis_digest']=rework_impact.analyze(core,request)['analysis_digest']
                    value=save(core,value,rework_request=request)
                child=work_revisions.create(core,value['rework_request'])['id']
                value=save(core,value,child_goal=child,status='RETURNING')
            checkpoint();p=Plans(core.db).get(value['child_goal'])
            if not p['task_id']:
                rules=Completion(core.db).criteria(value['source_task'])['rules']
                goals.command(core.root,{'action':'approve','id':p['id'],'revision':p['revision'],'acceptance':rules})
                p=Plans(core.db).get(p['id'])
            if not value.get('child_task'):value=save(core,value,child_task=p['task_id'])
            checkpoint()
            if core.db.one("SELECT 1 FROM actions WHERE task_id=? AND status IN ('UNKNOWN','DISPATCHING')",(p['task_id'],)):
                return save(core,value,status='WAITING',error='reconciliation_required')
            task=core.run_task(p['task_id'])
            if task['status']=='WAITING':return save(core,value,status='WAITING',error=task['error'])
            proof=evaluate(core,value)
            return save(core,value,status='CLOSED',error=None,actual=proof)
    except CoreError as error:
        if not value:raise
        if error.code=='repair_return_conflict':return records.get(core.db,ident)
        if error.code in {'stopped','busy','repair_yielded','development_busy','executor_busy','runtime_draining','application_maintenance'}:
            return {'status':'deferred','error':error.code}
        return stop(core,value,error.code,'REGRESSED' if value['status']=='CLOSED' else 'FAILED')
    finally:core.close()


def cancel(core,ident):
    # Cancellation must reach a worker/model checkpoint without waiting for its lane lock.
    with core.db.transaction() as tx:
        value=records.get(core.db,ident)
        if not value:raise CoreError('repair_return_missing','No automatic return mandate')
        if value['status']=='CANCELLED':return value
        was_closed=value['status']=='CLOSED'
        run=core.development.get(ident)
        core.grants.revoke(run['spec']['grant_id'],transaction=tx)
        core.development.cancel(ident,transaction=tx)
        if value.get('child_goal'):
            value={**value,'child_task':Plans(core.db).get(value['child_goal'])['task_id']}
        if value.get('child_task'):
            core.grants.revoke(core.tasks.get(value['child_task'])['body']['grant_id'],transaction=tx)
            core.tasks.cancel(value['child_task'],transaction=tx)
        value=records.save(core.db,{**value,'status':'CANCELLED','error':'cancelled'},tx)
    if value.get('package_id') and not was_closed:core.packages.quarantine(value['capability'],value['package_id'])
    return value


_last={}
_cursor={}
def advance(root,lane,*,interrupted=lambda:False):
    if interrupted() or lane.state()['status']=='running' or time.monotonic()-_last.get(str(root),0)<5:return None
    _last[str(root)]=time.monotonic();core=Core(root)
    try:
        # Rotate a bounded scan, including older closures, without adding polling events.
        sql="SELECT seq,data FROM events WHERE kind=? AND seq IN (SELECT MAX(seq) FROM events WHERE kind=? GROUP BY json_extract(data,'$.development_id')) AND json_extract(data,'$.status') NOT IN ('FAILED','CANCELLED','REGRESSED','UNSUPPORTED') AND seq>? ORDER BY seq LIMIT 4"
        rows=core.db.all(sql,(records.EVENT,records.EVENT,_cursor.get(str(root),0)))
        if not rows:
            _cursor[str(root)]=0;rows=core.db.all(sql,(records.EVENT,records.EVENT,0))
        for row in rows:
            _cursor[str(root)]=row['seq']
            value=decode(row['data'])
            if value['status'] in records.TERMINAL-{'CLOSED'}:continue
            if value['status']=='CLOSED':
                try:evaluate(core,value)
                except CoreError as error:
                    if error.code not in {'stopped','application_maintenance'}:stop(core,value,error.code,'REGRESSED')
                continue
            return lane.submit('repair-return',value['development_id'],lambda ident=value['development_id']:run(root,ident,interrupted=interrupted))
    finally:core.close()
