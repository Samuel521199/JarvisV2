"""Workbench MCP actions join the existing task ledger and single task lane."""
import re
import time

from control.recovery.gate import RunLock
from host.core import Core
from sdk.protocol import CoreError, canonical, decode, digest


def listing(root):
    core = Core(root)
    try:
        return {'connections': core.connectors.list(), 'catalog': core.connectors.catalog(),
                'recent': core.db.all("SELECT id,status,error,created FROM tasks WHERE request_id LIKE 'mcp-use.%' ORDER BY created DESC LIMIT 40")}
    finally: core.close()


def owned_task(core, ident):
    if not isinstance(ident, str) or not re.fullmatch(r'task-[0-9a-f]{32}', ident): raise CoreError('mcp_invalid', 'Invalid task ID')
    row = core.tasks.get(ident)
    if not row['request_id'].startswith('mcp-use.'): raise CoreError('denied', 'Not a connector task')
    return row


def command(root, value):
    fields = {'discover': {'id', 'revision'}, 'configure': {'id', 'revision', 'selected', 'enabled'},
              'submit': {'request_id', 'capability', 'implementation', 'revision', 'arguments'},
              'detail': {'id'}, 'cancel': {'id'}, 'reconcile': {'id'}}
    if not isinstance(value, dict) or not isinstance(value.get('action'), str) or value['action'] not in fields or set(value) != {'action'} | fields[value['action']]:
        raise CoreError('mcp_invalid', 'Invalid connector action')
    core = Core(root)
    try:
        action = value['action']
        if action in {'discover', 'configure'}:
            if not isinstance(value['id'], str) or not re.fullmatch(r'ext-[0-9a-f]{32}', value['id']) or type(value['revision']) is not int:
                raise CoreError('mcp_invalid', 'Invalid registration revision')
            if action == 'discover': return core.connectors.discover(value['id'], value['revision'])
            return core.connectors.configure(value['id'], value['revision'], value['selected'], value['enabled'])
        if action == 'submit':
            if (not isinstance(value['request_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,70}', value['request_id'])
                    or not isinstance(value['capability'], str) or not re.fullmatch(r'mcp\.[0-9a-f]{32}\.[0-9a-f]{12}', value['capability'])
                    or not isinstance(value['implementation'], str) or type(value['revision']) is not int):
                raise CoreError('mcp_invalid', 'Invalid connector call')
            request_id = 'mcp-use.' + value['request_id']; grant = 'mcp-use-' + digest(value)[:32]
            with RunLock(core.root):
                old = core.db.one('SELECT id,body FROM tasks WHERE request_id=?', (request_id,))
                if old:
                    if decode(old['body'])['grant_id'] != grant: raise CoreError('conflict', 'Request input changed')
                    return {'id': old['id'], 'existing': True}
                core.gate.require_running(); core.connectors.check()
                ref = core.connectors.reference(value['capability'], value['implementation'])
                if ref['revision'] != value['revision']: raise CoreError('conflict', 'Admission changed')
                args = {'text': canonical(value['arguments'])}; core.connectors.validate(ref['capability'], args)
                core.grants.add({'schema': 'jarvis.grant.v1', 'grant_id': grant, 'principal_id': 'owner.local', 'scope_id': 'personal',
                                 'capabilities': [ref['capability'], 'artifact.write.v1'], 'max_cost_units': 2, 'expires_at': time.time()+600})
                body = {'schema': 'jarvis.task.v1', 'request_id': request_id, 'principal_id': 'owner.local', 'scope_id': 'personal',
                        'grant_id': grant, 'goal': '调用连接器 · ' + ref['name'],
                        'steps': [{'step_id': 'use', 'capability': ref['capability'], 'arguments': args},
                                  {'step_id': 'deliver', 'capability': 'artifact.write.v1', 'arguments': {'name': 'result.json'}, 'input_from': 'use'}],
                        'limits': {'max_steps': 2, 'max_attempts': 1, 'max_seconds': 600, 'max_cost_units': 2}}
                try: ident = core.tasks.submit(body)
                except BaseException:
                    core.grants.revoke(grant); raise
                return {'id': ident, 'existing': False}
        task = owned_task(core, value['id'])
        if action == 'cancel':
            if task['status'] not in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:
                core.grants.revoke(task['body']['grant_id']); core.tasks.cancel(task['id'])
        if action == 'reconcile': return core.reconcile(task['id'])
        actions = core.tasks.actions(task['id'])
        for a in actions:
            a['result'] = decode(a['result']) if a['result'] else None
            a['arguments'] = decode(a['arguments'])
        return {'task': core.tasks.get(task['id']), 'actions': actions}
    finally: core.close()
