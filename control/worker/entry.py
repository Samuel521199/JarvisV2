"""Trusted fixed entry, copied into a read-only, secret-free LPAC stage."""
import json
import importlib
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
run = importlib.import_module("main").run

request = json.loads((root / "request.json").read_text(encoding="utf-8"))
outputs = [run(value) for value in request["inputs"]]
sys.stdout.reconfigure(encoding="utf-8")
print(json.dumps({"outputs": outputs}, ensure_ascii=False, allow_nan=False))
