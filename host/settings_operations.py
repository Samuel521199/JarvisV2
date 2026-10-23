"""Owner-operated, bounded workbench commands; no shell or new authority."""
from concurrent.futures import ThreadPoolExecutor
import threading
import sqlite3
from host.core import Core
from control.recovery.gate import RunLock
from sdk.protocol import CoreError


def command(root, value):
    fields={'task_detail':{'id'},'task_cancel':{'id'},'task_resume':{'id'},'task_reconcile':{'id'},
            'module_probe':{'id'},'module_change':{'id','operation','revision','implementation'},
            'dev_cancel':{'id'},'events':set(),'task_submit':{'task'},'release':{'id','operation','revision'}}
    if not isinstance(value,dict) or value.get('action') not in fields or set(value)!={'action'}|fields[value['action']]:
        raise CoreError('invalid_request','Unexpected settings operation')
    core=Core(root)
    try:
        action=value['action'];ident=value.get('id')
        if action=='task_submit':return {'task_id':core.tasks.submit(value['task'])}
        if ident is not None and (not isinstance(ident,str) or len(ident)>100):raise CoreError('invalid_request','Invalid identifier')
        if action=='events':return core.db.all('SELECT * FROM events ORDER BY seq DESC LIMIT 100')
        if action=='task_detail':return {'task':core.tasks.get(ident),'actions':core.tasks.actions(ident)}
        if action=='task_cancel':return {'changed':core.tasks.cancel(ident)}
        if action=='dev_cancel':return {'changed':core.development.cancel(ident)}
        if action=='task_reconcile':return core.reconcile(ident)
        if action=='task_resume':
            with RunLock(core.root):
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


class TaskRunner:
    """One bounded batch per host, separate from chat. Core owns durable task receipts."""
    def __init__(self,root):
        self.root=root;self.lock=threading.Lock();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='jarvis-tasks');self.future=None;self.closed=False

    def state(self):
        with self.lock:
            if self.future is None:return {'status':'idle'}
            if not self.future.done():return {'status':'running'}
            try:return {'status':'finished','result':self.future.result()}
            except Exception as exc:return {'status':'failed','error':exc.code if isinstance(exc,CoreError) else 'local_execution_failed'}

    def start(self,value):
        if not isinstance(value,dict) or set(value)!={'max_tasks'} or type(value['max_tasks']) is not int or not 1<=value['max_tasks']<=10:
            raise CoreError('invalid_limit','Choose one to ten tasks')
        with self.lock:
            if self.closed or self.future is not None and not self.future.done():raise CoreError('task_busy','A bounded batch is already running')
            self.future=self.pool.submit(self._run,value['max_tasks'])
        return {'status':'running'}

    def _run(self,limit):
        core=Core(self.root)
        try:return core.run(limit)
        finally:core.close()

    def start_tool(self,value):
        from host.tools import owned_task
        return self._start_selected(value, owned_task)

    def start_goal(self,value):
        from host.goals import owned_task
        return self._start_selected(value, owned_task)

    def start_connector(self,value):
        from host.connectors import owned_task
        return self._start_selected(value, owned_task)

    def _start_selected(self,value, owned_task):
        if not isinstance(value,dict) or set(value)!={'id'}:
            raise CoreError('tool_invalid','Expected one pure-tool task')
        with self.lock:
            if self.closed or self.future is not None and not self.future.done():raise CoreError('task_busy','A bounded task is already running')
            core=Core(self.root)
            try:
                task=owned_task(core,value['id']);core.gate.require_running()
                if task['status']=='SUCCEEDED':return {'status':'finished','id':task['id']}
                if task['cancel'] or task['status'] not in {'READY','WAITING'}:raise CoreError('invalid_state','Task cannot be started')
                if any(a['status']=='UNKNOWN' for a in core.tasks.actions(task['id'])):raise CoreError('unknown_effect','Reconcile receipts before continuing')
            finally:core.close()
            self.future=self.pool.submit(self._run_tool,value['id'])
        return {'status':'running','id':value['id']}

    def _run_tool(self,ident):
        core=Core(self.root)
        try:
            task=core.run_task(ident)
            if task['status']=='SUCCEEDED':
                from host.memory import completed_goal
                try:completed_goal(self.root,ident)
                except (CoreError,OSError,sqlite3.Error):pass  # Candidate backlog or revoked evidence must not rewrite delivery success.
            return {'tasks':[{'task_id':ident,'status':task['status'],'error':task['error']}]}
        finally:core.close()

    def close(self):
        with self.lock:self.closed=True
        self.pool.shutdown(wait=True)
