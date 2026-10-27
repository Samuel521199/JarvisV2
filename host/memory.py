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
    from modules.context_knowledge.joint import members
    if scopes:=members(scope):
        for value in scopes:scope_for(root,value)
        return scope
    if scope == 'personal': return scope
    if isinstance(scope,str) and scope.startswith('domain-'):
        from modules.context_knowledge.domains import Domains
        db,_=open_memory(root)
        try:domain=Domains(db).get(scope)
        finally:db.close()
        scope_for(root,domain['parent']);return domain['id']
    workspace = Workspace(root)
    try:
        project = workspace.get(scope)
        if project['removed']: raise CoreError('project_removed', 'Restore the project before using its memory')
        return project['id']
    finally: workspace.close()


def command(root, value):
    fields = {'list': {'scope'}, 'save': {'item', 'revision', 'candidate'}, 'forget': {'scope', 'key', 'revision'},
              'history':{'scope','kind','id'}, 'health':{'scope'}, 'context_recall':{'scope','provider','enabled','query','selectors'},
              'propose': {'turn_id'}, 'propose_goal':{'goal_id'}, 'dismiss': {'id', 'revision'}, 'preview': {'scope', 'provider', 'enabled'},
              'recall': {'scope','provider','enabled','query'}}
    if not isinstance(value, dict) or value.get('action') not in fields or set(value) != {'action'} | fields[value['action']]:
        raise CoreError('memory_invalid', 'Unexpected memory command')
    if value['action']=='recall':
        return retrieve(root,value['scope'],value['provider'],value['enabled'],value['query'])
    if value['action']=='context_recall':
        from modules.context_knowledge.conditions import context
        return retrieve(root,value['scope'],value['provider'],value['enabled'],value['query'],context(value['selectors']))
    db, memory = open_memory(root)
    try:
        with LOCK:
            action = value['action']
            if action=='health':
                from modules.context_knowledge.health import inspect
                from modules.context_knowledge.joint import writable
                scope_for(root,value['scope']);writable(value['scope'])
                return inspect(db,value['scope'])
            if action=='history':
                from modules.context_knowledge.history import versions
                scope_for(root,value['scope'])
                return versions(db,value['scope'],value['kind'],value['id'])
            if action in {'list', 'forget', 'preview'}: scope_for(root, value['scope'])
            if action in {'list','forget'}:
                from modules.context_knowledge.joint import writable
                writable(value['scope'])
            if action == 'list': return {'facts': memory.list(value['scope']), 'candidates': memory.candidates(value['scope']), 'epoch': memory.epoch(),
                                        'imported': [r['id'] for r in db.all('SELECT id FROM memory_origins WHERE scope=?',(value['scope'],))],
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
                    from host.memory_domains import chat_scope
                    context=decode(turn['memory_context']) if turn['memory_context'] else {}
                    text = decode(turn['request'])['text']; scope = scope_for(root,context.get('scope') or chat_scope(root,chat))
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
                imported=db.one('SELECT checksum,body FROM memory_origins WHERE id=? AND scope=?',(row['id'],row['scope']))
                if imported:
                    if digest(decode(imported['body']))!=imported['checksum']:raise CoreError('memory_source_changed','Imported origin damaged')
                    return memory.save(item,value['revision'],'import:'+row['id'],candidate)
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


def retrieve(root, scope, provider, enabled, query='', selectors=None):
    selectors={'channel':'chat'} if selectors is None else selectors
    scope_for(root,scope)
    from host.local_models import MANAGERS
    from control.paths import data_root
    manager=MANAGERS.get(str(data_root(root)))
    db, memory = open_memory(root)
    try:
        # Inference happens without the global memory write lock or an SQL write transaction.
        from host.knowledge_vectors import search
        with db.read_snapshot():
            view=memory.view(scope,provider,enabled,query,manager.rank_memory if manager else None,
                             lambda db,s,p,q:search(root,db,s,p,q),selectors=selectors)
        view.update(scope=scope,provider=provider,enabled=enabled,selectors=selectors)
        with LOCK,db.read_snapshot():
            if not memory.references_valid(scope,provider,enabled,view['facts'],selectors):
                view={**memory.view(scope,provider,enabled,query,selectors=selectors),'scope':scope,'provider':provider,'enabled':enabled,'selectors':selectors}
                view['retrieval']['semantic']='changed_during_retrieval'
            view['valid_refs']=memory.references(scope,provider,enabled,selectors)
            view['epoch']=memory.epoch()
        return view
    finally:db.close()


def dialogue_view(root, chat, route, enabled, query=''):
    from host.memory_domains import chat_scope
    view=retrieve(root,chat_scope(root,chat),route['id'],enabled,query)
    view['chat_id']=chat['id'];return view


def refresh_view(root, view, *, chats=None, memory_db=None):
    """Recheck selected evidence and history authorization immediately before assembly/send."""
    scope_for(root,view['scope'])
    owned_db = memory_db is None
    db, memory = open_memory(root) if owned_db else (memory_db, Memory(memory_db))
    try:
        if view.get('chat_id'):
            from host.memory_domains import chat_scope
            owned_chats = chats is None
            if owned_chats:chats=Dialogues(root)
            try:
                if chat_scope(root,chats.header(view['chat_id']),db=db)!=view['scope']:raise CoreError('memory_changed','Conversation domain changed')
            finally:
                if owned_chats:chats.close()
        with db.read_snapshot():
            if view.get('capture_candidate') and not db.one("SELECT 1 FROM memory_candidates WHERE id=? AND scope=? AND state='PENDING'",
                                                          (view['capture_candidate'],view['scope'])):
                raise CoreError('memory_changed','Candidate review state changed during this response')
            refs=view.get('dependencies',view['facts'])
            if not memory.references_valid(view['scope'],view['provider'],view['enabled'],refs,view.get('selectors')):
                raise CoreError('memory_changed','Referenced memory changed during this response')
            view['valid_refs']=memory.references(view['scope'],view['provider'],view['enabled'],view.get('selectors'))
            view['epoch']=memory.epoch()
    finally:
        if owned_db:db.close()


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
        from host.completion import projection
        closure=projection(core,task['id'])
        if closure['state'] in {'NEEDS_CORRECTION','INVALIDATED','CANCELLED','UNAVAILABLE'}:
            raise CoreError('memory_source_changed','Goal evidence or feedback no longer supports this candidate')
        actions=core.tasks.actions(task['id']);caps=[a['capability'] for a in actions if a['status']=='CONFIRMED' and a['capability'].startswith('plugin.')]
        if any(a['capability'].startswith('mcp.') for a in actions):
            raise CoreError('memory_source_changed','External connector results are not automatically admitted as reusable experience')
        if not caps:raise CoreError('memory_source_changed','No confirmed tool receipt')
        context=get(core,ident);scope=context['scope'] if context else 'personal'
        scope_for(root,scope)
        coverage=closure.get('requirement_coverage',{})
        qualification='已核对明确列出的受支持要求；仍不代表通用语义目标验证。' if coverage.get('complete') else '目标要求覆盖尚未证实，不能把执行成功作为业务结论正确的证明。'
        # Keep evidence limits ahead of the bounded goal text so truncation cannot remove them.
        text=('执行观察：'+qualification+'\n适用条件以工具当前契约为准；其他输入仍需核对。'
              +'\n已执行能力：'+', '.join(caps)+'\n目标：'+p['request']['goal'])[:4000]
        evidence={'version':'execution-observation-1.1','task_id':task['id'],'goal':p['request']['goal'],
                  'qualification':qualification,'actions':[(a['id'],a['result']) for a in actions]}
        if closure.get('feedback'):evidence['feedback_id']=closure['feedback']['id']
        return scope,text,digest(evidence)
    finally:core.close()


def completed_goal(root,task_id):
    db,_=open_memory(root)
    try:row=db.one('SELECT p.id FROM goal_plans p JOIN goal_growth g ON g.goal_id=p.id WHERE p.task_id=? AND g.status=?',(task_id,'REJOINED'))
    finally:db.close()
    if row:return command(root,{'action':'propose_goal','goal_id':row['id']})
