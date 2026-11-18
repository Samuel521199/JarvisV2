"""Local presentation archive for records with confirmed validation provenance."""
import json
import sqlite3

from control.paths import child
from sdk.protocol import CoreError


def _index(root):
    try:
        path = child(root, 'state/validation-archive.json')
        with path.open('rb') as stream:
            data = json.loads(stream.read(512 * 1024))
        if data.get('schema') == 1 and isinstance(data.get('chats'), dict) and isinstance(data.get('work'), dict):
            return data
    except (ValueError, OSError, AttributeError, CoreError):
        pass
    return {'chats': {}, 'work': {}}


def _matches(chat, index):
    return index.get(chat['id']) == [chat['updated'], chat['project_id']]


def annotate_chats(root, rows, db):
    index = _index(root)['chats']
    seen = {chat['id'] for chat in rows}
    missing = list(index.keys() - seen)
    for start in range(0, len(missing), 200):
        ids = missing[start:start + 200]
        matches = db.execute('SELECT * FROM chats WHERE id IN (' + ','.join('?' for _ in ids) + ')', ids)
        rows.extend(dict(chat) for chat in matches if _matches(chat, index))
    for chat in rows:
        if _matches(chat, index):
            chat['validation_archive'] = True
    return rows


def annotate_projects(root, rows):
    index = _index(root)
    projects = index.get('projects')
    if not isinstance(projects, dict):
        return rows
    candidates = [project for project in rows
                  if projects.get(project['id']) == [project['path'], project['name']]]
    if not candidates:
        return rows
    db = None
    try:
        path = child(root, 'state/dialogue.sqlite3')
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        for project in candidates:
            chats = db.execute('SELECT id,updated,project_id FROM chats WHERE project_id=? AND removed=0',
                               (project['id'],))
            if all(_matches(chat, index['chats']) for chat in chats):
                project['validation_archive'] = True
    except (sqlite3.Error, OSError, CoreError):
        pass
    finally:
        if db: db.close()
    return rows

def annotate_work(root, items):
    index = _index(root)
    ids = {item.get('chat_id') or item.get('context', {}).get('chat_id') for item in items}
    ids.intersection_update(index['chats'])
    archived = set()
    if ids:
        db = None
        try:
            path = child(root, 'state/dialogue.sqlite3')
            db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
            db.row_factory = sqlite3.Row
            placeholders = ','.join('?' for _ in ids)
            rows = db.execute('SELECT id,updated,project_id FROM chats WHERE id IN (' + placeholders + ')', tuple(ids))
            archived = {row['id'] for row in rows if _matches(row, index['chats'])}
        except (sqlite3.Error, OSError, CoreError):
            archived.clear()
        finally:
            if db: db.close()
    for item in items:
        if item['state'] in {'running', 'queued', 'external', 'unknown'}:
            continue
        receipt = item['attention']
        chat = item.get('chat_id') or item.get('context', {}).get('chat_id')
        # Only the chat's own replies inherit its archive status. Other
        # business records need their own exact evidence and result version.
        if (item['source'] == 'dialogue' and chat in archived
                or index['work'].get(receipt['key']) == receipt['version']):
            item['validation_archive'] = True
