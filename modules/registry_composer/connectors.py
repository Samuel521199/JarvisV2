"""Revision-bound MCP admission and execution behind the existing Registry.

Registration, discovery and enablement are distinct. Discovery never invokes
a tool; annotations and server instructions never become permissions.
"""
import re

from adapters.mcp.http import Session
from control.network import NetworkGate
from control.recovery.gate import StopGate
from modules.registry_composer.extensions import Extensions
from sdk.mcp_schema import arguments, normalize
from sdk.protocol import CoreError, canonical, decode, digest


def capability(ident, name): return 'mcp.' + ident[4:] + '.' + digest(name)[:12]


def describe(raw):
    if (not isinstance(raw, dict) or not isinstance(raw.get('name'), str)
            or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', raw['name'])
            or not isinstance(raw.get('description', ''), str)):
        raise CoreError('mcp_protocol', 'Invalid tool description')
    schema = raw.get('inputSchema'); supported = True
    try:
        normalize(schema)
        if schema['type'] != 'object': supported = False
    except (CoreError, TypeError, ValueError): supported = False
    return {'name': raw['name'], 'description': raw.get('description', '')[:2000], 'input_schema': schema,
            'annotations': raw.get('annotations', {}), 'digest': digest(raw), 'supported': supported}


class Connectors:
    def __init__(self, root): self.root = root

    def view(self, ident):
        store = Extensions(self.root)
        try:
            ext = store.db.execute('SELECT * FROM extensions WHERE id=?', (ident,)).fetchone()
            if not ext or ext['kind'] != 'mcp': raise CoreError('mcp_missing', 'MCP registration missing')
            admission = store.db.execute('SELECT * FROM mcp_admissions WHERE id=?', (ident,)).fetchone()
            base = {'id': ident, 'extension_revision': ext['revision'], 'name': ext['name'], 'config': decode(ext['config']),
                    'revision': 0, 'enabled': False, 'current': False, 'tools': [], 'selected': []}
            if admission:
                snap = decode(admission['snapshot'])
                base.update(revision=admission['revision'], enabled=bool(admission['enabled']),
                            current=admission['extension_revision'] == ext['revision'], tools=snap['tools'],
                            selected=decode(admission['tools']), protocol=snap['protocol'])
            return base
        finally: store.close()

    def list(self):
        store = Extensions(self.root)
        try: ids = [r['id'] for r in store.list() if r['kind'] == 'mcp']
        finally: store.close()
        return [self.view(i) for i in ids]

    def check(self):
        StopGate(self.root).require_running(); NetworkGate(self.root).require_online()

    def discover(self, ident, revision):
        self.check(); before = self.view(ident)
        if before['extension_revision'] != revision: raise CoreError('conflict', 'Registration changed')
        cfg = before['config']
        if cfg['transport'] != 'streamable-http' or cfg['credential_ref']:
            raise CoreError('mcp_transport_unsupported', 'Only HTTP endpoints without credentials are admitted in this version')
        def checkpoint():
            self.check()
            now = self.view(ident)
            if now['extension_revision'] != revision or now['revision'] != before['revision']:
                raise CoreError('conflict', 'Connection changed during discovery')
        session = Session(cfg['url'], checkpoint)
        info = session.initialize(); entries = [describe(t) for t in session.tools()]
        if len({t['name'] for t in entries}) != len(entries): raise CoreError('mcp_protocol', 'Duplicate tool names')
        snapshot = {'protocol': info['protocol'], 'tools': entries}
        checkpoint(); store = Extensions(self.root)
        try:
            store.db.execute('BEGIN IMMEDIATE')
            if self.view(ident)['revision'] != before['revision'] or self.view(ident)['extension_revision'] != revision:
                raise CoreError('conflict', 'Connection changed during discovery')
            store.db.execute('INSERT INTO mcp_admissions VALUES(?,?,?,?,0,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,extension_revision=excluded.extension_revision,snapshot=excluded.snapshot,enabled=0,tools=excluded.tools',
                             (ident, before['revision']+1, revision, canonical(snapshot), '[]'))
            store.db.execute('COMMIT')
        except BaseException:
            store.db.execute('ROLLBACK'); raise
        finally: store.close()
        return self.view(ident)

    def configure(self, ident, revision, selected, enabled):
        if type(revision) is not int or type(enabled) is not bool or not isinstance(selected, list) or len(selected) > 12 or any(not isinstance(x, str) for x in selected) or len(set(selected)) != len(selected):
            raise CoreError('mcp_invalid', 'Choose up to twelve tools')
        if enabled: self.check()
        store = Extensions(self.root)
        try:
            store.db.execute('BEGIN IMMEDIATE'); view = self.view(ident)
            if view['revision'] != revision or not view['current']: raise CoreError('conflict', 'Discover the current registration first')
            available = {t['name'] for t in view['tools'] if t['supported']}
            if set(selected) - available or enabled and not selected: raise CoreError('mcp_schema', 'Choose supported tools')
            store.db.execute('UPDATE mcp_admissions SET revision=revision+1,enabled=?,tools=? WHERE id=?', (enabled, canonical(selected), ident))
            store.db.execute('COMMIT')
        except BaseException:
            store.db.execute('ROLLBACK'); raise
        finally: store.close()
        return self.view(ident)

    def catalog(self):
        found = []
        for view in self.list():
            if not view['enabled'] or not view['current']: continue
            for tool in view['tools']:
                if tool['name'] not in view['selected']: continue
                found.append({'capability': capability(view['id'], tool['name']), 'name': view['name'] + ' / ' + tool['name'],
                              'description': tool['description'], 'active': 'mcp-' + digest({'config': view['config'], 'revision': view['revision'], 'tool': tool['digest']}),
                              'revision': view['revision'], 'input_schema': tool['input_schema'], 'kind': 'mcp',
                              'endpoint': view['config']['url'], 'extension_id': view['id'], 'tool_name': tool['name'], 'tool_digest': tool['digest'],
                              'available': True, 'scope': 'personal'})
        return found

    def reference(self, cap, implementation=None):
        ref = next((x for x in self.catalog() if x['capability'] == cap), None)
        if not ref: raise CoreError('module_disabled', 'Connector tool is disabled or registration changed')
        if implementation and ref['active'] != implementation: raise CoreError('package_changed', 'Connector admission changed; review a new task')
        return ref

    def validate(self, cap, args):
        if not isinstance(args, dict) or set(args) != {'text'} or not isinstance(args['text'], str):
            raise CoreError('mcp_arguments', 'Expected reviewed JSON text')
        ref = self.reference(cap)
        return arguments(ref['input_schema'], decode(args['text']))

    def execute(self, cap, implementation, args, checkpoint):
        def check():
            checkpoint(); self.check(); self.reference(cap, implementation)
        check(); ref = self.reference(cap, implementation); params = self.validate(cap, args)
        session = Session(ref['endpoint'], check); session.initialize()
        tools = session.tools()
        matches = [t for t in tools if isinstance(t, dict) and t.get('name') == ref['tool_name']]
        if len(matches) != 1 or digest(matches[0]) != ref['tool_digest']:
            raise CoreError('mcp_tool_changed', 'Server tool changed since discovery')
        check()
        result = session.request('tools/call', {'name': ref['tool_name'], 'arguments': params})
        if type(result.get('isError', False)) is not bool or not isinstance(result.get('content'), list):
            raise CoreError('mcp_protocol', 'Invalid tool result')
        # Text and structured JSON only; never render/download resource links or images.
        if any(not isinstance(x, dict) or x.get('type') != 'text' or not isinstance(x.get('text'), str) for x in result['content']):
            raise CoreError('mcp_result_unsupported', 'Only text results are supported')
        text = '\n'.join(x['text'] for x in result['content'])
        if not text and 'structuredContent' in result: text = canonical(result['structuredContent'])
        receipt = {'text': text, 'is_error': result.get('isError', False), 'source': 'mcp',
                   'endpoint': ref['endpoint'], 'tool': ref['tool_name'], 'tool_digest': ref['tool_digest'],
                   'structured': result.get('structuredContent'), 'protocol': session.version}
        if len(canonical(receipt).encode()) > 45000: raise CoreError('mcp_output_limit', 'Tool result exceeds artifact bound')
        check()
        return receipt
