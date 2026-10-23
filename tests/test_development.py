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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host.core import Core
from sdk.protocol import CoreError, canonical, decode
from control.recovery.gate import RunLock
from modules.autonomous_development.service import Development
from modules.model_gateway.routed import RoutedModels
from modules.release_recovery.packages import validate_candidate


def specification(request="test-dev"):
    return {"schema": "jarvis.development.v1", "request_id": request, "principal_id": "owner.local", "scope_id": "personal",
            "grant_id": "development-test", "goal": "Uppercase text", "capability": "plugin.upper.v1", "description": "Uppercase all Unicode letters; preserve whitespace.",
            "public_cases": [{"input": "hello", "expected": "HELLO"}], "evaluation_cases": [{"input": "héLLo\n", "expected": "HÉLLO\n"}, {"input": "", "expected": ""}],
            "sample_input": "Jarvis", "limits": {"max_attempts": 2, "max_model_calls": 5, "max_seconds": 120}}


def candidate(source="def run(text):\n    return text.upper()\n"):
    return {"schema": "jarvis.code-candidate.v1", "summary": "Text utility", "files": [{"path": "main.py", "content": source}]}


class Provider:
    def __init__(self, responses):
        self.responses, self.prompts = list(responses), []
        self.config = {"max_output_tokens": 4096, "model": "test-double"}
    def available(self): return True
    def generate(self, prompt, checkpoint):
        checkpoint(); self.prompts.append(prompt)
        value = self.responses.pop(0)
        return value if "status" in value else {"status": "SUCCEEDED", "value": value, "usage": {"total_tokens": 10}}


def plan():
    return {"schema": "jarvis.development-plan.v1", "capability": "plugin.upper.v1", "summary": "Pure conversion", "steps": ["Implement Unicode uppercase", "Check contract"]}


class DevelopmentCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use only the current independently prepared runtime, never an old runtime.
        cls.runtime_source = ROOT / "user-data/worker-runtime"
        if not cls.runtime_source.exists():
            from control.worker.runtime import RestrictedWorker
            with tempfile.TemporaryDirectory(prefix="jarvis-runtime-") as name:
                worker = RestrictedWorker(Path(name)); worker.prepare()
                cls.runtime_cache = tempfile.TemporaryDirectory(prefix="jarvis-runtime-cache-")
                cls.runtime_source = Path(cls.runtime_cache.name) / "runtime"
                shutil.copytree(worker.runtime, cls.runtime_source)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "runtime_cache"): cls.runtime_cache.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jarvis-development-")
        self.root = Path(self.temp.name).resolve()
        self.core = Core.initialize(self.root)
        shutil.copytree(self.runtime_source, self.root / "worker-runtime")
        self.core.grants.add({"schema": "jarvis.grant.v1", "grant_id": "development-test", "principal_id": "owner.local", "scope_id": "personal",
            "capabilities": ["model.generate.v1", "development.build.v1", "release.activate.v1", "plugin.upper.v1", "artifact.write.v1"],
            "max_cost_units": 30, "expires_at": time.time() + 3600})

    def tearDown(self):
        self.core.close(); self.temp.cleanup()

    def bind(self, responses, backup=None):
        self.provider = Provider(responses)
        providers = {"primary": self.provider}
        if backup: providers["backup"] = Provider(backup)
        gateway = RoutedModels(self.core.db, providers, list(providers))
        self.core.routed_models = gateway
        self.core.development = Development(self.core.db, self.core.gate, gateway, self.core.packages, self.core.tasks, self.core._development_task, lambda: RunLock(self.root))
        return gateway

    def assertCode(self, code, call, *args):
        with self.assertRaises(CoreError) as result: call(*args)
        self.assertEqual(code, result.exception.code)

    def test_real_worker_multi_file_closed_loop(self):
        value = candidate("from helper import transform\ndef run(text):\n    return transform(text)\n")
        value["files"].append({"path": "helper.py", "content": "def transform(text):\n    return text.upper()\n"})
        self.bind([plan(), value])
        ident = self.core.development.submit(specification())
        result = self.core.develop(ident, True)
        self.assertEqual(result["status"], "SUCCEEDED", result)
        task = self.core.tasks.get(result["task_id"])
        self.assertEqual(task["status"], "SUCCEEDED")
        output = decode(self.core.tasks.actions(task["id"])[0]["result"])
        self.assertEqual(output["text"], "JARVIS")
        self.assertEqual(self.core.develop(ident, True)["task_id"], task["id"])
        self.assertEqual(len(self.provider.prompts), 2)
        self.assertNotIn("HÉLLO", "\n".join(self.provider.prompts))
        self.assertNotIn("development-test", "\n".join(self.provider.prompts))

    def test_bounded_failed_candidate_then_repair(self):
        self.bind([plan(), candidate("def run(text):\n    return 'wrong'\n"), candidate()])
        ident = self.core.development.submit(specification())
        result = self.core.develop(ident, True)
        self.assertEqual(result["status"], "SUCCEEDED", result)
        self.assertEqual(result["attempt"], 1)
        self.assertEqual(self.core.db.one("SELECT COUNT(*) n FROM packages WHERE status='REJECTED'")["n"], 1)

    def test_no_grant_no_codegen_or_publication(self):
        self.bind([plan(), candidate()])
        self.core.grants.revoke("development-test")
        self.assertCode("denied", self.core.development.submit, specification())
        self.assertEqual(self.provider.prompts, [])

    def test_offline_does_not_call_model_and_resume_keeps_budget(self):
        self.bind([plan(), candidate()])
        ident = self.core.development.submit(specification())
        result = self.core.develop(ident)
        self.assertEqual(result["error"], "network_disabled")
        self.assertEqual(self.provider.prompts, [])
        self.assertEqual(self.core.develop(ident, True)["status"], "SUCCEEDED")

    def test_unknown_model_not_replayed_or_fallback_without_ack(self):
        gateway = self.bind([{"status": "UNKNOWN", "code": "timeout"}, plan(), candidate()], [plan(), candidate()])
        ident = self.core.development.submit(specification())
        self.assertEqual(self.core.develop(ident, True)["error"], "model_unknown")
        self.assertEqual(self.core.develop(ident, True)["error"], "model_unknown")
        self.assertEqual(len(self.provider.prompts), 1)
        self.assertEqual(gateway.providers["backup"].prompts, [])
        self.assertEqual(self.core.develop(ident, True, retry_unknown=True)["status"], "SUCCEEDED")
        self.assertEqual(self.core.db.one("SELECT COUNT(*) n FROM model_calls WHERE run_id=?", (ident,))["n"], 3)

    def test_definite_rejection_uses_configured_backup(self):
        gateway = self.bind([{"status": "REJECTED", "code": "http_404"}, candidate()], [plan()])
        ident = self.core.development.submit(specification())
        self.assertEqual(self.core.develop(ident, True)["status"], "SUCCEEDED")
        self.assertEqual(len(gateway.providers["backup"].prompts), 1)

    def test_cancel_leaves_other_tasks_available(self):
        self.bind([plan(), candidate()])
        ident = self.core.development.submit(specification())
        self.core.development.cancel(ident)
        self.assertEqual(self.core.develop(ident, True)["status"], "CANCELLED")
        self.assertEqual(self.provider.prompts, [])
        self.assertEqual(self.core.status()["control"], "ready")

    def test_waiting_for_model_does_not_occupy_executor_lane(self):
        self.bind([plan(), candidate()])
        generate = self.provider.generate
        def slow_model(prompt, checkpoint):
            if not self.provider.prompts:
                other = Core(self.root)
                try:
                    task = {"schema": "jarvis.task.v1", "request_id": "other-work", "principal_id": "owner.local", "scope_id": "personal", "grant_id": "local-default", "goal": "Separate work",
                            "steps": [{"step_id": "analyze", "capability": "text.analyze.v1", "arguments": {"text": "parallel work"}}],
                            "limits": {"max_steps": 1, "max_attempts": 1, "max_seconds": 60, "max_cost_units": 1}}
                    task_id = other.tasks.submit(task)
                    other.run()
                    self.assertEqual(other.tasks.get(task_id)["status"], "SUCCEEDED")
                    self.assertEqual(other.db.one("SELECT status FROM model_calls ORDER BY created DESC LIMIT 1")["status"], "DISPATCHING")
                finally: other.close()
            return generate(prompt, checkpoint)
        self.provider.generate = slow_model
        ident = self.core.development.submit(specification())
        self.assertEqual(self.core.develop(ident, True)["status"], "SUCCEEDED")

    def test_missing_worker_stops_before_spending_model_tokens(self):
        self.bind([plan(), candidate()])
        (self.root / "worker-runtime/manifest.json").unlink()
        ident = self.core.development.submit(specification())
        self.assertEqual(self.core.develop(ident, True)["error"], "worker_unavailable")
        self.assertEqual(self.provider.prompts, [])

    def install(self, source=None, request="test-dev", revision=0):
        package = self.core.packages.stage(candidate() if source is None else candidate(source), specification(request))
        self.assertTrue(self.core.packages.verify(package)["passed"])
        self.core.packages.activate(package, revision)
        return package

    def test_release_rollback_preserves_identity_revocation_and_correction(self):
        first = self.install()
        second = self.install("def run(text):\n    return ''.join(c.upper() for c in text)\n", "next", 1)
        identity = self.core.identity.describe()
        self.core.grants.revoke("development-test")
        self.core.packages.rollback("plugin.upper.v1", 2)
        self.assertEqual(self.core.packages.binding("plugin.upper.v1"), first)
        self.assertEqual(self.core.identity.describe(), identity)
        self.assertEqual(self.core.db.one("SELECT revoked FROM grants WHERE id='development-test'")["revoked"], 1)
        self.assertCode("release_in_use", self.core.packages.retire, second)

    def test_corrupt_active_package_auto_recovers_previous(self):
        first = self.install()
        second = self.install("def run(text):\n    return ''.join(c.upper() for c in text)\n", "next", 1)
        (self.root / "packages" / (second + ".json")).write_text("{}")
        result = self.core.packages.recover()
        self.assertEqual(result["repaired_slots"], ["plugin.upper.v1"])
        self.assertEqual(self.core.packages.binding("plugin.upper.v1"), first)

    def test_post_release_runtime_failure_quarantines_and_rolls_back(self):
        first = self.install()
        second = self.install("def run(text):\n    if text == 'boom': raise ValueError('fail')\n    return text.upper()\n", "next", 1)
        self.assertCode("worker_execution", self.core.packages.execute, "plugin.upper.v1", second, "boom")
        self.assertEqual(self.core.packages.binding("plugin.upper.v1"), first)
        self.assertEqual(self.core.db.one("SELECT status FROM packages WHERE id=?", (second,))["status"], "REJECTED")

    def test_first_release_failure_disables_slot(self):
        ident = self.install("def run(text):\n    if text == 'boom': raise ValueError('fail')\n    return text.upper()\n")
        self.assertCode("worker_execution", self.core.packages.execute, "plugin.upper.v1", ident, "boom")
        self.assertFalse(self.core.packages.slot("plugin.upper.v1")["enabled"])

    def test_canary_settles_only_after_successful_observations(self):
        ident = self.install()
        self.assertEqual(self.core.packages.get(ident)["status"], "CANARY")
        self.core.packages.execute("plugin.upper.v1", ident, "one")
        self.assertEqual(self.core.packages.get(ident)["status"], "CANARY")
        self.core.packages.execute("plugin.upper.v1", ident, "two")
        self.assertEqual(self.core.packages.get(ident)["status"], "STABLE")

    def test_release_generation_conflict_and_scope(self):
        ident = self.install()
        self.assertCode("conflict", self.core.packages.activate, ident, 0)
        self.assertCode("denied", self.core.packages.require_context, ident, {"principal_id": "friend", "scope_id": "personal"})

    def test_retirement_preserves_recovery_package_and_blocks_execution(self):
        first = self.install()
        second = self.install("def run(text):\n    return ''.join(c.upper() for c in text)\n", "second", 1)
        third = self.install("def run(text):\n    result = text.upper()\n    return result\n", "third", 2)
        self.assertCode("release_in_use", self.core.packages.retire, second)
        self.assertEqual(self.core.packages.retire(first)["retired"], first)
        self.assertCode("package_unavailable", self.core.packages.require, "plugin.upper.v1", first)
        self.assertEqual(self.core.packages.binding("plugin.upper.v1"), third)

    def test_result_receipt_recovers_without_reexecuting_candidate(self):
        self.bind([plan(), candidate()])
        ident = self.core.development.submit(specification())
        original = self.core.tasks.confirm
        def interrupt(task_id, action_id, result):
            if "package_id" in result: raise RuntimeError("simulate lost ledger confirmation")
            return original(task_id, action_id, result)
        self.core.tasks.confirm = interrupt
        result = self.core.develop(ident, True)
        self.assertEqual(result["status"], "WAITING")
        task_id = result["task_id"]
        self.core.tasks.confirm = original
        execute = self.core.packages.execute
        self.core.packages.execute = lambda *args: self.fail("Reconciliation must not rerun code")
        self.core.reconcile(task_id)
        self.core.packages.execute = execute
        self.core.tasks.resume(task_id)
        self.assertEqual(self.core.develop(ident, False)["status"], "SUCCEEDED")

    def test_runtime_generation_is_reused_after_development_checkpoint_loss(self):
        self.bind([plan(), candidate()])
        ident = self.core.development.submit(specification())
        verify = self.core.packages.verify
        self.core.packages.verify = lambda *args: (_ for _ in ()).throw(CoreError("busy", "temporary contention"))
        self.assertEqual(self.core.develop(ident, True)["error"], "busy")
        self.core.packages.verify = verify
        self.assertEqual(self.core.develop(ident, False)["status"], "SUCCEEDED")
        self.assertEqual(len(self.provider.prompts), 2)

    def test_no_candidate_import_or_path_escape(self):
        self.assertCode("candidate_import", validate_candidate, candidate("import os\ndef run(text): return text"))
        value = candidate(); value["files"][0]["path"] = "../main.py"
        self.assertCode("invalid_contract", validate_candidate, value)

    def test_real_process_death_before_and_after_release_commit(self):
        first = self.install()
        second = self.core.packages.stage(candidate("def run(text):\n    return ''.join(c.upper() for c in text)\n"), specification("next"))
        self.assertTrue(self.core.packages.verify(second)["passed"])
        for stage in ("prepared", "committed"):
            completed = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "tests/release_crash.py"), str(self.root), second, stage], capture_output=True, timeout=15)
            self.assertEqual(completed.returncode, 77, completed.stderr)
            result = self.core.packages.recover()
            self.assertEqual(self.core.packages.binding("plugin.upper.v1"), first if stage == "prepared" else second)
            self.assertEqual(result["aborted_preparations"], 1 if stage == "prepared" else 0)


if __name__ == "__main__": unittest.main()
