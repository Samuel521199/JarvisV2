from __future__ import annotations

import math
import time
import uuid
from contextlib import nullcontext

from control.policy.grants import GrantStore
from sdk.protocol import CoreError, PROJECT, canonical, contract, decode, digest, read_json


class Development:
    def __init__(self, db, gate, models, packages, tasks, run_task, execution_scope=nullcontext, publication_check=lambda *_: None, parent_check=lambda *_: None):
        self.db, self.gate, self.models = db, gate, models
        self.packages, self.tasks, self.run_task = packages, tasks, run_task
        self.execution_scope = execution_scope
        self.publication_check = publication_check
        self.parent_check = parent_check

    def get(self, ident):
        row = self.db.one("SELECT * FROM development_runs WHERE id=?", (ident,))
        if not row: raise CoreError("not_found", "Development run does not exist")
        row["spec"] = decode(row["spec"])
        return row

    def submit(self, spec, *, transaction=None):
        contract("development", spec)
        signature = digest(spec)
        old = self.db.one("SELECT id,digest FROM development_runs WHERE request_id=?", (spec["request_id"],))
        if old:
            if old["digest"] != signature: raise CoreError("conflict", "Development request ID reused")
            return old["id"]
        self.gate.require_running()
        with (nullcontext(transaction) if transaction is not None else self.db.transaction()) as tx:
            for capability in ("model.generate.v1", "development.build.v1", "release.activate.v1", spec["capability"], "artifact.write.v1"):
                GrantStore.authorize(tx, spec, capability)
            ident = "dev-" + uuid.uuid4().hex
            now = time.time()
            tx.execute("INSERT INTO development_runs(id,request_id,digest,spec,status,created,deadline) VALUES(?,?,?,?,'READY',?,?)",
                       (ident, spec["request_id"], signature, canonical(spec), now, now + spec["limits"]["max_seconds"]))
            self.db.event(tx, None, "development.accepted", {"run_id": ident})
        return ident

    def checkpoint(self, ident, capability="development.build.v1", charge=0):
        self.gate.require_running()
        self.parent_check(ident)
        row = self.get(ident)
        if row["cancel"]: raise CoreError("cancelled", "Development cancelled")
        if row["deadline"] <= time.time(): raise CoreError("deadline", "Development deadline reached")
        with self.db.transaction() as tx:
            GrantStore.authorize(tx, row["spec"], capability, charge=charge)

    def update(self, ident, **fields):
        allowed = {"status", "phase", "attempt", "candidate", "release_id", "task_id", "error", "plan"}
        if not fields or not set(fields) <= allowed: raise CoreError("internal", "Invalid development transition")
        with self.db.transaction() as tx:
            tx.execute("UPDATE development_runs SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?", (*fields.values(), ident))
            self.db.event(tx, None, "development.transition", {"run_id": ident, "phase": fields.get("phase"), "status": fields.get("status")})

    def cancel(self, ident, *, transaction=None):
        row = self.get(ident)
        if row["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}: return False
        with (nullcontext(transaction) if transaction is not None else self.db.transaction()) as tx:
            tx.execute("UPDATE development_runs SET cancel=1,status=CASE WHEN status='RUNNING' THEN status ELSE 'CANCELLED' END WHERE id=?", (ident,))
            if row["task_id"]: self.tasks.cancel(row["task_id"],transaction=tx)
        return True

    def execute(self, ident, network_enabled=False):
        row = self.get(ident)
        if row["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}: return row
        spec = row["spec"]
        check = lambda: self.checkpoint(ident)
        def model(phase, payload, schema):
            schema_body = read_json(PROJECT / "contracts/schemas" / (schema + ".v1.json"))
            prompt = canonical({"instruction": payload, "output_schema": schema_body})
            return self.models.request(ident, phase, prompt, schema, spec, spec["limits"]["max_model_calls"], check, network_enabled)
        try:
            check(); self.update(ident, status="RUNNING", error=None)
            # Only goal, contract and public examples leave the host. Expected private
            # evaluation cases, identity store, grant and task DB never reach a model.
            brief = {"goal": spec["goal"], "capability": spec["capability"], "contract": spec["description"], "examples": spec["public_cases"]}
            if not row["plan"]:
                plan = model("plan", {"role": "planner", "brief": brief,
                    "task": "Plan a pure text transformation tool. Choose implementation steps; never request permissions or external effects."}, "development-plan")
                if plan["capability"] != spec["capability"]:
                    raise CoreError("plan_scope", "Model changed the approved capability")
                self.update(ident, plan=canonical(plan), phase="code")
            while True:
                row = self.get(ident)
                check()
                if row["task_id"]:
                    task = self.tasks.get(row["task_id"])
                    if task["status"] in {"READY", "WAITING"}:
                        if task['status']=='WAITING':
                            with self.execution_scope(): self.tasks.resume(task['id'])
                        self.run_task(task["id"])
                    task = self.tasks.get(task["id"])
                    self.update(ident, status="SUCCEEDED" if task["status"] == "SUCCEEDED" else "WAITING", phase="delivered" if task["status"] == "SUCCEEDED" else "task", error=task["error"])
                    return self.get(ident)
                if row["phase"] in {"verified", "activated"}:
                    package = row["release_id"]
                    self.publication_check(ident, package)
                    self.checkpoint(ident, "release.activate.v1")
                    slot = self.packages.slot(spec["capability"])
                    with self.execution_scope():
                        self.packages.activate(package, slot["revision"] if slot else 0,
                            lambda: self.checkpoint(ident, "release.activate.v1"))
                    self.update(ident, phase="activated")
                    check()
                    existing = self.db.one("SELECT id FROM tasks WHERE request_id=?", (ident + ".delivery",))
                    if existing:
                        self.update(ident, task_id=existing["id"], phase="task")
                        continue
                    body = {"schema": "jarvis.task.v1", "request_id": ident + ".delivery",
                        "principal_id": spec["principal_id"], "scope_id": spec["scope_id"], "grant_id": spec["grant_id"], "goal": spec["goal"],
                        "steps": [{"step_id": "use", "capability": spec["capability"], "arguments": {"text": spec["sample_input"]}},
                                  {"step_id": "deliver", "capability": "artifact.write.v1", "arguments": {"name": "result.json"}, "input_from": "use"}],
                        "limits": {"max_steps": 2, "max_attempts": 1, "max_seconds": max(1, math.floor(row["deadline"] - time.time())), "max_cost_units": 2}}
                    task = self.tasks.submit(body)
                    self.update(ident, task_id=task, phase="task")
                    continue
                if row["attempt"] >= spec["limits"]["max_attempts"]:
                    raise CoreError("development_attempts", "Bounded development attempts exhausted")
                recipe = read_json(PROJECT / "seed/skills/pure-tool-development.json")
                phase = "code-" + str(row["attempt"])
                candidate = self.models.cached(ident, phase) or model(phase, {"role": "coder", "brief": brief, "plan": decode(self.get(ident)["plan"]),
                    "recipe": recipe, "previous_failure": row["error"],
                    "previous_candidate": decode(row["candidate"]) if row["candidate"] else None}, "code-candidate")
                self.checkpoint(ident)
                self.update(ident, candidate=canonical(candidate))
                try:
                    package = self.packages.stage(candidate, spec)
                    with self.execution_scope():
                        self.checkpoint(ident, charge=1)
                        report = self.packages.verify(package, check)
                    if not report["passed"]: raise CoreError("evaluation_failed", "Independent evaluation rejected candidate")
                    self.update(ident, release_id=package, phase="verified")
                except CoreError as exc:
                    if exc.code in {"stopped", "cancelled", "denied", "deadline", "budget_exhausted", "busy"}: raise
                    self.update(ident, attempt=row["attempt"] + 1, error=exc.code, phase="code")
        except CoreError as exc:
            state = "CANCELLED" if exc.code == "cancelled" or self.get(ident)['cancel'] else ("FAILED" if exc.code in {"deadline", "development_attempts", "plan_scope"} else "WAITING")
            self.update(ident, status=state, error=exc.code)
            return self.get(ident)

    def recover(self):
        with self.db.transaction() as tx:
            return tx.execute("UPDATE development_runs SET status='WAITING',error='host_interrupted' WHERE status='RUNNING'").rowcount
