from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from control.paths import child
from control.recovery.gate import RunLock
from host.core import Core
from modules.model_gateway import ModelGateway
from modules.registry_composer.registry import Registry
from sdk.protocol import CoreError, RetryableError, canonical, contract, decode, validate


def task(request="test", scope="personal", principal="owner.local", artifact=False):
    steps = [{"step_id": "analyze", "capability": "text.analyze.v1", "arguments": {"text": "hello world\n"}}]
    if artifact:
        steps.append({"step_id": "deliver", "capability": "artifact.write.v1", "arguments": {"name": "report.json"}, "input_from": "analyze"})
    return {"schema": "jarvis.task.v1", "request_id": request, "principal_id": principal, "scope_id": scope,
            "goal": "Analyze supplied text", "grant_id": "local-default", "steps": steps,
            "limits": {"max_steps": 8, "max_attempts": 2, "max_seconds": 60, "max_cost_units": 8}}


class CoreCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-core-test-")
        self.root = Path(self.temp.name).resolve()
        assert self.root.parent == Path(tempfile.gettempdir()).resolve()
        assert self.root.name.startswith("jarvis-core-test-")
        self.core = Core.initialize(self.root)

    def tearDown(self):
        self.core.close()
        self.temp.cleanup()

    def assertCode(self, code, function, *args):
        with self.assertRaises(CoreError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)

    def test_end_to_end_verified_report_and_no_duplicate_effect(self):
        body = task(artifact=True)
        ident = self.core.tasks.submit(body)
        self.assertEqual(self.core.tasks.submit(body), ident)
        self.core.run()
        result = self.core.tasks.get(ident)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["spent"], 2)
        actions = self.core.tasks.actions(ident)
        self.assertEqual([a["status"] for a in actions], ["CONFIRMED", "CONFIRMED"])
        receipt = decode(actions[1]["result"])
        report = self.root / receipt["relative_path"]
        self.assertEqual(json.loads(report.read_text()), {"characters": 12, "lines": 1, "words": 2, "utf8_bytes": 12})
        stamp = report.stat().st_mtime_ns
        self.core.run()
        self.assertEqual(report.stat().st_mtime_ns, stamp)
        self.assertEqual(self.core.tasks.get(ident)["spent"], 2)

    def test_request_key_conflicts_on_different_payload(self):
        body = task(); self.core.tasks.submit(body)
        body["goal"] = "different goal"
        self.assertCode("conflict", self.core.tasks.submit, body)

    def test_contracts_reject_unknown_fields_versions_and_boolean_limits(self):
        for mutate in (lambda x: x.update(unknown=True), lambda x: x.update(schema="jarvis.task.v2"),
                       lambda x: x["limits"].update(max_attempts=True),
                       lambda x: x["limits"].update(max_attempts=10 ** 500)):
            body = task(); mutate(body)
            self.assertCode("invalid_contract", contract, "task", body)

    def test_json_duplicate_keys_nonfinite_and_size_rejected(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', b'\xff', b'"\\ud800"'):
            self.assertCode("invalid_json", decode, raw)
        self.assertCode("message_too_large", decode, "x" * 262145)
        self.assertCode("unsupported_schema", validate, {"type": "string", "anyOf": []}, "x")

    def test_family_and_group_cannot_use_owner_grant(self):
        self.assertCode("denied", self.core.tasks.submit, task(principal="family.member"))
        self.assertCode("denied", self.core.tasks.submit, task(scope="group.study"))
        self.assertEqual(self.core.db.all("SELECT id FROM tasks"), [])

    def test_explicit_member_grant_and_scope(self):
        self.core.grants.add({"schema": "jarvis.grant.v1", "grant_id": "member-allowed",
            "principal_id": "family.member", "scope_id": "family.shared", "capabilities": ["text.analyze.v1"],
            "max_cost_units": 3, "expires_at": time.time() + 3600})
        body = task(principal="family.member", scope="family.shared"); body["grant_id"] = "member-allowed"
        ident = self.core.tasks.submit(body); self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["status"], "SUCCEEDED")
        body["request_id"] = "wrong-scope"; body["scope_id"] = "personal"
        self.assertCode("denied", self.core.tasks.submit, body)

    def test_revocation_between_admission_and_execution(self):
        ident = self.core.tasks.submit(task())
        self.core.grants.revoke("local-default")
        self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["status"], "WAITING")
        self.assertEqual(self.core.tasks.get(ident)["spent"], 0)
        other = Core.initialize(self.root)
        try:
            self.assertCode("denied", other.tasks.submit, task("after-reinit"))
        finally:
            other.close()

    def test_revocation_between_steps_prevents_second_effect(self):
        ident = self.core.tasks.submit(task(artifact=True))
        execute = self.core._execute
        def revoke(*args):
            value = execute(*args)
            self.core.grants.revoke("local-default")
            return value
        with patch.object(self.core, "_execute", side_effect=revoke):
            self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["status"], "WAITING")
        self.assertEqual(list((self.root / "artifacts").rglob("*.json")), [])

    def test_shared_budget_cannot_be_reset_by_new_task(self):
        grant = {"schema": "jarvis.grant.v1", "grant_id": "small", "principal_id": "owner.local",
                 "scope_id": "personal", "capabilities": ["text.analyze.v1"], "max_cost_units": 1,
                 "expires_at": time.time() + 3600}
        self.core.grants.add(grant)
        ids = []
        for key in ("one", "two"):
            body = task(key); body["grant_id"] = "small"; ids.append(self.core.tasks.submit(body))
        self.core.run()
        self.assertEqual([self.core.tasks.get(i)["status"] for i in ids], ["SUCCEEDED", "FAILED"])
        self.assertEqual(self.core.db.one("SELECT spent FROM grants WHERE id='small'")["spent"], 1)

    def test_safe_retry_is_bounded_persistent_and_other_task_runs(self):
        bad, good = self.core.tasks.submit(task("bad")), self.core.tasks.submit(task("good"))
        execute = self.core._execute
        def fail_selected(*args):
            if args[0] == bad:
                raise RetryableError("temporary")
            return execute(*args)
        with patch.object(self.core, "_execute", side_effect=fail_selected):
            self.core.run()
        self.assertEqual(self.core.tasks.get(bad)["status"], "FAILED")
        self.assertEqual(self.core.tasks.actions(bad)[0]["attempts"], 2)
        self.assertEqual(self.core.tasks.get(bad)["spent"], 2)
        self.assertEqual(self.core.tasks.get(good)["status"], "SUCCEEDED")

    def test_known_safe_transient_failure_can_recover(self):
        ident = self.core.tasks.submit(task())
        execute = self.core._execute
        calls = []
        def fail_once(*args):
            calls.append(1)
            if len(calls) == 1:
                raise RetryableError("temporary")
            return execute(*args)
        with patch.object(self.core, "_execute", side_effect=fail_once):
            self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["status"], "SUCCEEDED")
        self.assertEqual(self.core.tasks.get(ident)["spent"], 2)

    def test_late_or_duplicate_cancel_reports_no_new_change(self):
        done = self.core.tasks.submit(task("done")); self.core.run()
        self.assertFalse(self.core.tasks.cancel(done))
        self.assertEqual(self.core.tasks.get(done)["status"], "SUCCEEDED")
        waiting = self.core.tasks.submit(task("waiting"))
        self.assertTrue(self.core.tasks.cancel(waiting))
        self.assertFalse(self.core.tasks.cancel(waiting))

    def test_deadline_survives_restart(self):
        ident = self.core.tasks.submit(task())
        with self.core.db.transaction() as tx:
            tx.execute("UPDATE tasks SET deadline=? WHERE id=?", (time.time() - 1, ident))
        self.core.close(); self.core = Core(self.root); self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["error"], "deadline")
        self.assertEqual(self.core.tasks.actions(ident), [])

    def test_cancel_before_run_and_during_confirmed_effect(self):
        before = self.core.tasks.submit(task("before")); self.core.tasks.cancel(before)
        during = self.core.tasks.submit(task("during", artifact=True))
        execute = self.core._execute
        def cancel(*args):
            result = execute(*args)
            self.core.tasks.cancel(during)
            return result
        with patch.object(self.core, "_execute", side_effect=cancel):
            self.core.run()
        self.assertEqual(self.core.tasks.get(before)["status"], "CANCELLED")
        self.assertEqual(self.core.tasks.actions(before), [])
        self.assertEqual(self.core.tasks.get(during)["status"], "CANCELLED")
        self.assertEqual(len(self.core.tasks.actions(during)), 1)
        self.assertCode("invalid_state", self.core.tasks.resume, during)

    def test_stop_resume_generation_and_persistent_latch(self):
        self.core.gate.stop(); token = self.core.gate.token()
        self.assertCode("stopped", self.core.tasks.submit, task())
        self.assertCode("conflict", self.core.gate.resume, "wrong")
        self.core.gate.resume(token)
        ident = self.core.tasks.submit(task())
        self.core.gate.stop(latch=True)
        self.assertCode("stopped", self.core.run)
        self.assertCode("latched", self.core.gate.resume, token)
        self.assertEqual(self.core.tasks.get(ident)["status"], "READY")
        self.core.close(); self.core = Core(self.root)
        self.assertEqual(self.core.gate.state(), "latched")

    def test_stop_between_steps_keeps_checkpoint_and_other_state(self):
        ident = self.core.tasks.submit(task(artifact=True))
        execute = self.core._execute
        def stop_after_step(*args):
            result = execute(*args); self.core.gate.stop(); return result
        with patch.object(self.core, "_execute", side_effect=stop_after_step):
            self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["next_step"], 1)
        self.assertEqual(self.core.tasks.get(ident)["status"], "WAITING")
        self.core.gate.resume(self.core.gate.token()); self.core.tasks.resume(ident); self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["status"], "SUCCEEDED")
        self.assertEqual(self.core.tasks.get(ident)["spent"], 2)

    def crash(self, mode):
        body = task(); body["steps"] = [{"step_id": "write", "capability": "artifact.write.v1",
                                        "arguments": {"name": "proof.txt", "content": "verified"}}]
        ident = self.core.tasks.submit(body)
        result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "tests/crash_worker.py"), mode, str(self.root)],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertEqual(self.core.tasks.actions(ident)[0]["status"], "DISPATCHING")
        self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["status"], "WAITING")
        self.assertEqual(self.core.tasks.actions(ident)[0]["status"], "UNKNOWN")
        return ident

    def test_process_crash_after_write_reconciles_without_duplicate(self):
        ident = self.crash("after-effect")
        files = list((self.root / "artifacts").rglob("proof.txt")); self.assertEqual(len(files), 1)
        stamp = files[0].stat().st_mtime_ns
        self.assertCode("unknown_effect", self.core.tasks.resume, ident)
        self.core.reconcile(ident); self.core.tasks.resume(ident); self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["status"], "SUCCEEDED")
        self.assertEqual(files[0].stat().st_mtime_ns, stamp)
        self.assertEqual(self.core.tasks.get(ident)["spent"], 1)

    def test_process_crash_before_write_remains_unknown(self):
        ident = self.crash("before-effect")
        self.assertCode("unknown_effect", self.core.reconcile, ident)
        self.core.run()
        self.assertEqual(self.core.tasks.actions(ident)[0]["attempts"], 1)
        self.assertEqual(list((self.root / "artifacts").rglob("proof.txt")), [])

    def test_partial_existing_artifact_is_never_overwritten(self):
        ident = self.crash("before-effect")
        action = self.core.tasks.actions(ident)[0]
        path = self.root / "artifacts" / ident / action["id"] / "proof.txt"
        path.parent.mkdir(parents=True); path.write_text("part")
        self.assertCode("unknown_effect", self.core.reconcile, ident)
        self.assertEqual(path.read_text(), "part")

    def test_execution_lock_is_cross_process_and_released_after_death(self):
        worker = subprocess.Popen([sys.executable, "-I", "-B", str(ROOT / "tests/crash_worker.py"), "hold-lock", str(self.root)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertEqual(worker.stdout.readline().strip(), b"locked")
            self.assertCode("busy", self.core.run)
        finally:
            worker.kill(); worker.communicate(timeout=5)
        with RunLock(self.root):
            pass

    def test_lifecycle_switch_rollback_preserves_identity_facts_and_queued_binding(self):
        identity = self.core.identity.describe()
        ident = self.core.tasks.submit(task())
        self.core.change_module("text-analyzer", "activate", 1, "text.scan.v1")
        self.assertEqual(self.core.tasks.get(ident)["bindings"]["text.analyze.v1"], "text.basic.v1")
        self.core.run()
        self.core.change_module("text-analyzer", "rollback", 2)
        self.assertEqual(self.core.registry.binding("text.analyze.v1"), "text.basic.v1")
        self.assertEqual(self.core.identity.describe(), identity)
        self.assertCode("conflict", self.core.change_module, "text-analyzer", "stop", 1)

    def test_disabled_module_waits_then_resumes(self):
        ident = self.core.tasks.submit(task())
        self.core.change_module("text-analyzer", "stop", 1)
        self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["error"], "module_disabled")
        self.core.change_module("text-analyzer", "start", 2)
        self.core.tasks.resume(ident); self.core.run()
        self.assertEqual(self.core.tasks.get(ident)["status"], "SUCCEEDED")

    def test_arbitrary_module_provider_and_manifest_tampering_rejected(self):
        self.assertCode("unsupported_module", self.core.registry.manifest, "downloaded-code")
        self.assertCode("unsupported_provider", self.core.change_module, "text-analyzer", "activate", 1, "os.system")
        project = self.root / "fixture-project"
        for relative in ("modules/registry_composer/manifests/text-analyzer.json", "modules/registry_composer/builtins.py"):
            dest = project / relative; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, dest)
        (project / "modules/registry_composer/builtins.py").write_text("raise SystemExit('must not execute')")
        self.assertCode("package_changed", Registry(self.core.db, project).manifest, "text-analyzer")

    def test_facts_correction_deletion_scope_and_restart(self):
        fact = {"schema": "jarvis.fact.v1", "principal_id": "owner.local", "scope_id": "personal",
                "key": "style", "value": "brief", "source": "explicit-owner-input"}
        ident = self.core.facts.put(fact, 0)
        self.assertEqual(self.core.facts.view("family.member", "personal"), [])
        self.assertEqual(self.core.facts.view("owner.local", "family.shared"), [])
        fact["value"] = "detailed"; self.core.facts.put(fact, 1)
        self.assertCode("conflict", self.core.facts.put, fact, 1)
        self.core.facts.forget("owner.local", "personal", "style", 2)
        self.core.close(); self.core = Core(self.root)
        self.assertEqual(self.core.facts.view("owner.local", "personal"), [])
        self.assertCode("conflict", self.core.facts.put, fact, 2)
        self.assertEqual(self.core.db.one("SELECT value,deleted FROM facts WHERE id=?", (ident,)), {"value": "", "deleted": 1})

    def test_path_traversal_windows_devices_and_unknown_capabilities(self):
        for name in ("../escape", "D:/outside", "report.txt:secret"):
            self.assertCode("unsafe_path", child, self.root, name)
        for name in ("CON", "nul.txt", "a.", "../x", "C:x"):
            self.assertCode("invalid_arguments", self.core.registry.validate_arguments, "artifact.write.v1", {"name": name, "content": "x"})
        body = task(); body["steps"][0]["capability"] = "shell.execute.v1"
        self.assertCode("unsupported_capability", self.core.tasks.submit, body)

    def test_identity_missing_does_not_silently_create_new_assistant(self):
        with self.core.db.transaction() as tx:
            tx.execute("DELETE FROM meta WHERE key='identity'")
        self.assertCode("identity_missing", Core.initialize, self.root)

    def test_incomplete_initialization_never_masquerades_as_ready(self):
        with self.core.db.transaction() as tx:
            tx.execute("DELETE FROM meta WHERE key='initialization_complete'")
        self.assertCode("initialization_incomplete", Core.initialize, self.root)

    def test_module_missing_does_not_block_an_unrelated_capability(self):
        bad = self.core.tasks.submit(task("bad"))
        body = task("good"); body["steps"] = [{"step_id": "write", "capability": "artifact.write.v1",
                                             "arguments": {"name": "local.txt", "content": "ok"}}]
        good = self.core.tasks.submit(body)
        require = self.core.registry.require
        def missing(cap, impl):
            if cap == "text.analyze.v1":
                raise CoreError("package_unavailable", "missing")
            return require(cap, impl)
        with patch.object(self.core.registry, "require", side_effect=missing):
            self.core.run()
        self.assertEqual(self.core.tasks.get(bad)["status"], "WAITING")
        self.assertEqual(self.core.tasks.get(good)["status"], "SUCCEEDED")

    def test_proposal_kind_cannot_hide_effect_fields(self):
        self.assertCode("invalid_contract", contract, "step-proposal", {
            "schema": "jarvis.step-proposal.v1", "kind": "tool", "reason": "missing effect"})
        self.assertCode("invalid_contract", contract, "step-proposal", {
            "schema": "jarvis.step-proposal.v1", "kind": "finish", "reason": "done", "capability": "shell"})

    def test_model_fallback_is_only_proposal_and_never_expands_provider_list(self):
        called = []
        class Bad:
            def propose(self, context):
                called.append("bad"); context["x"] = 99; return {"unsupported": True}
        class Good:
            def propose(self, context):
                called.append("good")
                return {"schema": "jarvis.step-proposal.v1", "kind": "wait", "reason": "No external effect"}
        context = {"x": 1}
        gateway = ModelGateway({"bad": Bad(), "good": Good(), "forbidden": Good()})
        result = gateway.propose(context, ["forbidden", "bad", "good"], {"bad", "good"})
        self.assertEqual(result["provider"], "good")
        self.assertEqual(called, ["bad", "good"]); self.assertEqual(context, {"x": 1})
        self.assertFalse(self.core.models.describe()["configured"])
        self.assertCode("model_unavailable", self.core.models.propose, {}, ["good"], {"good"})


if __name__ == "__main__":
    unittest.main()
