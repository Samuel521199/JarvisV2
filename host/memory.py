"""Compose memory, chat provenance and project boundaries without cross-domain imports."""
import threading
from adapters.storage.sqlite import Database
from control.paths import child
from modules.context_knowledge.memory import Memory
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences
from modules.workspace.store import Workspace
from sdk.protocol import CoreError, decode, digest

LOCK = threading.RLock()


def open_memory(root):
    db = Database(child(root, 'state/core.sqlite3'))
    return db, Memory(db)


def scope_for(root, scope):
    if scope == 'personal': return scope
    workspace = Workspace(root)
    try:
        project = workspace.get(scope)
        if project['removed']: raise CoreError('project_removed', 'Restore the project before using its memory')
        return project['id']
    finally: workspace.close()


def command(root, value):
    fields = {'list': {'scope'}, 'save': {'item', 'revision', 'candidate'}, 'forget': {'scope', 'key', 'revision'},
              'propose': {'turn_id'}, 'propose_goal':{'goal_id'}, 'dismiss': {'id', 'revision'}, 'preview': {'scope', 'provider', 'enabled'}}
    if not isinstance(value, dict) or value.get('action') not in fields or set(value) != {'action'} | fields[value['action']]:
        raise CoreError('memory_invalid', 'Unexpected memory command')
    db, memory = open_memory(root)
    try:
        with LOCK:
            action = value['action']
            if action in {'list', 'forget', 'preview'}: scope_for(root, value['scope'])
            if action == 'list': return {'facts': memory.list(value['scope']), 'candidates': memory.candidates(value['scope']), 'epoch': memory.epoch(),
                                        'withdrawn': db.all('SELECT key,revision FROM facts WHERE principal=? AND scope=? AND deleted=1', ('owner.local',value['scope']))}
            if action == 'forget': return memory.forget(value['scope'], value['key'], value['revision'])
            if action == 'dismiss': return memory.dismiss(value['id'], value['revision'])
            if action == 'preview': return memory.view(value['scope'], value['provider'], value['enabled'])
            if action == 'propose_goal':
                scope,text,revision=goal_source(root,value['goal_id'])
                return memory.propose('goal:'+value['goal_id'],revision,scope,text)
            if action == 'propose':
                chats = Dialogues(root)
                try:
                    turn = chats.turn(value['turn_id']); chat = chats.read(turn['chat_id'])
                    if chat['removed']: raise CoreError('chat_archived', 'Restore this chat first')
                    text = decode(turn['request'])['text']; scope = scope_for(root, chat['project_id'] or 'personal')
                    return memory.propose('turn:' + turn['id'], digest(text), scope, text)
                finally: chats.close()
            item = value['item']
            if not isinstance(item, dict): raise CoreError('memory_invalid', 'Expected memory fields')
            scope_for(root, item.get('scope'))
            prefs = Preferences(root)
            try: known = set((prefs.read() or {}).get('catalog', {}).get('providers', {})) | {'codex-cli'}
            finally: prefs.close()
            if not isinstance(item.get('providers'), list) or any(not isinstance(p, str) or p not in known for p in item['providers']):
                raise CoreError('memory_invalid', 'Select registered model destinations')
            candidate = value['candidate']; source = 'owner:explicit'
            if candidate is not None:
                if not isinstance(candidate, dict) or set(candidate) != {'id', 'revision'}: raise CoreError('memory_invalid', 'Invalid candidate reference')
                row = db.one('SELECT * FROM memory_candidates WHERE id=?', (candidate['id'],))
                if not row: raise CoreError('conflict', 'Candidate missing')
                if item['scope']!=row['scope']:raise CoreError('memory_invalid','Candidate cannot change source domain')
                if row['source_id'].startswith('goal:'):
                    scope,text,revision=goal_source(root,row['source_id'][5:])
                    if revision!=row['source_revision']:raise CoreError('memory_source_changed','Goal evidence changed')
                    return memory.save(item,value['revision'],row['source_id'],candidate)
                chats = Dialogues(root)
                try:
                    turn = chats.turn(row['source_id'].removeprefix('turn:'))
                    if chats.read(turn['chat_id'])['removed'] or digest(decode(turn['request'])['text']) != row['source_revision']:
                        raise CoreError('memory_source_changed', 'Original source unavailable or changed')
                finally: chats.close()
                source = row['source_id']
            return memory.save(item, value['revision'], source, candidate)
    finally: db.close()


def dialogue_view(root, chat, route, enabled):
    scope = scope_for(root, chat['project_id'] or 'personal')
    db, memory = open_memory(root)
    try: return {**memory.view(scope, route['id'], enabled), 'scope': scope, 'provider': route['id'], 'enabled': enabled}
    finally: db.close()


def current_epoch(root):
    db, memory = open_memory(root)
    try: return memory.epoch()
    finally: db.close()


def goal_source(root,ident):
    from host.core import Core
    from host.goal_context import get, check
    from modules.task_resource.plans import Plans
    core=Core(root)
    try:
        p=Plans(core.db).get(ident);check(core,ident)
        if not p['task_id'] or p['cancel']:raise CoreError('memory_source_changed','Goal has no successful delivery')
        task=core.tasks.get(p['task_id'])
        if task['status']!='SUCCEEDED':raise CoreError('memory_source_changed','Goal is not complete')
        actions=core.tasks.actions(task['id']);caps=[a['capability'] for a in actions if a['status']=='CONFIRMED' and a['capability'].startswith('plugin.')]
        if any(a['capability'].startswith('mcp.') for a in actions):
            raise CoreError('memory_source_changed','External connector results are not automatically admitted as reusable experience')
        if not caps:raise CoreError('memory_source_changed','No confirmed tool receipt')
        context=get(core,ident);scope=context['scope'] if context else 'personal'
        scope_for(root,scope)
        text=('已通过实际执行完成：'+p['request']['goal']+'\n可复用能力：'+', '.join(caps)+'\n适用条件以工具当前契约为准；其他输入仍需核对。')[:4000]
        return scope,text,digest({'task_id':task['id'],'goal':p['request']['goal'],'actions':[(a['id'],a['result']) for a in actions]})
    finally:core.close()


def completed_goal(root,task_id):
    db,_=open_memory(root)
    try:row=db.one('SELECT p.id FROM goal_plans p JOIN goal_growth g ON g.goal_id=p.id WHERE p.task_id=? AND g.status=?',(task_id,'REJOINED'))
    finally:db.close()
    if row:return command(root,{'action':'propose_goal','goal_id':row['id']})
