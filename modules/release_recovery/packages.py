from __future__ import annotations

import ast
import os
import re
import time
import uuid

from control.paths import child
from sdk.protocol import CoreError, canonical, contract, decode, digest, read_json

SAFE_IMPORTS = {"json", "re", "math", "statistics", "decimal", "datetime", "collections", "itertools", "functools", "string", "csv", "io"}
# Harmless dead-end module reachable as io.abc / collections.abc.
_HARMLESS_MODULES = {"abc"}
BLOCKED_NAMES = {"eval", "exec", "compile", "open", "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
                 "input", "breakpoint", "help", "exit", "quit", "license", "credits", "copyright"}
# string.Formatter resolves "{0.attr}" lookups from a runtime string and hands the
# resulting object to overridable hooks (get_field, get_value, format_field,
# convert_field), so the class itself is outside the recipe; str.format stays allowed.
BLOCKED_ATTRIBUTES = {"open", "FileIO", "open_code", "Formatter", "get_field", "get_value", "format_field", "convert_field"}
# namedtuple's public API uses a leading underscore; these return plain tuples/dicts.
ALLOWED_PRIVATE = {"_asdict", "_replace", "_fields", "_make", "_field_defaults"}


def _module_escape_names():
    """Attribute names through which an allowed module exposes a module outside the recipe.

    Computed from the running interpreter so new stdlib aliases are caught too,
    e.g. statistics.sys, json.codecs.builtins, enum.bltns, csv.types.
    """
    import importlib
    import types
    allowed = SAFE_IMPORTS | _HARMLESS_MODULES
    names, seen, stack = set(), set(), [importlib.import_module(n) for n in sorted(SAFE_IMPORTS)]
    while stack:
        module = stack.pop()
        if module.__name__ in seen:
            continue
        seen.add(module.__name__)
        for attribute in dir(module):
            if attribute.startswith("_"):
                continue
            try:
                value = getattr(module, attribute)
            except Exception:
                continue
            if isinstance(value, types.ModuleType):
                if value.__name__.split(".")[0] in allowed:
                    stack.append(value)
                else:
                    names.add(attribute)
    return frozenset(names)


MODULE_ESCAPES = _module_escape_names()


def validate_candidate(candidate):
    contract("code-candidate", candidate)
    files = {}
    for entry in candidate["files"]:
        path = entry["path"]
        if path in files or path in {"entry.py", "site.py", "sitecustomize.py", "usercustomize.py"}:
            raise CoreError("candidate_path", "Duplicate or reserved candidate filename")
        files[path] = entry["content"]
    if "main.py" not in files or sum(len(x.encode()) for x in files.values()) > 60000:
        raise CoreError("candidate_contract", "main.py and a bounded source bundle are required")
    local = {path[:-3] for path in files}
    if local & SAFE_IMPORTS:
        raise CoreError("candidate_path", "Candidate must not shadow allowed standard-library modules")
    for name, source in files.items():
        try:
            tree = ast.parse(source, filename=name)
        except (SyntaxError, ValueError, RecursionError):
            raise CoreError("candidate_syntax", "Candidate Python syntax is invalid") from None
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                if getattr(node, "level", 0) or any(x.split(".")[0] not in SAFE_IMPORTS | local for x in imports):
                    raise CoreError("candidate_import", "Import is outside the pure-tool recipe")
                if isinstance(node, ast.ImportFrom) and any(x.name == "*" or x.name.startswith("_") or x.name in MODULE_ESCAPES | BLOCKED_NAMES | BLOCKED_ATTRIBUTES for x in node.names):
                    raise CoreError("candidate_import", "Imported name is outside the pure-tool recipe")
            if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in BLOCKED_NAMES):
                raise CoreError("candidate_construct", "Dynamic host access is outside this recipe")
            if isinstance(node, ast.Attribute) and ((node.attr.startswith("_") and node.attr not in ALLOWED_PRIVATE) or node.attr in BLOCKED_ATTRIBUTES | MODULE_ESCAPES):
                raise CoreError("candidate_construct", "Private, module or file access is outside this recipe")
        if name == "main.py" and not any(isinstance(x, ast.FunctionDef) and x.name == "run" for x in tree.body):
            raise CoreError("candidate_contract", "main.py must define run(text) returning text")
    return files


class Packages:
    def __init__(self, db, root, worker, gate, fault=lambda stage: None):
        self.db, self.root, self.worker, self.gate, self.fault = db, root, worker, gate, fault

    def get(self, ident):
        if not re.fullmatch(r"pkg-[0-9a-f]{64}", ident):
            raise CoreError("package_ref", "Invalid immutable package reference")
        row = self.db.one("SELECT * FROM packages WHERE id=?", (ident,))
        if not row: raise CoreError("package_missing", "Package not registered")
        bundle = read_json(child(self.root, "packages/" + ident + ".json"))
        if "pkg-" + digest(bundle) != ident:
            raise CoreError("package_changed", "Immutable package digest differs")
        row["bundle"], row["spec"] = bundle, decode(row["spec"])
        if row["capability"] != bundle["capability"] or digest(row["spec"]) != bundle["acceptance_digest"]:
            raise CoreError("package_changed", "Package and acceptance binding differ")
        return row

    def stage(self, candidate, spec):
        files = validate_candidate(candidate)
        bundle = {"schema": "jarvis.pure-package.v1", "capability": spec["capability"],
                  "recipe": "python313-pure-text.v1", "state_schema": 0,
                  "acceptance_digest": digest(spec), "files": files}
        ident = "pkg-" + digest(bundle)
        directory = child(self.root, "packages"); directory.mkdir(exist_ok=True)
        path = child(directory, ident + ".json")
        if not path.exists():
            with path.open("x", encoding="utf-8") as stream:
                stream.write(canonical(bundle)); stream.flush(); os.fsync(stream.fileno())
        with self.db.transaction() as tx:
            tx.execute("INSERT OR IGNORE INTO packages(id,capability,status,spec,created) VALUES(?,?,'CANDIDATE',?,?)",
                       (ident, spec["capability"], canonical(spec), time.time()))
            self.db.event(tx, None, "package.staged", {"package_id": ident})
        self.get(ident)
        return ident

    def evaluate(self, ident, checkpoint=lambda: None):
        package = self.get(ident)
        spec = package["spec"]
        cases = spec["public_cases"] + spec["evaluation_cases"]
        # The evaluator owns expected values; they never enter candidate files.
        outputs, evidence = self.worker.run(package["bundle"]["files"], [case["input"] for case in cases], checkpoint)
        passed = outputs == [case["expected"] for case in cases]
        return {"passed": passed, "case_count": len(cases), "public_cases": len(spec["public_cases"]),
                "independent_cases": len(spec["evaluation_cases"]), "acceptance_digest": digest(spec),
                "package_id": ident, "worker": evidence}

    def verify(self, ident, checkpoint=lambda: None):
        try:
            report = self.evaluate(ident, checkpoint)
        except CoreError as exc:
            if exc.code in {"stopped", "cancelled", "denied", "deadline", "busy"}: raise
            report = {"passed": False, "error": exc.code, "package_id": ident}
        with self.db.transaction() as tx:
            tx.execute("UPDATE packages SET status=?,report=? WHERE id=? AND status IN ('CANDIDATE','VERIFIED','REJECTED')",
                       ("VERIFIED" if report["passed"] else "REJECTED", canonical(report), ident))
            self.db.event(tx, None, "package.evaluated", {"package_id": ident, "passed": report["passed"]})
        return report

    def slot(self, capability):
        return self.db.one("SELECT * FROM release_slots WHERE capability=?", (capability,))

    def catalog(self, principal, scope):
        """Project published slots without loading code or starting probe workers."""
        result = []
        for slot in self.db.all('SELECT * FROM release_slots WHERE active IS NOT NULL ORDER BY capability'):
            row = self.db.one('SELECT spec,status FROM packages WHERE id=?', (slot['active'],))
            if not row: continue
            spec = decode(row['spec'])
            if spec['principal_id'] != principal or spec['scope_id'] != scope: continue
            error = None
            try: self.get(slot['active'])
            except (CoreError, OSError) as exc: error = getattr(exc, 'code', 'package_unavailable')
            result.append({**slot, 'name': spec['goal'], 'description': spec['description'],
                           'status': row['status'], 'scope': scope, 'error': error,
                           'available': bool(slot['enabled'] and row['status'] in {'CANARY', 'STABLE'} and not error),
                           'sample_input': spec['sample_input'], 'recipe': 'python313-pure-text.v1'})
        return result

    def activate(self, ident, revision, checkpoint=lambda: None, rollback=False):
        self.gate.require_running(); checkpoint()
        package = self.get(ident)
        if package["status"] not in {"VERIFIED", "CANARY", "STABLE"}:
            raise CoreError("release_unverified", "Only independently verified packages may activate")
        cap = package["capability"]
        current = self.slot(cap)
        if current and current["active"]:
            previous_spec = decode(self.db.one("SELECT spec FROM packages WHERE id=?", (current["active"],))["spec"])
            if any(previous_spec[key] != package["spec"][key] for key in ("principal_id", "scope_id")):
                raise CoreError("denied", "Cannot replace a capability belonging to another domain")
        if (current["revision"] if current else 0) != revision:
            raise CoreError("conflict", "Release generation changed")
        if current and current["active"] == ident:
            if not current["enabled"]:
                if not self.evaluate(ident, checkpoint)["passed"]:
                    raise CoreError("release_probe", "Stopped package failed its restart probe")
                checkpoint()
                with self.db.transaction() as tx:
                    if tx.execute("UPDATE release_slots SET enabled=1,revision=revision+1 WHERE capability=? AND revision=?",
                                  (cap, revision)).rowcount != 1: raise CoreError("conflict", "Release generation changed")
            return self.slot(cap)
        # Persist preparation before probe. Crash recovery never guesses a commit.
        operation = "rel-" + uuid.uuid4().hex
        with self.db.transaction() as tx:
            tx.execute("INSERT INTO release_operations VALUES(?,?,?,?,?,'PREPARED',?)",
                       (operation, cap, ident, current["active"] if current else None, revision, "rollback" if rollback else "activate"))
        self.fault("prepared")
        report = self.evaluate(ident, checkpoint)
        if not report["passed"]:
            with self.db.transaction() as tx:
                tx.execute("UPDATE release_operations SET status='REJECTED' WHERE id=?", (operation,))
            raise CoreError("release_probe", "Pre-activation probe failed; active package unchanged")
        checkpoint(); self.gate.require_running()
        with self.db.transaction() as tx:
            tx.execute("INSERT OR IGNORE INTO release_slots(capability) VALUES(?)", (cap,))
            if tx.execute("UPDATE release_slots SET active=?,previous=active,enabled=1,observations=0,revision=revision+1 WHERE capability=? AND revision=?",
                          (ident, cap, revision)).rowcount != 1:
                raise CoreError("conflict", "Release generation changed before commit")
            tx.execute("UPDATE packages SET status=? WHERE id=?", ("STABLE" if rollback else "CANARY", ident))
            tx.execute("UPDATE release_operations SET status='COMMITTED' WHERE id=?", (operation,))
            self.db.event(tx, None, "release.committed", {"operation_id": operation, "package_id": ident, "rollback": rollback})
        self.fault("committed")
        return self.slot(cap)

    def recover(self):
        with self.db.transaction() as tx:
            count = tx.execute("UPDATE release_operations SET status='ABORTED' WHERE status='PREPARED'").rowcount
            self.db.event(tx, None, "release.recovered", {"aborted_preparations": count})
        repaired = []
        for slot in self.db.all("SELECT * FROM release_slots WHERE enabled=1 AND active IS NOT NULL"):
            try: self.get(slot["active"])
            except (CoreError, OSError):
                self.quarantine(slot["capability"], slot["active"], self.gate.require_running)
                repaired.append(slot["capability"])
        return {"aborted_preparations": count, "repaired_slots": repaired}

    def binding(self, capability):
        slot = self.slot(capability)
        if not slot or not slot["enabled"] or not slot["active"]:
            raise CoreError("module_disabled", "Pure-tool release is unavailable")
        package = self.get(slot["active"])
        if package["status"] not in {"CANARY", "STABLE"}:
            raise CoreError("release_unverified", "Active package is not released")
        return slot["active"]

    def require(self, capability, ident):
        self.binding(capability)
        package = self.get(ident)
        if package["capability"] != capability or package["status"] not in {"CANARY", "STABLE"}:
            raise CoreError("package_unavailable", "Pinned package has been retired or rejected")

    def require_context(self, ident, context):
        spec = self.get(ident)["spec"]
        if any(spec[key] != context[key] for key in ("principal_id", "scope_id")):
            raise CoreError("denied", "Package is scoped to its original principal and domain")

    def rollback(self, capability, revision, checkpoint=lambda: None):
        slot = self.slot(capability)
        if not slot or not slot["previous"]:
            raise CoreError("no_previous_release", "No previously released package exists")
        return self.activate(slot["previous"], revision, checkpoint, rollback=True)

    def quarantine(self, capability, ident, checkpoint=lambda: None):
        current = self.slot(capability)
        if not current or current["active"] != ident: return
        try:
            self.rollback(capability, current["revision"], checkpoint)
        except CoreError:
            with self.db.transaction() as tx:
                tx.execute("UPDATE release_slots SET enabled=0,revision=revision+1 WHERE capability=? AND active=?", (capability, ident))
        with self.db.transaction() as tx:
            tx.execute("UPDATE packages SET status='REJECTED' WHERE id=?", (ident,))
            self.db.event(tx, None, "release.quarantined", {"package_id": ident})

    def execute(self, capability, ident, text, checkpoint=lambda: None):
        self.require(capability, ident)
        package = self.get(ident)
        try:
            if package["status"] == "CANARY" and not self.evaluate(ident, checkpoint)["passed"]:
                raise CoreError("release_probe", "Canary regression check failed")
            outputs, evidence = self.worker.run(package["bundle"]["files"], [text], checkpoint)
        except CoreError as exc:
            if exc.code not in {"stopped", "cancelled", "denied", "deadline"}:
                self.quarantine(capability, ident, checkpoint)
            raise
        with self.db.transaction() as tx:
            tx.execute("UPDATE release_slots SET observations=observations+1 WHERE capability=? AND active=?", (capability, ident))
            count = tx.execute("SELECT observations FROM release_slots WHERE capability=? AND active=?", (capability, ident)).fetchone()
            if count and count[0] >= 2:
                tx.execute("UPDATE packages SET status='STABLE' WHERE id=? AND status='CANARY'", (ident,))
        return {"text": outputs[0], "package_id": ident, "worker": evidence}

    def retire(self, ident):
        self.get(ident)
        if self.db.one("SELECT 1 FROM release_slots WHERE active=? OR previous=?", (ident, ident)):
            raise CoreError("release_in_use", "Current or recovery package cannot retire")
        for row in self.db.all("SELECT bindings FROM tasks WHERE status NOT IN ('SUCCEEDED','FAILED','CANCELLED') OR EXISTS(SELECT 1 FROM actions WHERE actions.task_id=tasks.id AND status IN ('UNKNOWN','DISPATCHING'))"):
            if ident in decode(row["bindings"]).values():
                raise CoreError("release_in_use", "Unfinished task pins this package")
        with self.db.transaction() as tx:
            tx.execute("UPDATE packages SET status='RETIRED' WHERE id=?", (ident,))
        return {"retired": ident, "files_retained": True}
