"""Owner-operated, bounded workbench commands; no shell or new authority."""
import sqlite3
from host.core import Core
from control.recovery.gate import RunLock
from control.execution import admission
from sdk.protocol import CoreError


def command(root, value):
    fields={'task_detail':{'id'},'task_cancel':{'id'},'task_resume':{'id'},'task_reconcile':{'id'},
            'module_probe':{'id'},'module_change':{'id','operation','revision','implementation'},
            'dev_cancel':{'id'},'events':set(),'task_submit':{'task'},'release':{'id','operation','revision'},
            'outcome_configure':{'enabled'},'outcome_retry':{'id'},'outcome_history':{'id'},
            'completion_detail':{'id'},'acceptance_set':{'id','revision','rules'},
            'completion_feedback':{'id','request_id','fingerprint','kind','note'},
            'experience_reuse':{'id','request_id','text'},'experience_review':{'id','revision'}}
    if not isinstance(value,dict) or value.get('action') not in fields or set(value)!={'action'}|fields[value['action']]:
        raise CoreError('invalid_request','Unexpected settings operation')
    core=Core(root)
    try:
        action=value['action'];ident=value.get('id')
        if action=='outcome_configure':
            from host.outcomes import service
            return service(core).configure(value['enabled'])
        if action=='task_submit':return {'task_id':core.tasks.submit(value['task'])}
        if ident is not None and (not isinstance(ident,str) or len(ident)>100):raise CoreError('invalid_request','Invalid identifier')
        if action in {'completion_detail','acceptance_set','completion_feedback','experience_reuse','experience_review'}:
            from host.completion import command as complete
            return complete(core,value)
        if action=='events':return core.db.all('SELECT * FROM events ORDER BY seq DESC LIMIT 100')
        if action in {'outcome_retry','outcome_history'}:
            from host.outcomes import service
            core.tasks.get(ident)
            return service(core).retry(ident) if action=='outcome_retry' else service(core).history(ident)
        if action=='task_detail':
            from host.outcomes import observe
            from host.completion import projection
            return {'task':core.tasks.get(ident),'actions':core.tasks.actions(ident),'outcome':observe(core,ident),'completion':projection(core,ident)}
        if action=='task_cancel':return {'changed':core.tasks.cancel(ident)}
        if action=='dev_cancel':return {'changed':core.development.cancel(ident)}
        if action=='task_reconcile':return core.reconcile(ident)
        if action=='task_resume':
            with admission(core.root):
                core.gate.require_running();core.tasks.resume(ident)
            return {'task':core.tasks.get(ident)}
        if action=='release':
            if value['operation'] not in {'probe','activate','rollback','retire','disable'} or type(value['revision']) is not int:
                raise CoreError('invalid_request','Invalid release operation')
            with RunLock(core.root):
                core.gate.require_running()
                if value['operation']=='probe':return core.packages.evaluate(ident,core.gate.require_running)
                if value['operation']=='retire':return core.packages.retire(ident)
                if value['operation']=='activate':
                    managed = core.db.one('SELECT d.id FROM development_runs d JOIN development_controls c ON c.run_id=d.id WHERE d.release_id=?', (ident,))
                    if managed: core._publication_check(managed['id'], ident)
                    return core.packages.activate(ident,value['revision'],core.gate.require_running)
                if value['operation']=='rollback':return core.packages.rollback(ident,value['revision'],core.gate.require_running)
                with core.db.transaction() as tx:
                    if tx.execute('UPDATE release_slots SET enabled=0,revision=revision+1 WHERE capability=? AND revision=?',(ident,value['revision'])).rowcount!=1:raise CoreError('conflict','Release changed')
                return core.packages.slot(ident)
        if action=='module_probe':return core.registry.probe(ident)
        if value['operation'] not in {'start','stop','activate','rollback'} or type(value['revision']) is not int:
            raise CoreError('invalid_request','Invalid module transition')
        return core.change_module(ident,value['operation'],value['revision'],value['implementation'])
    finally:core.close()


from host.task_scheduler import TaskRunner
