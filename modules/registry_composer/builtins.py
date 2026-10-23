from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from control.paths import child
from sdk.protocol import CoreError


def check_arguments(capability: str, args: dict):
    if capability == "text.analyze.v1":
        if set(args) != {"text"} or not isinstance(args["text"], str) or len(args["text"]) > 50000:
            raise CoreError("invalid_arguments", "Text analyzer requires bounded text")
    elif capability == "artifact.write.v1":
        if set(args) != {"name", "content"} or not all(isinstance(v, str) for v in args.values()):
            raise CoreError("invalid_arguments", "Artifact writer requires name and content")
        name = args["name"]
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", name) or name.endswith(".")
                or name.split(".")[0].upper() in reserved or len(args["content"]) > 60000):
            raise CoreError("invalid_arguments", "Unsafe filename or oversized content")
    else:
        raise CoreError("unsupported_capability", "Capability is not built in")


def analyze(text: str, implementation: str) -> dict:
    if implementation == "text.basic.v1":
        words = len(text.split())
    elif implementation == "text.scan.v1":
        words = 0
        in_word = False
        for char in text:
            if not char.isspace() and not in_word:
                words += 1
            in_word = not char.isspace()
    else:
        raise CoreError("unsupported_provider", "Unknown text provider")
    return {"characters": len(text), "lines": len(text.splitlines()), "words": words,
            "utf8_bytes": len(text.encode("utf-8"))}


def artifact_path(root: Path, task_id: str, action_id: str, args: dict):
    check_arguments("artifact.write.v1", args)
    return child(root, f"artifacts/{task_id}/{action_id}/{args['name']}")


def verify_artifact(root, task_id, action_id, args):
    path = artifact_path(root, task_id, action_id, args)
    expected = args["content"].encode("utf-8")
    if not path.exists() or path.stat().st_size != len(expected):
        raise CoreError("unknown_effect", "Artifact is missing or incomplete; do not blindly replay")
    actual = path.read_bytes()
    if actual != expected:
        raise CoreError("unknown_effect", "Artifact differs from the intended result")
    return {"relative_path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(actual).hexdigest(),
            "bytes": len(actual), "verified": True}


def write_artifact(root, task_id, action_id, args):
    path = artifact_path(root, task_id, action_id, args)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite existing user files. A partial write remains UNKNOWN.
    if not path.exists():
        with path.open("xb") as stream:
            stream.write(args["content"].encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
    return verify_artifact(root, task_id, action_id, args)
