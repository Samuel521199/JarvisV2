"""Compose acceptance, current evidence and conditional knowledge through ports."""
from contextlib import nullcontext
import sys
import time

from host.outcomes import service as outcome_service
from modules.task_resource.completion import Completion, text_report
from modules.context_knowledge.episodes import Episodes
from sdk.protocol import CoreError, decode, digest


def evaluator(core):
    from host.quote_sources import provider
    return Completion(core.db,source_review=provider(core),change_review=provider(core,changes=True),rework_review=provider(core,rework=True),recovery_review=provider(core,recovery=True))


def refresh(core, task_id, *, transaction=None):
    completion=evaluator(core);episodes=Episodes(core.db);observer=outcome_service(core)
    with (nullcontext(transaction) if transaction is not None else core.db.transaction()) as tx:
        outcome=observer.refresh(task_id,transaction=tx)
        result=completion.evaluate(task_id,outcome,tx)
        task=core.tasks.get(task_id)
        # This first reusable method has no remote effect or project/private memory.
        eligible=(text_report(task['body']) and task['body']['principal_id']=='owner.local'
                  and task['body']['scope_id']=='personal'
                  and not core.db.one('SELECT 1 FROM goal_plans WHERE task_id=?',(task_id,))
                  and not core.db.one('SELECT 1 FROM experience_uses WHERE task_id=?',(task_id,)))
        episodes.record(task,result,eligible,tx)
        method=episodes.source(task_id)
        result['method']={k:method[k] for k in ('id','status','revision','expires')} if method else None
        if method:result['method']['review_required']=method['status']=='QUARANTINED' or method['expires']<=time.time()
        result['method_available']=bool(method and method['status']=='ACTIVE' and method['expires']>time.time() and result['evidence_ready'])
        result['feedback_history']=core.db.all('SELECT id,kind,note,fingerprint,created FROM completion_feedback WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 20',(task_id,))
        result['assessment_history']=[{'created':r['created'],'assessment':decode(r['body'])} for r in
            core.db.all('SELECT body,created FROM completion_history WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 8',(task_id,))]
        return result


def projection(core, task_id):
    try:return refresh(core,task_id,transaction=core.db.connection if core.db.connection.in_transaction else None)
    except Exception:
        # The projection degrades to UNAVAILABLE by design; keep the cause for diagnosis.
        from control import logs
        logs.throttled(logs.get('completion'),'projection:'+type(sys.exc_info()[1]).__name__,'Completion projection unavailable for %s',task_id)
        return {'state':'UNAVAILABLE','task_id':task_id,'condition_score':None}


def check_use(core, task_id):
    task=core.db.one('SELECT request_id FROM tasks WHERE id=?',(task_id,))
    if not task or not task['request_id'].startswith('reuse.'):return
    if not core.db.one("SELECT value FROM meta WHERE key='completion_schema'"):
        raise CoreError('experience_changed','Required method evidence is unavailable')
    episodes=Episodes(core.db)
    use=core.db.one('SELECT * FROM experience_uses WHERE task_id=?',(task_id,))
    if not use:raise CoreError('experience_changed','Required method adoption record is unavailable')
    if core.db.one('SELECT 1 FROM experience_uses WHERE task_id=?',(use['source_task'],)):
        raise CoreError('experience_changed','Nested method sources are not enabled')
    # Revalidate the source, including file changes/revocations, at the effect boundary.
    source=refresh(core,use['source_task'],transaction=core.db.connection if core.db.connection.in_transaction else None)
    if not source['evidence_ready'] or source['state'] not in {'SATISFIED','VERIFIED','ACCEPTED'}:
        raise CoreError('experience_changed','Source task no longer supports this method')
    episodes.check_use(task_id)


def pump(core):
    """Existing scheduler only: bounded reconciliation, including missed completion callbacks."""
    Completion(core.db)
    rows=core.db.all('''SELECT t.id FROM tasks t JOIN task_acceptance a ON a.task_id=t.id
        LEFT JOIN task_completion c ON c.task_id=t.id WHERE t.status IN ('SUCCEEDED','FAILED','CANCELLED')
        AND (c.task_id IS NULL OR c.checked<?) ORDER BY COALESCE(c.checked,0),t.created LIMIT 2''',(time.time()-10,))
    for row in rows:projection(core,row['id'])


def command(core, value):
    completion=evaluator(core);episodes=Episodes(core.db)
    action=value['action'];task_id=value['id'];core.tasks.get(task_id)
    if action=='completion_detail':return refresh(core,task_id)
    if action=='acceptance_set':return completion.configure(task_id,value['revision'],value['rules'])
    if action=='completion_feedback':
        outcome_service(core)  # Ensure the optional observer schema before the shared transaction.
        with core.db.transaction() as tx:
            current=refresh(core,task_id,transaction=tx)
            completion.feedback(task_id,value['request_id'],value['fingerprint'],value['kind'],value['note'],current,tx)
            return refresh(core,task_id,transaction=tx)
    if action=='experience_review':
        outcome_service(core)
        with core.db.transaction() as tx:
            method=episodes.source(task_id)
            if not method or type(value['revision']) is not int or method['revision']!=value['revision']:
                raise CoreError('conflict','Method review changed')
            sources=core.db.all('SELECT s.task_id,s.input_digest,t.created FROM experience_sources s JOIN tasks t ON t.id=s.task_id WHERE s.method_id=? LIMIT 33',(method['id'],))
            expired=method['expires']<=time.time()
            if (method['status']!='QUARANTINED' and not expired) or len(sources)>32:
                raise CoreError('experience_review','This method needs a bounded fresh review')
            fresh_after=max(method['review_after'],method['expires'] if expired else 0)
            uses=core.db.all('SELECT task_id FROM experience_uses WHERE method_id=? LIMIT 33',(method['id'],))
            if len(uses)>32:raise CoreError('experience_review','Review exceeds the current bounded batch')
            for use in uses:
                inspected=refresh(core,use['task_id'],transaction=tx)
                feedback=core.db.one('SELECT kind FROM completion_feedback WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 1',(use['task_id'],))
                if feedback and feedback['kind']=='reject':raise CoreError('experience_review','A later adoption still has unresolved feedback')
                assessment=core.db.one('SELECT a.body FROM outcome_current c JOIN outcome_assessments a ON a.id=c.assessment_id WHERE c.task_id=?',(use['task_id'],))
                if inspected['state']!='CANCELLED' and (any(c['status']=='failed' for c in inspected['checks'])
                        or assessment and any(c['status']=='failed' for c in decode(assessment['body'])['criteria'])):
                    raise CoreError('experience_review','A later adoption still fails its checks')
            fresh=set()
            for source in sources:
                current=refresh(core,source['task_id'],transaction=tx)
                if current['state'] not in {'SATISFIED','VERIFIED','ACCEPTED'}:raise CoreError('experience_review','Unresolved counterevidence remains')
                if source['created']>fresh_after:fresh.add(source['input_digest'])
            if len(fresh)<2:raise CoreError('experience_review','Two distinct fresh successful inputs are required')
            bindings=decode(method['bindings'])
            if bindings!={cap:core.registry.binding(cap) for cap in bindings}:raise CoreError('experience_changed','Tool versions changed')
            tx.execute("UPDATE experience_methods SET status='ACTIVE',revision=revision+1,expires=? WHERE id=?",(time.time()+30*86400,method['id']))
            core.db.event(tx,task_id,'experience.requalified',{'method_id':method['id'],'revision':method['revision']+1})
            return refresh(core,task_id,transaction=tx)
    if action=='experience_reuse':
        if (not isinstance(value['text'],str) or len(value['text'])>50000 or not isinstance(value['request_id'],str)
                or not 1<=len(value['request_id'])<=60):
            raise CoreError('invalid_request','Expected fresh bounded text and request ID')
        outcome_service(core)
        from modules.task_resource.scheduling import Scheduling
        schedule=Scheduling(core.db)
        with core.db.transaction() as tx:
            old=core.db.one('SELECT * FROM tasks WHERE request_id=?',('reuse.'+value['request_id'],))
            if old:
                use=core.db.one('SELECT * FROM experience_uses WHERE task_id=?',(old['id'],))
                body=decode(old['body'])
                if not use or use['source_task']!=task_id or body['steps'][0]['arguments']['text']!=value['text']:
                    raise CoreError('conflict','Reuse request changed')
                return {'task_id':old['id'],'source_task':task_id,'method_id':use['method_id'],'existing':True}
            current=refresh(core,task_id,transaction=tx);method=episodes.source(task_id)
            if not current['method_available'] or not method: raise CoreError('experience_changed','No currently supported method')
            source=core.tasks.get(task_id)
            if source['bindings']!={cap:core.registry.binding(cap) for cap in source['bindings']}:
                raise CoreError('experience_changed','Tool versions changed; collect fresh evidence')
            body={'schema':'jarvis.task.v1','request_id':'reuse.'+value['request_id'],'principal_id':'owner.local','scope_id':'personal',
                  'grant_id':'local-default','goal':'分析本次文本并保存统计报告',
                  'steps':[{'step_id':'analyze','capability':'text.analyze.v1','arguments':{'text':value['text']}},
                           {'step_id':'deliver','capability':'artifact.write.v1','arguments':{'name':'report.json'},'input_from':'analyze'}],
                  'limits':{'max_steps':2,'max_attempts':2,'max_seconds':600,'max_cost_units':2}}
            ident=core.tasks.submit(body,transaction=tx)
            episodes.use(ident,task_id,method,tx)
            schedule.enqueue([ident],transaction=tx)
            core.db.event(tx,ident,'experience.adopted',{'source_task':task_id,'method_id':method['id'],'method_revision':method['revision']})
            return {'task_id':ident,'source_task':task_id,'method_id':method['id']}
    raise CoreError('invalid_request','Unsupported completion action')
