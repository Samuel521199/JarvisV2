import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import uuid

from control.paths import child, reject_links
from sdk.protocol import CoreError, canonical
from adapters.desktop.locations import folder_name, test_location

LOCK = threading.RLock()
BLOCKED = {'.git', '.env', '.ssh', '.aws', '.codex', '.jarvis', 'node_modules', '__pycache__', '.venv', 'user-data'}
TEXT = {'.txt', '.md', '.py', '.js', '.mjs', '.ts', '.tsx', '.jsx', '.html', '.css', '.json', '.toml', '.yaml', '.yml', '.rs', '.csv', '.xml', '.svg', '.sql', '.ini', '.cfg', '.log', '.jarvis-workspace'}


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.db = sqlite3.connect(child(self.root, 'state/workspace.sqlite3'), timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,path TEXT UNIQUE NOT NULL,name TEXT NOT NULL,description TEXT NOT NULL,section TEXT NOT NULL,pinned INTEGER NOT NULL,removed INTEGER NOT NULL,created REAL NOT NULL)')

    def close(self): self.db.close()
    def list(self): return [dict(r) for r in self.db.execute('SELECT * FROM projects ORDER BY pinned DESC,section,name')]

    def get(self, ident):
        row = self.db.execute('SELECT * FROM projects WHERE id=?', (ident,)).fetchone()
        if not row: raise CoreError('project_missing', 'Project not registered')
        return dict(row)

    def open(self, raw, create=False):
        if not isinstance(raw, str) or not raw.strip() or len(raw) > 2048: raise CoreError('unsafe_path', 'Expected an absolute local folder')
        path = Path(raw)
        if not path.is_absolute() or raw.startswith(('\\\\', '//')): raise CoreError('unsafe_path', 'Local absolute paths only')
        reject_links(path)
        path = path.resolve()
        if path == Path(path.anchor) or path.is_relative_to(self.root): raise CoreError('unsafe_path', 'Runtime data is not a workspace')
        if create: path.mkdir(exist_ok=True)  # Parent must already exist; no arbitrary ancestor creation.
        if not path.is_dir(): raise CoreError('project_missing', 'Folder does not exist')
        ident = 'project-' + uuid.uuid4().hex
        self.db.execute('INSERT OR IGNORE INTO projects VALUES(?,?,?,?,?,0,0,?)', (ident, str(path), path.name, '', '', time.time()))
        self.db.execute('UPDATE projects SET removed=0 WHERE path=?', (str(path),))
        return dict(self.db.execute('SELECT * FROM projects WHERE path=?', (str(path),)).fetchone())

    def update(self, ident, patch):
        self.get(ident)
        if not isinstance(patch, dict) or not patch or set(patch) - {'name', 'description', 'section', 'pinned', 'removed'}: raise CoreError('project_invalid', 'Unexpected project field')
        for key, value in patch.items():
            if key in {'pinned', 'removed'}:
                if type(value) is not bool: raise CoreError('project_invalid', 'Expected boolean')
            elif not isinstance(value, str) or len(value) > (2000 if key == 'description' else 100) or (key == 'name' and not value.strip()):
                raise CoreError('project_invalid', 'Invalid project text')
        self.db.execute('UPDATE projects SET ' + ','.join(k+'=?' for k in patch) + ' WHERE id=?', (*patch.values(), ident))
        return self.get(ident)

    def create_project(self, parent, name, test=False):
        name = folder_name(name)
        if type(test) is not bool: raise CoreError('project_invalid', 'Expected boolean')
        if test:
            if parent: raise CoreError('project_invalid', 'Test location is selected by desktop policy')
            base = test_location(); reject_links(base)
            base.mkdir(exist_ok=True)
        else:
            if not isinstance(parent,str) or not Path(parent).is_absolute() or parent.startswith(('\\\\','//')):
                raise CoreError('unsafe_path','Select an absolute local parent folder')
            base = Path(parent); reject_links(base)
        base = base.resolve()
        if not base.is_dir() or base.is_relative_to(self.root) or base.is_relative_to(Path(__file__).resolve().parents[2]):
            raise CoreError('unsafe_path','Choose a user project location outside Jarvis source and data')
        target = child(base,name)
        try: target.mkdir(exist_ok=False)  # Never adopt/overwrite an existing folder as a new project.
        except FileExistsError: raise CoreError('project_exists','Choose another name or open the existing project') from None
        return self.open(str(target))

    def path(self, ident, relative='', write=False):
        project = self.get(ident)
        if project['removed']: raise CoreError('project_removed', 'Restore the project first')
        base = Path(project['path']); reject_links(base)
        if not base.is_dir(): raise CoreError('project_missing', 'Folder is unavailable')
        if not isinstance(relative, str): raise CoreError('unsafe_path', 'Invalid relative path')
        parts = Path(relative.replace('\\', '/')).parts
        for part in parts:
            lower = part.lower()
            if lower in BLOCKED or lower.startswith('.env') or any(s in lower for s in ('credential', 'secret', 'token', 'private_key')):
                raise CoreError('file_restricted', 'Sensitive or generated paths are excluded')
        target = child(base, relative)
        if target.resolve().is_relative_to(self.root): raise CoreError('file_restricted', 'Runtime data is excluded')
        # A UI editor is not the self-upgrade/release mechanism.
        source_root = Path(__file__).resolve().parents[2]
        if write and target.resolve().is_relative_to(source_root): raise CoreError('self_write_requires_release', 'Own source changes require the release pipeline')
        return target

    def tree(self, ident, relative=''):
        base = self.path(ident); target = self.path(ident, relative)
        if not target.is_dir(): raise CoreError('not_directory', 'Expected a folder')
        entries = []; truncated = False
        with os.scandir(target) as iterator:
            for entry in iterator:
                if len(entries) >= 400: truncated = True; break
                try:
                    path = self.path(ident, str(Path(entry.path).relative_to(base)))
                    directory = path.is_dir()
                    entries.append({'name': path.name, 'path': path.relative_to(base).as_posix(), 'directory': directory,
                                    'editable': not directory and path.suffix.lower() in TEXT})
                except (CoreError, OSError): continue
        entries.sort(key=lambda x: (not x['directory'], x['name'].casefold()))
        return {'entries': entries, 'truncated': truncated, 'path': relative}

    def read(self, ident, relative):
        path = self.path(ident, relative)
        if not path.is_file() or path.suffix.lower() not in TEXT: raise CoreError('text_only', 'Only supported text files can be edited')
        with path.open('rb') as handle: raw = handle.read(262145)
        if len(raw) > 262144 or b'\x00' in raw: raise CoreError('file_too_large', 'Text file limit is 256 KiB')
        try: text = raw.decode('utf-8-sig')
        except UnicodeError: raise CoreError('text_encoding', 'UTF-8 required')
        return {'path': relative, 'text': text, 'revision': hashlib.sha256(raw).hexdigest()}

    def write(self, ident, relative, text, revision):
        if not isinstance(text, str) or len(text.encode()) > 262144 or '\x00' in text: raise CoreError('file_too_large', 'Text file limit exceeded')
        path = self.path(ident, relative, write=True)
        if path.suffix.lower() not in TEXT: raise CoreError('text_only', 'Only supported text files can be written')
        with LOCK:
            if path.exists():
                if self.read(ident, relative)['revision'] != revision: raise CoreError('conflict', 'File changed; reread before saving')
            elif revision is not None: raise CoreError('conflict', 'File was removed; explicit creation required')
            # Atomic replacement, flushed bytes. Same-user hostile races are not an OS sandbox.
            fd, name = tempfile.mkstemp(prefix='.jarvis-write-', dir=path.parent)
            try:
                with os.fdopen(fd, 'wb') as handle: handle.write(text.encode()); handle.flush(); os.fsync(handle.fileno())
                self.path(ident, relative, write=True)
                os.replace(name, path)
            finally:
                if os.path.exists(name): os.unlink(name)
        return self.read(ident, relative)

    def mkdir(self, ident, relative):
        self.path(ident, relative, write=True).mkdir(exist_ok=False)
        return {'ok': True}

    def export(self, ident):
        item = self.get(ident)
        return {'filename': item['name'] + '.jarvis-workspace', 'text': canonical({'schema_version': 1, 'folders': [{'path': item['path']}], 'name': item['name'], 'description': item['description']})}
