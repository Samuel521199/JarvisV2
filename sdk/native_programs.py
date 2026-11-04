"""Integrity inventory for fixed first-party native programs, not a sandbox."""
import hashlib
import json
from pathlib import Path


def verify_program(root, entry):
    root = Path(root).resolve()
    name = Path(entry).resolve().relative_to(root).as_posix()
    manifest = json.loads((root / 'modules/skills/studio3d/worker-programs.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 1 or name not in manifest['entries'] or not manifest['sources']:
        raise ValueError('Unregistered native program')
    for relative, expected in manifest['sources'].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Native program source changed: ' + relative)
    if name not in manifest['sources']:
        raise ValueError('Native entry is missing its integrity receipt')
    return name
