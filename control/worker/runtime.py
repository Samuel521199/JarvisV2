"""Stage a small independent CPython runtime from this trusted interpreter."""
import hashlib
import os
import re
from pathlib import Path
import shutil
import sys
import uuid
import zipfile

from control.paths import child, reject_links
from control.worker.launcher import launch, acl
from control.worker.win32 import bind
from sdk.protocol import CoreError, PROJECT, canonical, decode, read_json


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class RestrictedWorker:
    def __init__(self, root):
        self.root = root
        self.runtime = child(root, "worker-runtime")

    def prepare(self):
        if os.name != "nt" or sys.version_info[:2] != (3, 13):
            raise CoreError("worker_unavailable", "First worker recipe supports Windows CPython 3.13 only")
        manifest = child(self.root, "worker-runtime/manifest.json")
        if manifest.exists():
            return self.verify()
        if self.runtime.exists():
            raise CoreError("worker_incomplete", "Incomplete runtime staging; preserve it for inspection")
        self.runtime.mkdir()
        source = Path(sys.base_prefix)
        for name in ("python.exe", "python313.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"):
            # GUI entry avoids a console helper that conflicts with one-process jobs.
            origin = source / ("pythonw.exe" if name == "python.exe" else name)
            reject_links(origin)
            shutil.copyfile(origin, self.runtime / name)
        # Only standard-library source; no site packages, hooks, binaries from old Jarvis.
        excluded = {"site-packages", "__pycache__", "test", "tests", "idlelib", "tkinter", "ensurepip", "turtledemo"}
        with zipfile.ZipFile(self.runtime / "stdlib.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((source / "Lib").rglob("*.py")):
                rel = path.relative_to(source / "Lib")
                if not excluded.intersection(rel.parts):
                    reject_links(path); archive.write(path, rel.as_posix())
        dlls = self.runtime / "DLLs"; dlls.mkdir()
        for path in sorted((source / "DLLs").iterdir()):
            if path.suffix.lower() in {".pyd", ".dll"} and not any(x in path.name for x in ("_tkinter", "tcl", "tk86")):
                reject_links(path); shutil.copyfile(path, dlls / path.name)
        (self.runtime / "python313._pth").write_text("stdlib.zip\nDLLs\n.\n", encoding="utf-8")
        files = {p.relative_to(self.runtime).as_posix(): sha(p) for p in self.runtime.rglob("*") if p.is_file()}
        manifest.write_text(canonical({"schema": 1, "python": sys.version.split()[0], "files": files}), encoding="utf-8")
        return self.verify()

    def verify(self):
        manifest = child(self.root, "worker-runtime/manifest.json")
        if not manifest.exists():
            raise CoreError("worker_unavailable", "Run worker-prepare before enabling autonomous development")
        body = read_json(manifest)
        if body.get("schema") != 1 or body.get("python") != sys.version.split()[0]:
            raise CoreError("worker_runtime_changed", "Runtime recipe/version differs")
        expected = set(body["files"])
        actual = {p.relative_to(self.runtime).as_posix() for p in self.runtime.rglob("*") if p.is_file()} - {"manifest.json"}
        if expected != actual or any(sha(child(self.runtime, name)) != value for name, value in body["files"].items()):
            raise CoreError("worker_runtime_changed", "Staged runtime integrity differs")
        return {"ready": True, "files": len(actual), "bytes": sum((self.runtime / n).stat().st_size for n in actual)}

    def run(self, files, inputs, checkpoint=lambda: None, seconds=8):
        self.verify(); checkpoint()
        parent = child(self.root, "worker-runs"); parent.mkdir(exist_ok=True)
        stage = child(parent, uuid.uuid4().hex); stage.mkdir()
        leases = child(self.root, "state/worker-leases"); leases.mkdir(exist_ok=True)
        lease = child(leases, stage.name + ".json")
        try:
            for name, source in files.items():
                path = child(stage, name)
                if path.name in {"entry.py", "request.json"}:
                    raise CoreError("candidate_path", "Reserved worker path")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")
            child(stage, "request.json").write_text(canonical({"inputs": inputs}), encoding="utf-8")
            shutil.copyfile(PROJECT / "control/worker/entry.py", stage / "entry.py")
            result = launch(self.runtime, stage, checkpoint, seconds, lease_path=lease)
            if result["exit_code"]:
                raise CoreError("worker_execution", "Candidate failed in restricted Worker")
            body = decode(result["stdout"])
            if (not isinstance(body, dict) or set(body) != {"outputs"} or not isinstance(body["outputs"], list)
                    or len(body["outputs"]) != len(inputs) or any(not isinstance(v, str) or len(v) > 50000 for v in body["outputs"])):
                raise CoreError("worker_reply", "Invalid candidate output")
            return body["outputs"], result["evidence"]
        finally:
            # The generated directory was resolved under our worker-runs root.
            reject_links(stage)
            if stage.parent.resolve() != parent.resolve() or len(stage.name) != 32:
                raise CoreError("unsafe_path", "Worker cleanup target changed")
            shutil.rmtree(stage)

    def recover(self):
        """Caller holds RunLock: remove only journaled, owned orphan resources."""
        directory = child(self.root, "state/worker-leases")
        if not directory.exists(): return {"recovered": 0}
        native = bind()
        count = 0
        for path in directory.glob("*.json"):
            reject_links(path)
            value = read_json(path)
            if (set(value) != {"profile", "stage", "sid", "pid"} or not re.fullmatch(r"Jarvis2\.Run\.[0-9a-f]{32}", value["profile"])
                    or not re.fullmatch(r"[0-9a-f]{32}", value["stage"]) or path.stem != value["stage"]
                    or value["pid"] is not None and (type(value["pid"]) is not int or value["pid"] <= 0)
                    or value["sid"] is not None and not re.fullmatch(r"S-1-15-2(?:-[0-9]+){7}", value["sid"])):
                raise CoreError("worker_lease", "Invalid orphan lease; manual inspection required")
            parent = child(self.root, "worker-runs")
            stage = child(parent, value["stage"])
            if value["sid"]:
                for target in (self.runtime, stage):
                    if target.exists(): acl(native, target, value["sid"], True)
            result = native["DeleteAppContainerProfile"](value["profile"])
            if result < 0 and (result & 0xFFFF) not in {2, 3}:
                raise CoreError("worker_cleanup", "Orphan profile could not be removed")
            if stage.exists():
                if stage.parent.resolve() != parent.resolve(): raise CoreError("unsafe_path", "Cleanup escaped staging")
                shutil.rmtree(stage)
            path.unlink(); count += 1
        return {"recovered": count}
