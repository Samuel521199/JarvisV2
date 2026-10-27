"""Strict JSON contracts for the deliberately small first runtime.

Only the JSON Schema vocabulary used by our schemas is supported. Unknown
schema keywords fail closed; this is not a general JSON Schema implementation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Protocol

MAX_MESSAGE_BYTES = 262_144
PROJECT = Path(__file__).resolve().parents[1]


class CoreError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class RetryableError(Exception):
    """Adapter reports a transient failure with no effect; gateway still checks capability."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CoreError("invalid_json", "Duplicate JSON key")
        result[key] = value
    return result


def decode(raw: bytes | str) -> Any:
    if isinstance(raw, str):
        try:
            raw = raw.encode("utf-8")
        except UnicodeError as exc:
            raise CoreError("invalid_json", "Invalid Unicode in JSON") from exc
    if len(raw) > MAX_MESSAGE_BYTES:
        raise CoreError("message_too_large", "JSON message exceeds limit")
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        canonical(result).encode("utf-8")  # Reject lone surrogate escapes as well.
        return result
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise CoreError("invalid_json", "Expected bounded UTF-8 JSON") from exc


def read_json(path: Path) -> Any:
    with path.open("rb") as stream:
        return decode(stream.read(MAX_MESSAGE_BYTES + 1))


def validate(schema: dict, value: Any, path: str = "$", depth: int = 0):
    if depth > 32:
        raise CoreError("invalid_contract", "Maximum nesting exceeded")
    allowed = {"$schema", "$id", "title", "description", "type", "properties", "required",
               "additionalProperties", "items", "minItems", "maxItems", "minLength", "maxLength",
               "pattern", "minimum", "maximum", "enum", "const"}
    if set(schema) - allowed:
        raise CoreError("unsupported_schema", "Unsupported schema keyword")
    types = {"object": dict, "array": list, "string": str, "integer": int,
             "number": (float, int), "boolean": bool, "null": type(None)}
    kind = schema.get("type")
    if kind not in types:
        raise CoreError("unsupported_schema", "Explicit schema type required")
    if not isinstance(value, types[kind]) or (kind in {"integer", "number"} and isinstance(value, bool)):
        raise CoreError("invalid_contract", f"{path}: expected {kind}")
    if "const" in schema and value != schema["const"]:
        raise CoreError("invalid_contract", f"{path}: unsupported constant/version")
    if "enum" in schema and value not in schema["enum"]:
        raise CoreError("invalid_contract", f"{path}: unsupported value")
    if kind == "object":
        props = schema.get("properties", {})
        if set(schema.get("required", [])) - set(value):
            raise CoreError("invalid_contract", f"{path}: required fields missing")
        if schema.get("additionalProperties") is not False:
            raise CoreError("unsupported_schema", "Objects must reject unknown fields")
        if set(value) - set(props):
            raise CoreError("invalid_contract", f"{path}: unknown fields")
        for key, item in value.items():
            validate(props[key], item, f"{path}.{key}", depth + 1)
    elif kind == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 1024):
            raise CoreError("invalid_contract", f"{path}: array length")
        for item in value:
            validate(schema["items"], item, path + "[]", depth + 1)
    elif kind == "string":
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", MAX_MESSAGE_BYTES):
            raise CoreError("invalid_contract", f"{path}: string length")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise CoreError("invalid_contract", f"{path}: invalid format")
    elif kind in {"integer", "number"}:
        if (isinstance(value, float) and not math.isfinite(value)) or not schema.get("minimum", -1e20) <= value <= schema.get("maximum", 1e20):
            raise CoreError("invalid_contract", f"{path}: number outside bounds")


def contract(name: str, value: Any) -> dict:
    if name not in {"task", "grant", "module", "step-proposal", "fact", "development", "code-candidate", "development-plan", "goal-plan", "capability-draft", "assistant-turn", "knowledge-source", "outcome-assessment"}:
        raise CoreError("unknown_contract", "Contract is not registered")
    validate(decode((PROJECT / "contracts" / "schemas" / f"{name}.v1.json").read_bytes()), value)
    # Enforce the transport bound for direct Python callers as well.
    decode(canonical(value))
    if name == "step-proposal":
        fields = {"capability", "arguments"} & set(value)
        if (value["kind"] == "tool" and fields != {"capability", "arguments"}) or (value["kind"] != "tool" and fields):
            raise CoreError("invalid_contract", "Proposal kind and effect fields disagree")
    return value


class ModelProvider(Protocol):
    """Proposals only. Providers cannot write tasks, grants or module state."""
    def propose(self, context: dict) -> dict: ...


class ToolProvider(Protocol):
    def execute(self, arguments: dict) -> dict: ...
