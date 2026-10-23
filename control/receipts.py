"""Host-owned receipts for restricted computations, separate from code releases."""
import re
from control.atomic import write_json
from control.paths import child
from sdk.protocol import CoreError, digest, read_json


def receipt_path(root, action_id):
    if not re.fullmatch(r"action-[0-9a-f]{32}", action_id):
        raise CoreError("invalid_action", "Invalid action receipt ID")
    return child(root, "state/receipts/" + action_id + ".json")


def binding(task_id, action_id, implementation, arguments):
    return {"task_id": task_id, "action_id": action_id, "implementation": implementation, "arguments_digest": digest(arguments)}


def read(root, expected):
    path = receipt_path(root, expected["action_id"])
    if not path.exists(): raise CoreError("unknown_effect", "No committed computation receipt")
    value = read_json(path)
    if set(value) != {"binding", "result", "result_digest"} or value["binding"] != expected or digest(value["result"]) != value["result_digest"]:
        raise CoreError("receipt_changed", "Computation receipt binding differs")
    return value["result"]


def commit(root, expected, result):
    path = receipt_path(root, expected["action_id"])
    if path.exists():
        existing = read(root, expected)
        if digest(existing) != digest(result): raise CoreError("receipt_changed", "Do not overwrite a committed computation")
        return existing
    path.parent.mkdir(exist_ok=True)
    write_json(path, {"binding": expected, "result": result, "result_digest": digest(result)})
    return result
