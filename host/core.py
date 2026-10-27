from __future__ import annotations

import time
import sqlite3
from pathlib import Path

from adapters.storage.sqlite import Database
from adapters.models.http_client import JsonModel
from adapters.models.native import NativeModel
from control.credentials import Credentials
from control.network import NetworkGate
from control.paths import child, data_root
from control.policy.grants import GrantStore
from control.recovery.gate import RunLock, StopGate
from control.worker.runtime import RestrictedWorker
from control import receipts
from modules.continuity import Continuity
from modules.context_knowledge import Facts
from modules.model_gateway.routed import RoutedModels
from modules.preferences.store import Preferences, resolve
from modules.release_recovery.packages import Packages
from modules.autonomous_development.service import Development
from modules.registry_composer.registry import Registry
from modules.registry_composer.connectors import Connectors
from modules.task_resource.ledger import Ledger
from modules.task_resource.works import Works
from sdk.protocol import CoreError, RetryableError, PROJECT, canonical, decode, digest, read_json


class Core:
    """Composition only; state, grants and capabilities have separate owners.

    The local OS account owns configuration and control. Generated candidates
    execute only through the restricted Worker, never as host imports. Model
    access uses explicitly configured transports and invocation authorization.
    """
    def __init__(self, root: str | Path):
        self.root = data_root(root)
        self.db = Database(child(self.root, "state/core.sqlite3"))
        self.gate = StopGate(self.root)
        self.identity = Continuity(self.db)
        try:
            self.identity.describe()
            if not self.db.one("SELECT value FROM meta WHERE key='initialization_complete'"):
                raise CoreError("initialization_incomplete", "Initialization did not finish; preserve state for recovery")
            self.grants = GrantStore(self.db)
            self.worker = RestrictedWorker(self.root)
            self.packages = Packages(self.db, self.root, self.worker, self.gate)
            self.connectors = Connectors(self.root)
            self.registry = Registry(self.db, plugins=self.packages, connectors=self.connectors)
            self.tasks = Ledger(self.db, self.gate, self.registry)
            self.works = Works(self.db)
            self.facts = Facts(self.db)
            self.preferences = Preferences(self.root)
            self.credentials = Credentials(self.root)
        except BaseException:
            # Schema checks and stores above may fail; never leak the open connections.
            self.close()
            raise
        try:
            selected = self.preferences.read()
            if selected:
                config = selected['catalog']
                names = [name for name, item in config['providers'].items() if item.get('enabled', True)]
                providers = {name: self.make_model(config, name) for name in names}
                order = [config['default_provider']]
                if config['automatic_fallback']:
                    order.extend(name for name in config['fallback_order'] if name in providers and name not in order)
            else:
                config = read_json(PROJECT / "config/model-routes.json")
                if set(config) != {"schema", "routes", "order"} or config["schema"] != 1:
                    raise CoreError("model_config", "Unknown route configuration")
                providers = {route["id"]: JsonModel(route) for route in config["routes"]}
                if len(providers) != len(config["routes"]): raise CoreError("model_config", "Duplicate route ID")
                order = config['order']
            self.routed_models = RoutedModels(self.db, providers, order)
            self.routed_models.network_check = NetworkGate(self.root).require_online
        except BaseException:
            self.close()
            raise
        self.development = Development(self.db, self.gate, self.routed_models, self.packages, self.tasks,
                                       self._development_task, lambda: RunLock(self.root), self._publication_check, self._development_parent_check)

    def _development_parent_check(self, ident):
        parent=self.db.one('SELECT p.id,p.cancel,g.status FROM goal_growth g JOIN goal_plans p ON p.id=g.goal_id WHERE g.development_id=?',(ident,))
        if parent and (parent['cancel'] or parent['status']=='CANCELLED'):
            raise CoreError('cancelled','Parent goal was cancelled')
        if parent:
            from host.goal_context import check
            routes=self.db.one('SELECT routes FROM development_controls WHERE run_id=?',(ident,))
            destinations=[r['id'] for items in decode(routes['routes']).values() for r in items] if routes else None
            check(self,parent['id'],destinations)

    def _publication_check(self, ident, package):
        row = self.db.one('SELECT approved_package FROM development_controls WHERE run_id=?', (ident,))
        grant = self.development.get(ident)['spec']['grant_id']
        if (row and row['approved_package'] != package) or (not row and grant.startswith('workbench-')):
            raise CoreError('review_required', 'Review the exact verified candidate before publication')
        if row and self.packages.get(package)['status']=='VERIFIED':
            self.development.checkpoint(ident,'release.activate.v1')

    @classmethod
    def initialize(cls, raw):
        root = data_root(raw, create=True)
        for relative in ("state", "artifacts"):
            child(root, relative).mkdir(exist_ok=True)
        with RunLock(root):
            path = child(root, "state/core.sqlite3")
            if not path.exists():
                db = Database(path, create=True)
                try:
                    Continuity(db).initialize()
                    Registry(db).initialize()
                    GrantStore(db).add({"schema": "jarvis.grant.v1", "grant_id": "local-default",
                        "principal_id": "owner.local", "scope_id": "personal",
                        "capabilities": ["text.analyze.v1", "artifact.write.v1"],
                        "max_cost_units": 1000, "expires_at": time.time() + 365 * 86400})
                    seeds = []
                    for name in ("charter/baseline.json", "skills/text-report.json", "knowledge/runtime-boundary.json"):
                        value = decode((PROJECT / "seed" / name).read_bytes())
                        seeds.append({"source": "seed/" + name, "digest": digest(value), "schema": value["schema"]})
                    with db.transaction() as tx:
                        tx.execute("INSERT INTO meta(key,value) VALUES('seed_refs',?)", (canonical(seeds),))
                        tx.execute("INSERT INTO meta(key,value) VALUES('initialization_complete','1')")
                finally:
                    db.close()
        return cls(root)

    def close(self):
        if hasattr(self, 'preferences'): self.preferences.close()
        self.db.close()

    def make_model(self, config, provider=None, model=None, reasoning='default'):
        return NativeModel(resolve(config, provider, model, reasoning), self.credentials.get, child(self.root, 'temp'))

    def status(self):
        return {"release": (PROJECT / "VERSION").read_text().strip(), "identity": self.identity.describe(),
                "control": self.gate.state(), "stop_token": self.gate.token(), "integrity": self.db.integrity(),
                "task_counts": self.db.all("SELECT status,COUNT(*) AS count FROM tasks GROUP BY status"),
                "modules": self.registry.describe(), "models": {"configured": bool(self.routed_models.providers),
                    "providers": list(self.routed_models.order), "network_default": False},
                "model_routes": [{"id": key, "model": value.config["model"], "credential_available": value.available()} for key, value in self.routed_models.providers.items()],
                "releases": self.db.all("SELECT * FROM release_slots"),
                "development_counts": self.db.all("SELECT status,COUNT(*) AS count FROM development_runs GROUP BY status"),
                "runtime_scope": "trusted builtins + LPAC pure tools; model calls require explicit network flag and grant"}

    def run(self, max_tasks=100):
        if not isinstance(max_tasks, int) or not 1 <= max_tasks <= 100:
            raise CoreError("invalid_limit", "Run count must be 1..100")
        completed = []
        with RunLock(self.root):
            self.gate.require_running()
            recovery = self.tasks.recover()
            recovery["workers"] = self.worker.recover()
            self.packages.recover()
            # Snapshot avoids spinning forever when a task becomes WAITING.
            ready = self.db.all("SELECT id FROM tasks WHERE status='READY' ORDER BY created LIMIT ?", (max_tasks,))
            for row in ready:
                if self.gate.state() != "ready":
                    break
                self._run_task(row["id"])
                task = self.tasks.get(row["id"])
                completed.append({"task_id": task["id"], "status": task["status"], "error": task["error"]})
        return {"recovery": recovery, "tasks": completed}

    def run_task(self, task_id):
        """Explicitly execute only this task; completed effects are never replayed."""
        with RunLock(self.root):
            self.gate.require_running()
            self.tasks.recover(); self.worker.recover(); self.packages.recover()
            task = self.tasks.get(task_id)
            if task['status'] == 'SUCCEEDED': return task
            if task['status'] == 'WAITING': self.tasks.resume(task_id)
            elif task['status'] != 'READY': raise CoreError('invalid_state', 'Task cannot be started')
            self._run_task(task_id)
            return self.tasks.get(task_id)

    def _run_task(self, task_id):
        try:
            return self._execute_task(task_id)
        finally:
            from host.outcomes import observe
            observe(self, task_id)
            from host.completion import projection
            projection(self, task_id)

    def _execute_task(self, task_id):
        self.tasks.state(task_id, "RUNNING")
        while True:
            task = self.tasks.get(task_id)
            if task["cancel"]:
                self.tasks.state(task_id, "CANCELLED")
                return
            if self.gate.state() != "ready":
                self.tasks.state(task_id, "WAITING", "stopped")
                return
            if task["deadline"] <= time.time():
                self.tasks.state(task_id, "FAILED", "deadline")
                return
            if task["next_step"] == len(task["body"]["steps"]):
                self.tasks.state(task_id, "SUCCEEDED")
                from host.session_workspace import deliver_task
                try: deliver_task(self,task_id)
                except (CoreError,OSError,sqlite3.Error) as exc:
                    with self.db.transaction() as tx:
                        self.db.event(tx,task_id,'session.delivery_pending',{'error':exc.code if isinstance(exc,CoreError) else 'session_folder_unavailable'})
                return
            step = task["body"]["steps"][task["next_step"]]
            args = dict(step["arguments"])
            try:
                self._goal_memory_check(task_id)
                if "input_from" in step:
                    source = self.db.one("SELECT result,status FROM actions WHERE task_id=? AND step_id=?",
                                         (task_id, step["input_from"]))
                    if not source or source["status"] != "CONFIRMED":
                        raise CoreError("invalid_plan", "Input result is not confirmed")
                    result = decode(source['result'])
                    if step['capability'].startswith('plugin.'):
                        if not isinstance(result, dict) or not isinstance(result.get('text'), str):
                            raise CoreError('invalid_plan', 'Referenced result is not text')
                        args['text'] = result['text']
                    else: args['content'] = canonical(result)
                self.registry.validate_arguments(step["capability"], args)
                impl = task["bindings"][step["capability"]]
                self.registry.require(step["capability"], impl)
                self.registry.require_context(step["capability"], impl, task["body"])
                action = self.tasks.prepare(task_id, step, args)
                self.tasks.dispatch(task_id, action["id"])
            except CoreError as exc:
                state = "CANCELLED" if exc.code == "cancelled" else ("WAITING" if exc.code in {
                    "stopped", "denied", "module_disabled", "package_changed", "package_unavailable", "goal_context_changed", "plan_source_changed", "network_disabled", "experience_changed", "work_conflict", "rework_source_changed", "work_budget_exhausted", "work_budget_invalid"} else "FAILED")
                self.tasks.state(task_id, state, exc.code)
                return
            try:
                # Recheck the out-of-band stop marker at the effect boundary.
                self.gate.require_running()
                result = self._execute(task_id, action["id"], step["capability"], args, impl)
                self.tasks.confirm(task_id, action["id"], result)
                if step['capability'].startswith('mcp.') and result.get('is_error'):
                    self.tasks.state(task_id, 'FAILED', 'mcp_tool_error')
                    return
            except RetryableError:
                if not self.registry.safe_retry(step["capability"]):
                    self.tasks.uncertain(task_id, action["id"])
                    return
                self.tasks.retry(task_id, action["id"])
                time.sleep(min(0.01 * 2 ** action["attempts"], 0.2))
            except Exception as exc:
                self.tasks.uncertain(task_id, action["id"], exc.code if isinstance(exc, CoreError) else 'execution_uncertain')
                return

    def run_claimed_task(self, task_id, permit):
        """Only the bounded cohort may share its already-held OS execution lock."""
        from control.execution import ExecutionPermit
        if not isinstance(permit, ExecutionPermit):
            raise CoreError('execution_owner', 'Missing execution permit')
        permit.bind(self.root, task_id)
        self.gate.require_running()
        with self.db.transaction() as tx:
            task = self.tasks.get(task_id)
            if task['status'] == 'SUCCEEDED':
                return task
            if task['cancel']:
                raise CoreError('cancelled', 'Task cancelled')
            if any(a['status'] == 'UNKNOWN' for a in self.tasks.actions(task_id)):
                raise CoreError('unknown_effect', 'Reconcile effects before dispatch')
            if task['status'] not in {'READY', 'WAITING'}:
                raise CoreError('invalid_state', 'Task already has an execution owner')
            if tx.execute("UPDATE tasks SET status='RUNNING',revision=revision+1 WHERE id=? AND revision=? AND cancel=0",
                          (task_id, task['revision'])).rowcount != 1:
                raise CoreError('conflict', 'Task changed during claim')
            self.db.event(tx, task_id, 'scheduler.claimed', {})
        self._execution_permit = permit
        try:
            self._run_task(task_id)
            return self.tasks.get(task_id)
        finally:
            del self._execution_permit

    def _goal_memory_check(self, task_id):
        from host.completion import check_use
        check_use(self, task_id)
        from host.quote_sources import check_task
        check_task(self,task_id)
        if hasattr(self, '_execution_permit'):
            self._execution_permit.check(self.root, task_id)
        row=self.db.one('SELECT id FROM goal_plans WHERE task_id=?',(task_id,))
        if row:
            from host.goal_context import check
            check(self,row['id'])
            from host.work_revisions import check as check_work
            check_work(self,row['id'],execution=True)
            from modules.task_resource.work_budgets import WorkBudgets
            WorkBudgets(self.db).check_dispatch(task_id,charging=False)

    def _execute(self, task_id, action_id, capability, arguments, implementation):
        def checkpoint():
            self.gate.require_running()
            self._goal_memory_check(task_id)
            task = self.tasks.get(task_id)
            if task["cancel"]: raise CoreError("cancelled", "Task cancelled")
            if task["deadline"] <= time.time(): raise CoreError("deadline", "Task deadline reached")
            with self.db.transaction() as tx:
                GrantStore.authorize(tx, task["body"], capability)
        result = self.registry.execute(self.root, task_id, action_id, capability, arguments, implementation, checkpoint)
        if capability.startswith(("plugin.", "mcp.")):
            receipts.commit(self.root, receipts.binding(task_id, action_id, implementation, arguments), result)
        return result

    def develop(self, ident, network_enabled=False, retry_unknown=False):
        with RunLock(self.root, "development"):
            control = self.db.one('SELECT routes FROM development_controls WHERE run_id=?', (ident,))
            if control:
                routes = decode(control['routes'])
                providers = {}
                for profile in routes.values():
                    for route in profile:
                        # Stable route key includes phase/model; adapter still resolves the actual provider credential ID.
                        key = digest(route)
                        if route['adapter']=='codex-cli':
                            from adapters.models.codex_cli import CodexModel
                            providers[key]=CodexModel(route,self.root)
                        else:providers[key] = NativeModel(route, self.credentials.get, child(self.root, 'temp'))
                gateway = RoutedModels(self.db, providers, list(providers))
                gateway.network_check = NetworkGate(self.root).require_online
                gateway.phase_order = lambda phase: [digest(r) for r in routes['plan' if phase == 'plan' else 'code']]
                self.routed_models = gateway; self.development.models = gateway
            with RunLock(self.root):
                self.worker.recover(); self.tasks.recover(); self.packages.recover()
            self.routed_models.recover(ident); self.development.recover()
            if self.development.get(ident)["status"] not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                try: self.worker.verify()
                except CoreError as exc:
                    self.development.update(ident, status="WAITING", error=exc.code)
                    return self.development.get(ident)
            if retry_unknown: self.routed_models.acknowledge_unknown(ident)
            return self.development.execute(ident, network_enabled)

    def _development_task(self, task_id):
        with RunLock(self.root):
            self._run_task(task_id)

    def reconcile(self, task_id):
        """Read-only effect checking; never repeats an uncertain write."""
        with RunLock(self.root):
            self.tasks.recover()
            task = self.tasks.get(task_id)
            changed = []
            for action in self.tasks.actions(task_id):
                if action["status"] != "UNKNOWN":
                    continue
                args = decode(action["arguments"])
                cap = action["capability"]
                if cap.startswith(("plugin.", "mcp.")):
                    result = receipts.read(self.root, receipts.binding(task_id, action["id"], task["bindings"][cap], args))
                else:
                    result = self.registry.reconcile(self.root, task_id, action["id"], cap, args, task["bindings"][cap])
                self.tasks.confirm(task_id, action["id"], result)
                if cap.startswith('mcp.') and result.get('is_error'):
                    self.tasks.state(task_id, 'FAILED', 'mcp_tool_error')
                changed.append(action["id"])
            return {"reconciled": changed, "task_state": self.tasks.get(task_id)["status"],
                    "note": "Task remains waiting/cancelled; explicit resume does not undo a cancel or stop."}

    def change_module(self, module_id, operation, revision, implementation=None):
        with RunLock(self.root):
            if operation != "stop":
                self.gate.require_running()
            return self.registry.change(module_id, operation, revision, implementation)
