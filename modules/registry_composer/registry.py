from __future__ import annotations

import hashlib

from control.paths import child
from sdk.protocol import CoreError, PROJECT, contract, decode
from modules.registry_composer.builtins import analyze, check_arguments, verify_artifact, write_artifact

CATALOG = {"text-analyzer": ("text.analyze.v1", {"text.basic.v1", "text.scan.v1"}),
           "artifact-writer": ("artifact.write.v1", {"artifact.local.v1"})}


class Registry:
    def __init__(self, db, project=PROJECT, plugins=None, connectors=None):
        self.db = db
        self.project = project
        self.plugins = plugins
        self.connectors = connectors

    def manifest(self, module_id):
        if module_id not in CATALOG:
            raise CoreError("unsupported_module", "Dynamic candidate loading is disabled")
        try:
            body = decode(child(self.project, f"modules/registry_composer/manifests/{module_id}.json").read_bytes())
        except OSError as exc:
            raise CoreError("package_unavailable", "Module manifest is unavailable") from exc
        contract("module", body)
        cap, providers = CATALOG[module_id]
        if (body["module_id"] != module_id or body["provides"] != [cap]
                or set(body["implementations"]) != providers or body["requires"]):
            raise CoreError("incompatible_module", "Manifest differs from compiled capability catalog")
        required = "modules/registry_composer/builtins.py"
        if [entry["path"] for entry in body["files"]] != [required]:
            raise CoreError("incompatible_module", "Unexpected package files")
        for entry in body["files"]:
            try:
                actual = hashlib.sha256(child(self.project, entry["path"]).read_bytes()).hexdigest()
            except OSError as exc:
                raise CoreError("package_unavailable", "Provider source is unavailable") from exc
            if actual != entry["sha256"]:
                raise CoreError("package_changed", "Provider source digest differs; no activation")
        return body

    def initialize(self):
        for module_id in CATALOG:
            body = self.manifest(module_id)
            with self.db.transaction() as tx:
                tx.execute("INSERT OR IGNORE INTO modules(id,active) VALUES(?,?)", (module_id, body["implementations"][0]))

    def binding(self, capability):
        if capability.startswith('mcp.') and self.connectors:
            return self.connectors.reference(capability)['active']
        if capability.startswith("plugin.") and self.plugins:
            return self.plugins.binding(capability)
        for module_id, (cap, _) in CATALOG.items():
            if cap == capability:
                self.manifest(module_id)
                row = self.db.one("SELECT * FROM modules WHERE id=?", (module_id,))
                if not row or not row["enabled"]:
                    raise CoreError("module_disabled", "Required module is disabled")
                return row["active"]
        raise CoreError("unsupported_capability", "Unknown capability")

    def require(self, capability, implementation):
        if capability.startswith('mcp.') and self.connectors:
            self.connectors.check()
            return self.connectors.reference(capability, implementation)
        if capability.startswith("plugin.") and self.plugins:
            return self.plugins.require(capability, implementation)
        self.binding(capability)  # Current enabled state and integrity always checked.
        if not any(capability == cap and implementation in impls for cap, impls in CATALOG.values()):
            raise CoreError("unsupported_provider", "Task binding is not a trusted provider")

    def validate_arguments(self, capability, arguments):
        if capability.startswith('mcp.') and self.connectors:
            return self.connectors.validate(capability, arguments)
        if capability.startswith("plugin.") and self.plugins:
            if set(arguments) != {"text"} or not isinstance(arguments["text"], str) or len(arguments["text"]) > 50000:
                raise CoreError("invalid_arguments", "Pure tools require bounded text only")
            return
        check_arguments(capability, arguments)

    def require_context(self, capability, implementation, context):
        if capability.startswith('mcp.'):
            if context.get('principal_id') != 'owner.local' or context.get('scope_id') != 'personal':
                raise CoreError('denied', 'Connector admission currently belongs to the personal scope')
        if capability.startswith("plugin.") and self.plugins:
            self.plugins.require_context(implementation, context)

    @staticmethod
    def safe_retry(capability):
        return capability == "text.analyze.v1"

    def execute(self, root, task_id, action_id, capability, arguments, implementation, checkpoint=lambda: None):
        self.require(capability, implementation)
        if capability.startswith('mcp.') and self.connectors:
            return self.connectors.execute(capability, implementation, arguments, checkpoint)
        if capability.startswith("plugin.") and self.plugins:
            return self.plugins.execute(capability, implementation, arguments["text"], checkpoint)
        if capability == "text.analyze.v1":
            return analyze(arguments["text"], implementation)
        if capability == "artifact.write.v1":
            return write_artifact(root, task_id, action_id, arguments)
        raise CoreError("unsupported_capability", "No executor")

    def reconcile(self, root, task_id, action_id, capability, arguments, implementation):
        if capability.startswith("plugin."):
            raise CoreError("unknown_effect", "Interrupted plugin result has no durable output receipt; explicit task decision required")
        if capability == "artifact.write.v1":
            return verify_artifact(root, task_id, action_id, arguments)
        if capability == "text.analyze.v1":
            self.require(capability, implementation)
            return analyze(arguments["text"], implementation)
        raise CoreError("unsupported", "No reliable reconciliation for this effect")

    def probe(self, module_id, implementation=None):
        body = self.manifest(module_id)
        row = self.db.one("SELECT * FROM modules WHERE id=?", (module_id,))
        impl = implementation or row["active"]
        if impl not in body["implementations"]:
            raise CoreError("unsupported_provider", "Provider is not admitted")
        if module_id == "text-analyzer":
            fixture = decode(child(self.project, "evals/text-analyzer.json").read_bytes())
            for case in fixture["cases"]:
                if analyze(case["input"], impl) != case["expected"]:
                    raise CoreError("evaluation_failed", "Independent text fixture failed")
        return {"module_id": module_id, "implementation": impl, "probe": "passed",
                "coverage": "manifest and text fixtures" if module_id == "text-analyzer" else "manifest integrity only",
                "isolation": "trusted-host-not-os-sandbox"}

    def describe(self):
        results = []
        for row in self.db.all("SELECT * FROM modules ORDER BY id"):
            try:
                health = self.probe(row["id"])
            except (CoreError, OSError) as exc:
                health = {"probe": "failed", "code": getattr(exc, "code", "io_error")}
            results.append({**row, "health": health})
        return results

    def change(self, module_id, operation, expected_revision, implementation=None):
        row = self.db.one("SELECT * FROM modules WHERE id=?", (module_id,))
        if not row or row["revision"] != expected_revision:
            raise CoreError("conflict", "Module revision changed")
        if operation in {"activate", "rollback"}:
            target = row["previous"] if operation == "rollback" else implementation
            self.probe(module_id, target)
            if target is None:
                raise CoreError("unsupported", "No previous version")
            active, previous, enabled = target, row["active"], 1
        elif operation in {"start", "stop"}:
            if operation == "start":
                self.probe(module_id)
            active, previous, enabled = row["active"], row["previous"], int(operation == "start")
        else:
            raise CoreError("unsupported", "Lifecycle method unsupported")
        with self.db.transaction() as tx:
            if tx.execute("UPDATE modules SET active=?,previous=?,enabled=?,revision=revision+1 WHERE id=? AND revision=?",
                          (active, previous, enabled, module_id, expected_revision)).rowcount != 1:
                raise CoreError("conflict", "Module revision changed")
            self.db.event(tx, None, "module." + operation, {"module_id": module_id, "implementation": active})
        return self.db.one("SELECT * FROM modules WHERE id=?", (module_id,))
