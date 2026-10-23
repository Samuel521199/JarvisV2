"""Published pure tools: an owner request creates a narrowly scoped durable task.

No separate skill registry, scheduler or executor. Packages own admission and
lifecycle; Ledger owns effects; the existing task lane owns background work.
"""
import re
import time

from host.core import Core
from control.recovery.gate import RunLock
from sdk.protocol import CoreError, decode, digest


def catalog(root):
    core = Core(root)
    try:
        items = core.packages.catalog('owner.local', 'personal')
        recent = core.db.all("SELECT id,status,error,body,bindings,created FROM tasks WHERE request_id LIKE 'tool-use.%' ORDER BY created DESC LIMIT 40")
        for row in recent:
            body = decode(row.pop('body')); bindings = decode(row.pop('bindings'))
            cap = body['steps'][0]['capability']
            row.update(capability=cap, package_id=bindings[cap], goal=body['goal'])
        return {'items': items, 'recent': recent, 'scope': 'personal'}
    finally: core.close()


def owned_task(core, ident):
    if not isinstance(ident, str) or not re.fullmatch(r'task-[0-9a-f]{32}', ident):
        raise CoreError('tool_invalid', 'Invalid tool task')
    row = core.tasks.get(ident)
    if (not row['request_id'].startswith('tool-use.') or row['body']['principal_id'] != 'owner.local'
            or row['body']['scope_id'] != 'personal'):
        raise CoreError('denied', 'Not a workbench pure-tool request')
    return row


def command(root, value):
    fields = {'submit': {'request_id', 'capability', 'package_id', 'revision', 'text'},
              'detail': {'id'}, 'cancel': {'id'}, 'reconcile': {'id'}}
    if (not isinstance(value, dict) or not isinstance(value.get('action'), str)
            or value['action'] not in fields or set(value) != {'action'} | fields[value['action']]):
        raise CoreError('tool_invalid', 'Invalid pure-tool request')
    core = Core(root)
    try:
        if value['action'] == 'submit':
            if (not isinstance(value['request_id'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,70}', value['request_id'])
                    or not isinstance(value['capability'], str) or not re.fullmatch(r'plugin\.[a-z][a-z0-9-]{0,40}\.v1', value['capability'])
                    or not isinstance(value['package_id'], str) or not re.fullmatch(r'pkg-[0-9a-f]{64}', value['package_id'])
                    or type(value['revision']) is not int or value['revision'] < 1
                    or not isinstance(value['text'], str) or len(value['text']) > 50000 or len(value['text'].encode('utf-8')) > 100000):
                raise CoreError('tool_invalid', 'Choose a published tool and bounded text')
            request_id = 'tool-use.' + value['request_id']
            grant_id = 'tool-use-' + digest(value)[:32]
            with RunLock(core.root):
                # Lost HTTP responses can be recovered even after a release or grant changes.
                old = core.db.one('SELECT id,body FROM tasks WHERE request_id=?', (request_id,))
                if old:
                    if decode(old['body'])['grant_id'] != grant_id: raise CoreError('conflict', 'Request ID already has different input')
                    return {'id': old['id'], 'existing': True}
                core.gate.require_running()
                slot = core.packages.slot(value['capability'])
                if not slot or slot['revision'] != value['revision'] or slot['active'] != value['package_id']:
                    raise CoreError('conflict', 'Refresh the tool version before creating a task')
                core.packages.require(value['capability'], value['package_id'])
                core.packages.require_context(value['package_id'], {'principal_id': 'owner.local', 'scope_id': 'personal'})
                core.grants.add({'schema': 'jarvis.grant.v1', 'grant_id': grant_id,
                                 'principal_id': 'owner.local', 'scope_id': 'personal',
                                 'capabilities': [value['capability'], 'artifact.write.v1'],
                                 'max_cost_units': 2, 'expires_at': time.time() + 600})
                body = {'schema': 'jarvis.task.v1', 'request_id': request_id,
                        'principal_id': 'owner.local', 'scope_id': 'personal', 'grant_id': grant_id,
                        'goal': '使用本地工具 · ' + value['capability'],
                        'steps': [{'step_id': 'use', 'capability': value['capability'], 'arguments': {'text': value['text']}},
                                  {'step_id': 'deliver', 'capability': 'artifact.write.v1', 'arguments': {'name': 'result.json'}, 'input_from': 'use'}],
                        'limits': {'max_steps': 2, 'max_attempts': 1, 'max_seconds': 600, 'max_cost_units': 2}}
                try: ident = core.tasks.submit(body)
                except BaseException:
                    core.grants.revoke(grant_id)
                    raise
                return {'id': ident, 'existing': False}
        task = owned_task(core, value['id'])
        if value['action'] == 'cancel':
            # Revocation precedes cancellation so an in-flight worker also stops.
            if task['status'] not in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:
                core.grants.revoke(task['body']['grant_id'])
                core.tasks.cancel(task['id'])
            return {'task': core.tasks.get(task['id'])}
        if value['action'] == 'reconcile': return core.reconcile(task['id'])
        actions = core.tasks.actions(task['id'])
        for a in actions:
            a['arguments'] = decode(a['arguments'])
            a['result'] = decode(a['result']) if a['result'] else None
        grant = core.db.one('SELECT revoked,spent,body FROM grants WHERE id=?', (task['body']['grant_id'],))
        if grant: grant['body'] = decode(grant['body'])
        return {'task': task, 'actions': actions, 'grant': grant}
    finally: core.close()
