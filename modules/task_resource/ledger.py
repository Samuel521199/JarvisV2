from __future__ import annotations

import time
import uuid
from contextlib import nullcontext

from control.policy.grants import GrantStore
from sdk.protocol import CoreError, canonical, contract, decode, digest

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}


class Ledger:
    def __init__(self, db, gate, registry):
        self.db, self.gate, self.registry = db, gate, registry

    def submit(self, body, *, transaction=None):
        contract("task", body)
        if len(body["steps"]) > body["limits"]["max_steps"]:
            raise CoreError("budget_exhausted", "Plan exceeds step budget")
        seen = {}
        bindings = {}
        for step in body["steps"]:
            if step["step_id"] in seen:
                raise CoreError("invalid_plan", "Duplicate step ID")
            if "input_from" in step:
                source = seen.get(step['input_from'])
                artifact = step['capability'] == 'artifact.write.v1' and set(step['arguments']) == {'name'}
                pure_text = step['capability'].startswith('plugin.') and not step['arguments'] and source and source.startswith(('plugin.', 'mcp.'))
                if not source or not (artifact or pure_text):
                    raise CoreError('invalid_plan', 'Only earlier confirmed outputs may supply bounded text or artifact content')
            seen[step['step_id']] = step['capability']
            bindings[step["capability"]] = self.registry.binding(step["capability"])
            self.registry.require_context(step["capability"], bindings[step["capability"]], body)
        body_digest = digest(body)
        with (nullcontext(transaction) if transaction is not None else self.db.transaction()) as tx:
            old = tx.execute("SELECT * FROM tasks WHERE request_id=?", (body["request_id"],)).fetchone()
            if old:
                if old["digest"] != body_digest:
                    raise CoreError("conflict", "Request ID reused with different content")
                return old["id"]
            self.gate.require_running()
            for step in body["steps"]:
                GrantStore.authorize(tx, body, step["capability"])
            task_id = "task-" + uuid.uuid4().hex
            now = time.time()
            tx.execute("INSERT INTO tasks(id,request_id,digest,body,bindings,status,created,deadline) VALUES(?,?,?,?,?,'READY',?,?)",
                       (task_id, body["request_id"], body_digest, canonical(body), canonical(bindings), now,
                        now + body["limits"]["max_seconds"]))
            self.db.event(tx, task_id, "task.accepted", {"request_id": body["request_id"], "steps": len(body["steps"])})
            from modules.task_resource.completion import Completion
            tx.execute('SAVEPOINT acceptance_default')
            try:
                Completion(self.db).default(task_id, body, tx)
                tx.execute('RELEASE acceptance_default')
            except Exception:
                tx.execute('ROLLBACK TO acceptance_default');tx.execute('RELEASE acceptance_default')
                self.db.event(tx,task_id,'acceptance.unavailable',{})
        return task_id

    def get(self, task_id):
        task = self.db.one("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not task:
            raise CoreError("not_found", "Task does not exist")
        task["body"] = decode(task["body"])
        task["bindings"] = decode(task["bindings"])
        return task

    def actions(self, task_id):
        return self.db.all("SELECT * FROM actions WHERE task_id=? ORDER BY rowid", (task_id,))

    def cancel(self, task_id, *, transaction=None):
        self.get(task_id)
        with (nullcontext(transaction) if transaction is not None else self.db.transaction()) as tx:
            changed = tx.execute("UPDATE tasks SET cancel=1,status=CASE WHEN status='RUNNING' THEN status ELSE 'CANCELLED' END,"
                       "revision=revision+1 WHERE id=? AND cancel=0 AND status NOT IN ('SUCCEEDED','FAILED','CANCELLED')", (task_id,)).rowcount
            if changed:
                self.db.event(tx, task_id, "task.cancel_requested", {})
            return bool(changed)

    def state(self, task_id, state, error=None):
        with self.db.transaction() as tx:
            tx.execute("UPDATE tasks SET status=?,error=?,revision=revision+1 WHERE id=?", (state, error, task_id))
            self.db.event(tx, task_id, "task." + state.lower(), {"code": error})

    def recover(self):
        """Caller holds the execution lock; unfinished effects are never replayed."""
        with self.db.transaction() as tx:
            count = tx.execute("UPDATE actions SET status='UNKNOWN',error='interrupted' WHERE status='DISPATCHING'").rowcount
            for row in tx.execute("SELECT * FROM tasks WHERE status='RUNNING'").fetchall():
                unknown = tx.execute("SELECT 1 FROM actions WHERE task_id=? AND status='UNKNOWN'", (row["id"],)).fetchone()
                state = "CANCELLED" if row["cancel"] else ("WAITING" if unknown else "READY")
                tx.execute("UPDATE tasks SET status=?,revision=revision+1 WHERE id=?", (state, row["id"]))
                self.db.event(tx, row["id"], "task.recovered", {"state": state})
        return {"unknown_actions": count}

    def resume(self, task_id):
        self.gate.require_running()
        task = self.get(task_id)
        if task["status"] != "WAITING" or task["cancel"]:
            raise CoreError("invalid_state", "Only a waiting, non-cancelled task may resume")
        if any(a["status"] == "UNKNOWN" for a in self.actions(task_id)):
            raise CoreError("unknown_effect", "Reconcile unknown effects before resuming")
        self.state(task_id, "READY")

    def prepare(self, task_id, step, arguments):
        action_id = "action-" + digest({"task": task_id, "step": step["step_id"]})[:32]
        hashed = digest({"capability": step["capability"], "arguments": arguments})
        with self.db.transaction() as tx:
            old = tx.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if old and old["digest"] != hashed:
                raise CoreError("conflict", "Action ID reused with different arguments")
            if not old:
                tx.execute("INSERT INTO actions(id,task_id,step_id,capability,arguments,digest,status) VALUES(?,?,?,?,?,?,'PREPARED')",
                           (action_id, task_id, step["step_id"], step["capability"], canonical(arguments), hashed))
        return self.db.one("SELECT * FROM actions WHERE id=?", (action_id,))

    def dispatch(self, task_id, action_id):
        with self.db.transaction() as tx:
            self.gate.require_running()
            task = tx.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            action = tx.execute("SELECT * FROM actions WHERE id=? AND task_id=?", (action_id, task_id)).fetchone()
            if task["cancel"]:
                raise CoreError("cancelled", "Task cancelled")
            if task["deadline"] <= time.time():
                raise CoreError("deadline", "Task deadline exceeded")
            body = decode(task["body"])
            if task["status"] != "RUNNING" or not action or action["status"] != "PREPARED":
                raise CoreError("invalid_state", "Action is not dispatchable")
            if action["attempts"] >= body["limits"]["max_attempts"] or task["spent"] >= body["limits"]["max_cost_units"]:
                raise CoreError("budget_exhausted", "Task attempt or cost budget exhausted")
            from modules.task_resource.work_budgets import WorkBudgets
            WorkBudgets(self.db).check_dispatch(task_id)
            GrantStore.authorize(tx, body, action["capability"], charge=1)
            tx.execute("UPDATE tasks SET spent=spent+1,revision=revision+1 WHERE id=?", (task_id,))
            tx.execute("UPDATE actions SET status='DISPATCHING',attempts=attempts+1 WHERE id=?", (action_id,))
            self.db.event(tx, task_id, "action.dispatching", {"action_id": action_id})

    def confirm(self, task_id, action_id, result):
        with self.db.transaction() as tx:
            action = tx.execute("SELECT * FROM actions WHERE id=? AND task_id=?", (action_id, task_id)).fetchone()
            if not action or action["status"] not in {"DISPATCHING", "UNKNOWN"}:
                raise CoreError("invalid_state", "Action cannot be confirmed")
            tx.execute("UPDATE actions SET status='CONFIRMED',result=?,error=NULL WHERE id=?", (canonical(result), action_id))
            tx.execute("UPDATE tasks SET next_step=next_step+1,revision=revision+1 WHERE id=?", (task_id,))
            self.db.event(tx, task_id, "action.confirmed", {"action_id": action_id})

    def uncertain(self, task_id, action_id, error='execution_uncertain'):
        with self.db.transaction() as tx:
            tx.execute("UPDATE actions SET status='UNKNOWN',error=? WHERE id=?", (error, action_id))
        self.state(task_id, "CANCELLED" if self.get(task_id)["cancel"] else "WAITING", "unknown_effect")

    def retry(self, task_id, action_id):
        with self.db.transaction() as tx:
            tx.execute("UPDATE actions SET status='PREPARED',error='transient_no_effect' WHERE id=? AND status='DISPATCHING'",
                       (action_id,))
            self.db.event(tx, task_id, "action.retry", {"action_id": action_id})
