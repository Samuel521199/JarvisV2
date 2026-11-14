"""Optional local candidate trials in the existing background lane and OS lock."""
import secrets,time
from control.application_runtime import require_accepting
from control.policy.grants import GrantStore
from control.recovery.gate import RunLock
from host.core import Core
from host.completion import refresh
from modules.context_knowledge.lesson_trials import LessonTrials
from modules.context_knowledge.task_lessons import EVENT
from modules.task_resource import lesson_checks
from sdk.protocol import CoreError,decode,digest


def key_for(candidate):return digest([lesson_checks.VERSION,candidate['family']])


def eligible(core,task_id):
    candidate=refresh(core,task_id).get('learning_candidate')
    if (not candidate or candidate['state']!='CANDIDATE' or candidate['next_step'] not in
        {'independent_validation','resolve_validation_failure','review_validation_run','compare_real_tasks'}
        or candidate['applicability'].get('purpose') not in lesson_checks.PURPOSES):
        raise CoreError('lesson_unsupported','Candidate needs current evidence and a supported independent oracle')
    task=core.tasks.get(task_id);steps=task['body']['steps']
    if (task['status']!='SUCCEEDED' or task['cancel'] or not 2<=len(steps)<=3
        or steps[-1]['capability']!='artifact.write.v1' or steps[-1].get('input_from')!=steps[-2]['step_id']
        or set(steps[0]['arguments'])!={'text'} or steps[0].get('input_from')
        or candidate['procedure'][0]['arguments']['text']!={'role':'current_input'}):
        raise CoreError('lesson_unsupported','Only one or two sequential pure-text stages can be tested')
    for index,step in enumerate(steps[:-1]):
        cap=step['capability'];binding=task['bindings'].get(cap)
        if (not cap.startswith('plugin.') or index and (step.get('input_from')!=steps[index-1]['step_id'] or step['arguments'])
            or core.registry.binding(cap)!=binding):
            raise CoreError('lesson_unsupported','Procedure or tool binding changed')
        core.packages.require(cap,binding);core.packages.require_context(binding,task['body'])
        # The separate local-test policy supplies the test allowance; it does not
        # charge zero-cost business work or resurrect a revoked capability grant.
        GrantStore.authorize(core.db.connection,task['body'],cap)
    return task,candidate


def run(root,task_id,*,interrupted=lambda:False):
    """At most two 8s/3CPU-s/256MiB worker batches; no business artifact writes."""
    core=Core(root);reserved=False;key=None
    try:
        with RunLock(core.root):
            require_accepting(core.root);core.gate.require_running()
            task,candidate=eligible(core,task_id);trials=LessonTrials(core.db);policy=trials.policy()
            key=key_for(candidate);prior=trials.prior(key)
            if prior:return {'status':'existing','trial':prior}
            if not policy['enabled']:raise CoreError('lesson_policy','Local candidate testing is disabled')
            if interrupted():raise CoreError('lesson_yielded','Foreground work has priority')
            seed=secrets.token_hex(16);purpose=candidate['applicability']['purpose']
            cases=lesson_checks.challenges(purpose,seed);challenge=lesson_checks.manifest(purpose,cases)
            binding=(candidate['family'],candidate['fingerprint']);started=time.monotonic()
            def checkpoint():
                require_accepting(core.root);core.gate.require_running()
                if interrupted():raise CoreError('lesson_yielded','Foreground work has priority')
                if time.monotonic()-started>18:raise CoreError('deadline','Local-test time limit reached')
                current_policy=trials.policy()
                if not current_policy['enabled'] or current_policy['revision']!=policy['revision']:
                    raise CoreError('lesson_policy','Local-test permission changed')
                _,current=eligible(core,task_id)
                if (current['family'],current['fingerprint'])!=binding:raise CoreError('lesson_changed','Candidate evidence changed')
            checkpoint()
            with core.db.transaction() as tx:
                trials.reserve(task_id,key,{'family':candidate['family'],'source_task':task_id,
                    'fingerprint':candidate['fingerprint'],'seed':seed,'challenge':challenge,
                    'max_worker_batches':len(task['body']['steps'])-1,'worker_wall_seconds':8,
                    'max_total_seconds':18,'synthetic_inputs_only':True},policy['revision'],tx)
            reserved=True;values=[c['input'] for c in cases];workers=[]
            # Calling the test worker directly avoids business execution and
            # release observation/promotion side effects of Packages.execute.
            for step in task['body']['steps'][:-1]:
                checkpoint();package=core.packages.get(task['bindings'][step['capability']])
                values,evidence=core.worker.run(package['bundle']['files'],values,checkpoint,seconds=8)
                if not isinstance(values,list) or len(values)!=len(cases) or any(not isinstance(value,str) for value in values):
                    raise CoreError('lesson_output','Incomplete local-test worker receipt')
                workers.append(evidence)
            checkpoint()
            scores=[{'id':case['id'],'output_digest':digest(output),**lesson_checks.score(purpose,case['input'],output)} for case,output in zip(cases,values)]
            result={'status':'PASSED' if all(s['passed'] for s in scores) else 'FAILED','cases':scores,
                'workers':workers,'seconds':time.monotonic()-started,'cloud_calls':0,
                'business_artifacts_written':False,'automatic_promotion':False,'scope':challenge['scope']}
            with core.db.transaction() as tx:trials.finish(task_id,key,result,tx)
            return result
    except CoreError as error:
        if reserved:
            # Failure is retained and consumes the reserved allowance. A missing
            # finish after process death is UNKNOWN, never automatic replay.
            with core.db.transaction() as tx:LessonTrials(core.db).finish(task_id,key,{'status':'INTERRUPTED','error':error.code,'automatic_promotion':False},tx)
        return {'status':'deferred' if not reserved else 'INTERRUPTED','error':error.code}
    finally:core.close()


def advance(root,lane,*,interrupted=lambda:False):
    """Called by existing idle maintenance, never by a new timer or observer."""
    if interrupted() or lane.state()['status']=='running':return None
    core=Core(root)
    try:
        trials=LessonTrials(core.db);policy=trials.policy()
        if not policy['enabled'] or trials.used()>=policy['max_trials_24h']:return None
        rows=core.db.all('SELECT task_id,data FROM events WHERE kind=? ORDER BY seq DESC LIMIT 32',(EVENT,))
        seen=set()
        for row in rows:
            if row['task_id'] in seen:continue
            seen.add(row['task_id']);candidate=decode(row['data'])
            if (candidate.get('state')!='CANDIDATE' or candidate.get('applicability',{}).get('purpose') not in lesson_checks.PURPOSES
                or trials.prior(key_for(candidate))):continue
            try:eligible(core,row['task_id'])
            except CoreError:continue
            try:return lane.submit('lesson-validation',row['task_id'],lambda ident=row['task_id']:run(root,ident,interrupted=interrupted))
            except CoreError as error:
                if error.code=='development_busy':return None
                raise
    finally:core.close()
