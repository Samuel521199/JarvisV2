"""Static dependency guard for the independently written core (not a sandbox)."""
import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

LAYERS = {"sdk", "control", "adapters", "modules", "host", "apps"}


def check():
    errors = []
    count = 0
    for layer in sorted(LAYERS):
        for path in (ROOT / layer).rglob("*.py"):
            count += 1
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = [n.name for n in node.names] if isinstance(node, ast.Import) else ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                for name in names:
                    top = name.split(".")[0]
                    if top not in sys.stdlib_module_names and top not in LAYERS:
                        errors.append(f"Unapproved dependency: {path.relative_to(ROOT)} -> {name}")
                    if layer == "sdk" and top in LAYERS - {"sdk"}:
                        errors.append(f"SDK depends on implementation: {name}")
                    if layer == "control" and top in {"host", "modules", "adapters", "apps"}:
                        errors.append(f"Control depends on business runtime: {name}")
                    if layer in {"modules", "adapters"} and top in {"host", "apps"}:
                        errors.append(f"Runtime dependency cycle: {name}")
                    if layer == "modules" and top == "modules":
                        own = path.relative_to(ROOT).parts[1]
                        if len(name.split(".")) > 1 and name.split(".")[1] != own:
                            errors.append(f"Cross-domain implementation import: {name}")
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.match(r"^[A-Za-z]:[/\\]", node.value):
                    errors.append(f"Hardcoded machine runtime path: {path.relative_to(ROOT)}")
    print(json.dumps({"python_files": count, "errors": errors}, ensure_ascii=False))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(check())
