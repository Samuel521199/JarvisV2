"""Portable data/asset locations for standalone first-party authoring programs."""
import hashlib
import json
import os
from pathlib import Path
import sys

CODE_ROOT = Path(__file__).resolve().parents[1]


def option(name):
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    if name not in args:
        return None
    index = args.index(name)
    if index + 1 == len(args) or args[index + 1].startswith('--'):
        raise ValueError('Missing value for ' + name)
    return args[index + 1]


def data_root():
    value = option('--data-root') or os.environ.get('JARVIS_DATA_ROOT')
    return Path(value).expanduser().resolve() if value else CODE_ROOT / 'user-data'


def workspace_root():
    value = option('--workspace-root') or os.environ.get('JARVIS_WORKSPACE_ROOT')
    if value:
        return Path(value).expanduser().resolve()
    return data_root().parent if option('--data-root') or os.environ.get('JARVIS_DATA_ROOT') else CODE_ROOT


def project_path(relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Expected a project-relative asset location')
    return data_root().joinpath(*path.parts[1:]) if path.parts and path.parts[0] == 'user-data' else workspace_root() / path


def reference_path(relative):
    value = option('--reference')
    return Path(value).expanduser().resolve() if value else Path.home() / 'Desktop' / relative


def optional_character_tool():
    """Locate an existing, explicitly pinned optional tool; never install/update it."""
    manifest = json.loads((CODE_ROOT / 'modules/skills/studio3d/external-tools.json').read_text(encoding='utf-8'))
    value = option('--skill-tool') or os.environ.get('JARVIS_CHARACTER_TOOL')
    codex_dir = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))
    path = Path(value).expanduser().resolve() if value else codex_dir / manifest['character_authoring']['relative_path']
    expected = manifest['character_authoring']['sha256']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Optional character-authoring tool is missing or differs from its reviewed pin')
    return path
