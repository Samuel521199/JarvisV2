"""Bounded parallel dispatch over the original ledger and exclusive OS cohort."""
from concurrent.futures import ThreadPoolExecutor
import threading
import os
import sqlite3
import time

from adapters.desktop.resources import sample
from control.execution import ExecutionCohort
from control.paths import data_root
from control.recovery.gate import RunLock
from host.core import Core
from modules.task_resource.scheduling import Scheduling, resources, TERMINAL
from sdk.protocol import CoreError, decode


class TaskRunner:
    def __init__(self, root, *, resource_sample=sample, foreground_pending=lambda: False):
        self.root = data_root(root)
        self.owner = RunLock(self.root, 'task-runner'); self.owner.__enter__()
        self.cohort = ExecutionCohort(self.root)
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='jarvis-tasks')
        self.active = {}; self.results = []; self.cached = []; self.error = None
        self.closed = False; self.drain = True; self.resource_sample = resource_sample
        self.foreground_pending = foreground_pending
        self.metrics = {}; self.cooldown = 0; self.last_sample = 0
        try:
            core = Core(self.root)
            try: Scheduling(core.db)
            finally: core.close()
            self.thread = threading.Thread(target=self._loop, name='jarvis-dispatch', daemon=True)
            self.thread.start()
        except BaseException:
            self.pool.shutdown(wait=True); self.owner.__exit__(None, None, None)
            raise

    def state(self):
        with self.lock:
            status = 'running' if self.active or self.cached else 'failed' if self.error else 'finished' if self.results else 'idle'
            return {'status': status, 'active': sorted(self.active), 'queued': list(self.cached),
                    'result': {'tasks': list(self.results)}, 'error': self.error,
                    'resources': dict(self.metrics), 'scope': 'bounded_core_dispatch'}

    def _store(self, fn):
        core = Core(self.root)
        try: return fn(core, Scheduling(core.db))
        finally: core.close()

    def policy(self):
        return self._store(lambda c, s: s.policy())

    def configure(self, value):
        result = self._store(lambda c, s: s.configure(value)); self.wake.set()
        return result

    def prioritize(self, value):
        result = self._store(lambda c, s: s.prioritize(value)); self.wake.set()
        return result

    def _enqueue(self, core, ids):
        with self.lock:
            if self.closed: raise CoreError('task_busy', 'Task runner is closing')
            result = Scheduling(core.db).enqueue(ids)
            self.cached = list(dict.fromkeys(self.cached + ids)); self.error = None
            self.wake.set()
        return {'status': 'queued', **result}

    def start(self, value):
        if not isinstance(value, dict) or set(value) != {'max_tasks'} or type(value['max_tasks']) is not int or not 1 <= value['max_tasks'] <= 10:
            raise CoreError('invalid_limit', 'Choose one to ten tasks')
        core = Core(self.root)
        try:
            core.gate.require_running()
            ids = [r['id'] for r in core.db.all("SELECT id FROM tasks WHERE status='READY' AND cancel=0 ORDER BY created LIMIT ?", (value['max_tasks'],))]
            return self._enqueue(core, ids)
        finally: core.close()

    def start_tool(self, value):
        from host.tools import owned_task
        return self._start_selected(value, owned_task)

    def start_goal(self, value):
        from host.goals import owned_task
        return self._start_selected(value, owned_task)

    def start_connector(self, value):
        from host.connectors import owned_task
        return self._start_selected(value, owned_task)

    def _start_selected(self, value, owned_task):
        if not isinstance(value, dict) or set(value) != {'id'}:
            raise CoreError('tool_invalid', 'Expected one existing task')
        core = Core(self.root)
        try:
            task = owned_task(core, value['id']); core.gate.require_running()
            if task['status'] == 'SUCCEEDED': return {'status': 'finished', 'id': task['id']}
            with self.lock:
                if task['id'] in self.active: return {'status': 'running', 'id': task['id'], 'existing': True}
            return {**self._enqueue(core, [task['id']]), 'id': task['id']}
        finally: core.close()

    def _capacity(self, policy):
        now = time.monotonic()
        if now-self.last_sample >= .5:
            try: self.metrics = self.resource_sample()
            except (OSError, ValueError): self.metrics = {'cpu_percent': None, 'memory_total': None, 'memory_used': None}
            self.last_sample = now
            cpu = self.metrics.get('cpu_percent')
            if cpu is not None and cpu >= policy['cpu_ceiling']: self.cooldown = now+2
        if now < self.cooldown: return 0, 'CPU 繁忙，为聊天保留余量'
        if self.foreground_pending(): return 0, '优先处理已排队的聊天'
        return min(policy['max_workers'], max(1, (os.cpu_count() or 2)//2)), None

    @staticmethod
    def _recover(core):
        core.tasks.recover(); core.worker.recover(); core.packages.recover()

    def _loop(self):
        core = None
        try:
            core = Core(self.root); store = Scheduling(core.db)
            while True:
                self.wake.clear()
                from host.outcomes import observe
                observe(core, limit=32)
                from host.completion import pump
                try:pump(core)
                except Exception:pass  # Optional reconciliation cannot stop the execution scheduler.
                with self.lock:
                    for ident, entry in list(self.active.items()):
                        if not entry['future'].done(): continue
                        try: result = entry['future'].result()
                        except BaseException as exc:
                            result = {'task_id': ident, 'status': 'WAITING', 'error': exc.code if isinstance(exc, CoreError) else 'local_execution_failed'}
                        store.mark(ident, finished=True, reason=result.get('error'))
                        self.results.append(result); self.results = self.results[-100:]
                        entry['permit'].close(); del self.active[ident]
                    rows = store.pending()
                    if not self.closed:
                        store.admit_waiting()
                        from host.waiting import advance
                        advance(core,store)
                        rows = store.pending()
                    self.cached = [r['task_id'] for r in rows if r['task_id'] not in self.active]
                    if self.closed and (not self.drain or not rows) and not self.active: break
                    policy = store.policy(); capacity, pressure = self._capacity(policy)
                    keys = set().union(*(e['profile']['conflicts'] for e in self.active.values())) if self.active else set()
                    reserved = sum(e['profile']['memory_mib'] for e in self.active.values())
                    for row in rows:
                        ident = row['task_id']
                        if ident in self.active: continue
                        if row['status'] in TERMINAL or row['cancel']:
                            store.mark(ident, finished=True); continue
                        if self.closed and not self.drain: continue
                        if core.gate.state() != 'ready':
                            store.mark(ident, reason='助手当前未允许执行'); continue
                        if core.db.one("SELECT 1 FROM actions WHERE task_id=? AND status='UNKNOWN'", (ident,)):
                            store.mark(ident, finished=True, reason='unknown_effect'); continue
                        profile = resources(decode(row['body']))
                        reason = pressure
                        if not reason and len(self.active) >= capacity: reason = '等待执行槽'
                        if not reason and keys & profile['conflicts']: reason = '等待冲突资源释放'
                        total, used = self.metrics.get('memory_total'), self.metrics.get('memory_used')
                        if not reason and (total is None or used is None): reason = '内存指标未知，暂缓新任务'
                        if not reason and (total-used)/1024**2 - reserved - profile['memory_mib'] < policy['memory_reserve_mib']:
                            reason = '为聊天和系统保留内存'
                        if reason:
                            store.mark(ident, reason=reason); continue
                        try: permit = self.cohort.acquire(ident, lambda: self._recover(core))
                        except CoreError as exc:
                            store.mark(ident, reason='等待执行所有权' if exc.code == 'busy' else exc.code); continue
                        # Recovery may have converted a crashed in-flight action to UNKNOWN.
                        if core.db.one("SELECT 1 FROM actions WHERE task_id=? AND status='UNKNOWN'", (ident,)):
                            permit.close(); store.mark(ident, finished=True, reason='unknown_effect'); continue
                        store.mark(ident, started=True)
                        try: future = self.pool.submit(self._run_tool, ident, permit)
                        except BaseException: permit.close(); raise
                        self.active[ident] = {'future': future, 'permit': permit, 'profile': profile}
                        keys.update(profile['conflicts']); reserved += profile['memory_mib']
                    if self.closed and not self.active:
                        # Pressure-blocked work remains durably queued for the next Host.
                        break
                    pending = bool(rows or self.active)
                self.wake.wait(.1 if pending else 2)
        except BaseException as exc:
            with self.lock: self.error = exc.code if isinstance(exc, CoreError) else 'scheduler_failed'
        finally:
            self.pool.shutdown(wait=True)
            with self.lock:
                for entry in self.active.values(): entry['permit'].close()
                self.active.clear()
            if core: core.close()

    def _run_tool(self, ident, permit):
        core = Core(self.root)
        try:
            task = core.run_claimed_task(ident, permit)
            if task['status'] == 'SUCCEEDED':
                from host.memory import completed_goal
                try: completed_goal(self.root, ident)
                except (CoreError, OSError, sqlite3.Error): pass
            return {'task_id': ident, 'status': task['status'], 'error': task['error']}
        finally:
            core.close(); self.wake.set()

    def close(self, drain=True):
        with self.lock: self.closed = True; self.drain = drain; self.wake.set()
        self.thread.join()
        if self.owner:
            self.owner.__exit__(None, None, None); self.owner = None
