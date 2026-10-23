"""Workbench application commands compose independent domains, never execute model text."""
import os
from modules.workspace.store import Workspace
from modules.dialogue.store import Dialogues
from modules.skills.catalog import Skills
from sdk.protocol import CoreError, decode
from sdk.pricing import estimate
from adapters.desktop.folder_picker import pick_folder
from adapters.desktop.locations import reveal_folder, test_location
from host import session_workspace


def read(root, route):
    cls = {'/api/projects': Workspace, '/api/skills': Skills, '/api/usage': Dialogues}.get(route)
    if not cls: raise CoreError('not_found', 'Unknown read command')
    store = cls(root)
    try:
        if route == '/api/usage':
            rows=[]
            for x in store.usage():
                usage=decode(x['usage']) if x['usage'] else {}
                profile=decode(x.pop('billing_profile')) if x['billing_profile'] else None
                x.pop('billing_profile',None)
                rows.append({**x,'usage':usage,'billing':estimate(profile,usage,x['created']),'connection_label':(profile or {}).get('connection_label',x['provider']),'key_label':(profile or {}).get('key_label','')})
            return rows
        return store.list()
    finally: store.close()


def command(root, route, value):
    if not isinstance(value, dict): raise CoreError('invalid_request', 'Expected an object')
    fields = {
        '/api/chat/workspace': ({'id','action'}, {'config','revision'}),
        '/api/project/create': ({'parent','name'}, {'test'}),
        '/api/project/locations': (set(),set()),
        '/api/project/pick': (set(), set()),
        '/api/project/open': ({'path'}, {'create'}), '/api/project/update': ({'id', 'patch'}, set()),
        '/api/project/tree': ({'id'}, {'path'}), '/api/project/read': ({'id', 'path'}, set()),
        '/api/project/write': ({'id', 'path', 'text', 'revision'}, set()), '/api/project/mkdir': ({'id', 'path'}, set()),
        '/api/project/export': ({'id'}, set()), '/api/project/reveal': ({'id'}, set()),
        '/api/project/archive': ({'id', 'archived'}, set()), '/api/chat/update': ({'id', 'patch'}, set()),
        '/api/skill/enable': ({'id', 'enabled'}, set()),
    }
    if route not in fields: raise CoreError('not_found', 'Unknown command')
    required, optional = fields[route]
    if not required <= set(value) or set(value) - required - optional: raise CoreError('invalid_request', 'Unexpected fields')
    if route == '/api/project/pick': return pick_folder()
    if route == '/api/project/locations': return {'test_root':str(test_location()),'home':os.path.expanduser('~'),'platform':__import__('sys').platform}
    if route == '/api/chat/workspace': return session_workspace.command(root,value)
    if route == '/api/chat/update':
        store = Dialogues(root)
        try: return store.update(value['id'], value['patch'])
        finally: store.close()
    if route == '/api/skill/enable':
        store = Skills(root)
        try: return store.enable(value['id'], value['enabled'])
        finally: store.close()
    store = Workspace(root)
    try:
        ident = value.get('id'); path = value.get('path', '')
        if route.endswith('/create'): return store.create_project(value['parent'],value['name'],value.get('test',False))
        if route.endswith('/open'):
            if type(value.get('create', False)) is not bool: raise CoreError('invalid_request', 'Expected boolean')
            return store.open(path, value.get('create', False))
        if route.endswith('/update'): return store.update(ident, value['patch'])
        if route.endswith('/tree'): return store.tree(ident, path)
        if route.endswith('/read'): return store.read(ident, path)
        if route.endswith('/write'): return store.write(ident, path, value['text'], value['revision'])
        if route.endswith('/mkdir'): return store.mkdir(ident, path)
        if route.endswith('/export'): return store.export(ident)
        if route.endswith('/reveal'):
            target = store.path(ident)
            return reveal_folder(target)
        if route.endswith('/archive'):
            store.get(ident); chats = Dialogues(root)
            try: return chats.archive_project(ident, value['archived'])
            finally: chats.close()
    finally: store.close()
