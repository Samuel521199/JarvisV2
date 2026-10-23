"""Local owner-operated CLI. Run with Python -I -B; no server is exposed."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from control.paths import data_root
from control.recovery.gate import StopGate, RunLock
from host.core import Core
from sdk.protocol import CoreError, canonical, decode, read_json


def parser():
    p = argparse.ArgumentParser(description="Jarvis deterministic core / 确定性核心")
    p.add_argument("--data-root", default=None)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("init", "status", "tasks", "modules", "events"):
        sub.add_parser(name)
    for name in ("worker-prepare", "worker-status", "development-runs", "releases"):
        sub.add_parser(name)
    q = sub.add_parser("develop"); q.add_argument("file"); q.add_argument("--network", action="store_true")
    q = sub.add_parser("dev-resume"); q.add_argument("id"); q.add_argument("--network", action="store_true"); q.add_argument("--retry-unknown", action="store_true")
    for name in ("dev-status", "dev-cancel"):
        q = sub.add_parser(name); q.add_argument("id")
    q = sub.add_parser("release")
    q.add_argument("operation", choices=["probe", "activate", "rollback", "retire", "disable"])
    q.add_argument("id"); q.add_argument("--revision", type=int)
    for name in ("submit", "grant-add"):
        q = sub.add_parser(name); q.add_argument("file")
    q = sub.add_parser("run"); q.add_argument("--max-tasks", type=int, default=100)
    for name in ("task", "cancel", "resume-task", "reconcile", "grant-revoke"):
        q = sub.add_parser(name); q.add_argument("id")
    q = sub.add_parser("stop"); q.add_argument("--latch", action="store_true")
    q = sub.add_parser("resume"); q.add_argument("--token", required=True)
    q = sub.add_parser("module")
    q.add_argument("operation", choices=["probe", "start", "stop", "activate", "rollback"])
    q.add_argument("id"); q.add_argument("--revision", type=int); q.add_argument("--implementation")
    for name in ("facts", "fact-put", "fact-forget"):
        q = sub.add_parser(name)
        q.add_argument("--principal", default="owner.local"); q.add_argument("--scope", default="personal")
        if name != "facts":
            q.add_argument("--key", required=True); q.add_argument("--revision", type=int, required=True)
        if name == "fact-put":
            q.add_argument("--value", required=True); q.add_argument("--source", required=True)
    return p


def execute(args):
    config = tomllib.loads((ROOT / "config/defaults.toml").read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or config.get("network_enabled") is not False:
        raise CoreError("unsupported_config", "Only local/offline configuration is supported")
    root = args.data_root or ROOT / config["data_root"]
    if args.command == "stop":
        gate = StopGate(data_root(root))
        return {"control": gate.stop(latch=args.latch), "stop_token": gate.token()}
    if args.command == "resume":
        gate = StopGate(data_root(root))
        with RunLock(gate.root):
            gate.resume(args.token)
        return {"control": gate.state()}
    core = Core.initialize(root) if args.command == "init" else Core(root)
    try:
        cmd = args.command
        if cmd == "worker-prepare":
            with RunLock(core.root): return core.worker.prepare()
        if cmd == "worker-status": return core.worker.verify()
        if cmd == "develop":
            ident = core.development.submit(read_json(Path(args.file)))
            return core.develop(ident, args.network)
        if cmd == "dev-resume": return core.develop(args.id, args.network, args.retry_unknown)
        if cmd == "dev-status":
            return {"run": core.development.get(args.id), "calls": core.db.all("SELECT id,phase,provider,status,reservation,usage,error FROM model_calls WHERE run_id=? ORDER BY created", (args.id,))}
        if cmd == "dev-cancel": return {"cancel_requested": core.development.cancel(args.id)}
        if cmd == "development-runs": return core.db.all("SELECT id,status,phase,attempt,task_id,error FROM development_runs ORDER BY created")
        if cmd == "releases": return {"slots": core.db.all("SELECT * FROM release_slots"), "packages": core.db.all("SELECT id,capability,status,report FROM packages ORDER BY created")}
        if cmd == "release":
            with RunLock(core.root):
                if args.operation == "probe": return core.packages.evaluate(args.id, core.gate.require_running)
                if args.operation == "retire": return core.packages.retire(args.id)
                if args.revision is None: raise CoreError("revision_required", "Observed release revision required")
                if args.operation == "activate": return core.packages.activate(args.id, args.revision, core.gate.require_running)
                if args.operation == "rollback": return core.packages.rollback(args.id, args.revision, core.gate.require_running)
                with core.db.transaction() as tx:
                    if tx.execute("UPDATE release_slots SET enabled=0,revision=revision+1 WHERE capability=? AND revision=?", (args.id, args.revision)).rowcount != 1:
                        raise CoreError("conflict", "Release revision changed")
                return core.packages.slot(args.id)
        if cmd in {"init", "status"}:
            return core.status()
        if cmd == "submit":
            return {"task_id": core.tasks.submit(read_json(Path(args.file)))}
        if cmd == "run":
            return core.run(args.max_tasks)
        if cmd == "tasks":
            return core.db.all("SELECT id,request_id,status,revision,spent,error FROM tasks ORDER BY created")
        if cmd == "task":
            return {"task": core.tasks.get(args.id), "actions": core.tasks.actions(args.id)}
        if cmd == "events":
            return core.db.all("SELECT * FROM events ORDER BY seq DESC LIMIT 100")
        if cmd == "cancel":
            changed = core.tasks.cancel(args.id)
            return {"task_id": args.id, "cancel_requested": changed, "status": core.tasks.get(args.id)["status"]}
        if cmd == "resume-task":
            with RunLock(core.root):
                core.tasks.resume(args.id)
            return {"task_id": args.id, "state": "READY"}
        if cmd == "reconcile":
            return core.reconcile(args.id)
        if cmd == "grant-add":
            return {"grant_id": core.grants.add(read_json(Path(args.file)))}
        if cmd == "grant-revoke":
            core.grants.revoke(args.id)
            return {"grant_id": args.id, "revoked": True}
        if cmd == "modules":
            return core.registry.describe()
        if cmd == "module":
            if args.operation == "probe":
                return core.registry.probe(args.id, args.implementation)
            if args.revision is None:
                raise CoreError("revision_required", "Lifecycle changes require the observed revision")
            return core.change_module(args.id, args.operation, args.revision, args.implementation)
        if cmd == "facts":
            return core.facts.view(args.principal, args.scope)
        if cmd == "fact-put":
            value = {"schema": "jarvis.fact.v1", "principal_id": args.principal, "scope_id": args.scope,
                     "key": args.key, "value": args.value, "source": args.source}
            return {"fact_id": core.facts.put(value, args.revision)}
        if cmd == "fact-forget":
            core.facts.forget(args.principal, args.scope, args.key, args.revision)
            return {"forgotten": True}
        raise CoreError("unsupported", "Unsupported command")
    finally:
        core.close()


def main():
    try:
        result = execute(parser().parse_args())
        print(canonical({"ok": True, "result": result}))
        return 0
    except CoreError as exc:
        print(canonical({"ok": False, "error": {"code": exc.code, "message": str(exc)}}))
        return 2
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(canonical({"ok": False, "error": {"code": "local_io_or_config", "message": type(exc).__name__}}))
        return 3


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
