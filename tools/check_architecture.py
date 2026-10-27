"""Static dependency guard for the independently written core (not a sandbox)."""
import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

LAYERS = {"sdk", "control", "adapters", "modules", "host", "apps"}


def host_cycles(root):
    """Strongly connected host modules, counting imports inside functions too."""
    graph = {}
    for path in (root / 'host').glob('*.py'):
        deps = set()
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'), filename=str(path))):
            if isinstance(node, ast.ImportFrom) and node.module == 'host':
                deps |= {'host.' + alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('host.'):
                deps.add(node.module)
            elif isinstance(node, ast.Import):
                deps |= {alias.name for alias in node.names if alias.name.startswith('host.')}
        graph['host.' + path.stem] = deps - {'host.' + path.stem}
    index, low, stack, on_stack, found, counter = {}, {}, [], set(), [], [0]
    def visit(node):  # Tarjan; host has ~60 modules, recursion depth is small
        index[node] = low[node] = counter[0]; counter[0] += 1; stack.append(node); on_stack.add(node)
        for other in graph[node]:
            if other not in graph: continue
            if other not in index: visit(other); low[node] = min(low[node], low[other])
            elif other in on_stack: low[node] = min(low[node], index[other])
        if low[node] == index[node]:
            component = []
            while True:
                item = stack.pop(); on_stack.discard(item); component.append(item)
                if item == node: break
            if len(component) > 1: found.append(sorted(component))
    for node in sorted(graph):
        if node not in index: visit(node)
    return found


def optional_import(tree, target):
    """True when ``target`` sits in a try block that handles ImportError."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(target is child for stmt in node.body for child in ast.walk(stmt)):
            for handler in node.handlers:
                names = [handler.type] if not isinstance(handler.type, ast.Tuple) else list(handler.type.elts)
                if any(isinstance(n, ast.Name) and n.id in {'ImportError', 'ModuleNotFoundError'} for n in names):
                    return True
    return False


def check():
    errors = []
    count = 0
    # Optional inference libraries are confined to the declared subprocess worker.
    # This explicit exception does not permit imports into the Host or core.
    runtime = json.loads((ROOT / 'modules/local_models/runtime.json').read_text(encoding='utf-8'))
    worker = 'adapters/models/local_embedding_worker.py'
    allowed = {item['import'] for item in runtime['dependencies']}
    if runtime['worker'] != worker or allowed != {'numpy', 'onnxruntime', 'tokenizers'}:
        errors.append('Invalid optional local-runtime dependency declaration')
        allowed = set()
    engineering = json.loads((ROOT/'modules/skills/anatomy/runtime-boundary.json').read_text(encoding='utf-8'))
    engineering_worker = 'adapters/engineering/worker.py'
    engineering_allowed = {item['import'] for item in engineering['dependencies']}
    if engineering['worker'] != engineering_worker or engineering['bootstrap'] != 'apps/engineering/worker.py' or engineering_allowed != {'OCP','cantera'}:
        errors.append('Invalid optional engineering-runtime dependency declaration')
        engineering_allowed = set()
    studio=json.loads((ROOT/'modules/skills/studio3d/runtime.json').read_text(encoding='utf-8'))
    studio_worker='adapters/studio3d/worker.py'
    studio_allowed={x['import'] for x in studio['dependencies']}
    studio_support={'adapters/studio3d/asset_pipeline.py','adapters/studio3d/projection.py'}
    # These original helpers use only stdlib and receive validated Blender
    # objects; registering them does not grant new bpy/mathutils import sites.
    studio_helpers={'adapters/studio3d/organic.py','adapters/studio3d/framing.py'}
    if studio['worker']!=studio_worker or studio['bootstrap']!='apps/studio3d/worker.py' or set(studio.get('support_workers',[]))!=studio_support|studio_helpers or studio_allowed!={'bpy','mathutils'}:
        errors.append('Invalid optional Blender-runtime declaration');studio_allowed=set()
    learning=studio.get('learning',{})
    learning_worker='adapters/studio3d/learning_worker.py'
    learning_allowed=set(learning.get('dependencies',[]))
    if learning.get('worker')!=learning_worker or learning.get('bootstrap')!='apps/studio3d/learning_worker.py' or learning_allowed!={'bpy','mathutils','bmesh'}:
        errors.append('Invalid fixed Blender learning-runtime declaration');learning_allowed=set()
    # The vector index may use numpy when present: the optional local-embedding
    # runtime pins it in the same interpreter. The import must stay inside a
    # try/except ImportError fallback so a stdlib-only install keeps working.
    accelerated = {'modules/context_knowledge/vectors.py': {'numpy'} & allowed}
    for layer in sorted(LAYERS):
        for path in (ROOT / layer).rglob("*.py"):
            count += 1
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = [n.name for n in node.names] if isinstance(node, ast.Import) else ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                for name in names:
                    top = name.split(".")[0]
                    relative = path.relative_to(ROOT).as_posix()
                    if top not in sys.stdlib_module_names and top not in LAYERS and not (relative == worker and top in allowed) and not (relative == engineering_worker and top in engineering_allowed) and not (relative in {studio_worker,*studio_support} and top in studio_allowed) and not (relative == learning_worker and top in learning_allowed) and not (top in accelerated.get(relative, set()) and optional_import(tree, node)):
                        errors.append(f"Unapproved dependency: {path.relative_to(ROOT)} -> {name}")
                    if layer == "sdk" and top in LAYERS - {"sdk"}:
                        errors.append(f"SDK depends on implementation: {name}")
                    if layer == "control" and top in {"host", "modules", "adapters", "apps"}:
                        errors.append(f"Control depends on business runtime: {name}")
                    if layer in {"modules", "adapters", "host"} and top == "apps" or layer in {"modules", "adapters"} and top == "host":
                        errors.append(f"Runtime dependency cycle: {name}")
                    if layer == "modules" and top == "modules":
                        own = path.relative_to(ROOT).parts[1]
                        if len(name.split(".")) > 1 and name.split(".")[1] != own:
                            errors.append(f"Cross-domain implementation import: {name}")
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.match(r"^[A-Za-z]:[/\\]", node.value):
                    errors.append(f"Hardcoded machine runtime path: {path.relative_to(ROOT)}")
    # Ratchet: known host import cycles may shrink, never grow or multiply.
    baseline_path = ROOT / 'tools/architecture-baseline.json'
    known = [set(c) for c in json.loads(baseline_path.read_text(encoding='utf-8'))['host_import_cycles']] if baseline_path.exists() else []
    cycles = host_cycles(ROOT) if (ROOT / 'host').is_dir() else []
    for cycle in cycles:
        if not any(set(cycle) <= allowed for allowed in known):
            errors.append('New or grown host import cycle: ' + ', '.join(cycle))
    print(json.dumps({"python_files": count, "host_cycle_modules": sum(len(c) for c in cycles), "errors": errors}, ensure_ascii=False))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(check())
