"""Explicitly rebuild the reviewed native source inventory after source edits.

This build tool never runs automatically in the application or in a Worker.
Changing its inventory does not grant permission to execute a new operation.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sync(root=ROOT):
    root = Path(root)
    path = root / 'modules/skills/studio3d/worker-programs.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    sources = sorted({p for folder in ('sdk', 'adapters/studio3d', 'modules/skills/studio3d', 'apps/studio3d')
                      for p in (root / folder).glob('*.py')})
    manifest['sources'] = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    path.write_bytes((json.dumps(manifest, indent=2) + '\n').encode())
    print(json.dumps({'entries': len(manifest['entries']), 'sources': len(sources)}))


if __name__ == '__main__':
    sync()
