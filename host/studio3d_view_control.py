"""Bounded, opt-in inspection of an already open Studio3D viewer.

No browser automation, model mutation, generated code or network forwarding.
The authenticated page applies the same controls used by the person. Results
are browser observations, not independent topology or quality certification.
"""
import base64
import hashlib
import json
import math
import re
import threading
import time

from sdk.protocol import CoreError

MODES = ('pbr', 'clay', 'wire', 'normal', 'checker', 'uv', 'base', 'roughness', 'metalness', 'ao', 'game-rig')
CAMERAS = ('iso', 'front', 'rear', 'left', 'right', 'top', 'bottom')
FIELDS = {'mode', 'camera', 'part', 'isolate', 'overlay', 'clip', 'exposure', 'lighting', 'zoom', 'light_angle'}
_HUBS, _GUARD = {}, threading.Lock()


def command(root, body):
    from host.studio3d import enabled
    if body.get('action') not in ('status', 'stop', 'list'):
        enabled(root)
    with _GUARD:
        hub = _HUBS.setdefault(str(root), ViewerInspection(root))
    return hub.command(body)


def require(ok, message):
    if not ok:
        raise CoreError('viewer_inspection_invalid', message)


def identity(value, length=32):
    return isinstance(value, str) and bool(re.fullmatch('[a-f0-9]{' + str(length) + '}', value))


def validate_view(value, objects):
    require(isinstance(value, dict) and set(value) <= FIELDS, 'Unknown view controls')
    for name, choices in [('mode', MODES), ('camera', CAMERAS), ('lighting', ('neutral', 'studio', 'reference'))]:
        if name in value:
            require(value[name] in choices, 'Unsupported ' + name)
    for name in ('isolate', 'overlay'):
        if name in value:
            require(type(value[name]) is bool, 'Boolean required')
    if 'part' in value:
        require(value['part'] is None or value['part'] in objects, 'Unknown object; read the live inventory')
    require(not value.get('isolate') or value.get('part') in objects, 'Isolation requires an explicit object')
    for name, low, high in [('clip', -1, 1), ('exposure', .2, 2.5), ('zoom', .25, 4), ('light_angle', -180, 180)]:
        if name in value:
            v = value[name]
            require(type(v) in (int, float) and math.isfinite(v) and low <= v <= high, 'Out of range ' + name)
    return dict(value)


def source_binding(root, asset_id, sha256):
    from host.studio3d import file
    raw, _ = file(root, asset_id, 'model.glb')
    require(hashlib.sha256(raw).hexdigest() == sha256, 'Model digest mismatch')


class ViewerInspection:
    """Ephemeral sessions and at-most-once dispatch; no automatic replay."""
    def __init__(self, root, verify=None, clock=None):
        self.root, self.verify = root, verify or source_binding
        self.clock = clock or time.monotonic
        self.lock = threading.RLock()
        self.sessions, self.requests = {}, {}

    def _expire(self):
        now = self.clock()
        for row in self.requests.values():
            if row['status'] in ('QUEUED', 'DISPATCHED') and now - row['_created'] > 60:
                row['status'] = 'EXPIRED' if row['status'] == 'QUEUED' else 'UNKNOWN'
        for key, row in list(self.sessions.items()):
            if now - row['_seen'] > 45:
                del self.sessions[key]

    @staticmethod
    def _public(row):
        return {k: v for k, v in row.items() if not k.startswith('_')}

    def command(self, body):
        require(isinstance(body, dict), 'Object required')
        op = body.get('action')
        with self.lock:
            self._expire()
            if op == 'register':
                require(set(body) == {'action', 'client_id', 'asset_id', 'sha256', 'objects'}, 'Invalid registration')
                require(identity(body['client_id']) and identity(body['asset_id']) and identity(body['sha256'], 64), 'Invalid identity')
                names = body['objects']
                require(isinstance(names, list) and 0 < len(names) <= 256, 'Object list required')
                require(all(isinstance(n, str) and 0 < len(n) <= 128 for n in names) and len(set(names)) == len(names), 'Unique bounded object names required')
                require(body['client_id'] not in self.sessions and len(self.sessions) < 8, 'Session exists or capacity reached')
                self.verify(self.root, body['asset_id'], body['sha256'])
                self.sessions[body['client_id']] = {k: body[k] for k in ('client_id', 'asset_id', 'sha256', 'objects')}
                self.sessions[body['client_id']]['_seen'] = self.clock()
                return {'registered': True, 'version': '1.0.1'}
            if op == 'list':
                require(set(body) == {'action', 'asset_id', 'sha256'}, 'Invalid session query')
                return {'sessions': [self._public(s) for s in self.sessions.values() if s['asset_id'] == body['asset_id'] and s['sha256'] == body['sha256']], 'modes': MODES, 'cameras': CAMERAS}
            if op == 'request':
                require(set(body) == {'action', 'id', 'client_id', 'asset_id', 'sha256', 'view', 'capture'}, 'Invalid request')
                require(identity(body['id']) and body['id'] not in self.requests, 'Request ID already consumed or invalid')
                require(type(body['capture']) is bool and len(self.requests) < 128, 'Invalid capture or session command capacity reached')
                s = self.sessions.get(body['client_id'])
                require(s and s['asset_id'] == body['asset_id'] and s['sha256'] == body['sha256'], 'No matching live viewer')
                require(not any(r['client_id'] == body['client_id'] and r['status'] in ('QUEUED', 'DISPATCHED') for r in self.requests.values()), 'Viewer already has pending work')
                view = validate_view(body['view'], s['objects'])
                row = {k: body[k] for k in ('id', 'client_id', 'asset_id', 'sha256', 'capture')}
                row.update(view=view, status='QUEUED', _created=self.clock(), evidence_kind='browser-observation-not-mesh-certification')
                self.requests[body['id']] = row
                return self._public(row)
            if op == 'status':
                require(set(body) == {'action', 'id'} and body['id'] in self.requests, 'Unknown inspection request')
                return self._public(self.requests[body['id']])
            if op in ('poll', 'stop', 'ack'):
                allowed = {'action', 'client_id', 'asset_id', 'sha256'} | ({'id', 'result'} if op == 'ack' else set())
                require(set(body) == allowed, 'Invalid viewer response')
                s = self.sessions.get(body['client_id'])
                require(s and s['asset_id'] == body['asset_id'] and s['sha256'] == body['sha256'], 'Stale or wrong viewer')
                s['_seen'] = self.clock()
                if op == 'stop':
                    del self.sessions[body['client_id']]
                    for r in self.requests.values():
                        if r['client_id'] == body['client_id'] and r['status'] in ('QUEUED', 'DISPATCHED'):
                            r['status'] = 'CANCELLED' if r['status'] == 'QUEUED' else 'UNKNOWN'
                    return {'stopped': True}
                if op == 'poll':
                    row = next((r for r in self.requests.values() if r['client_id'] == body['client_id'] and r['status'] == 'QUEUED'), None)
                    if row:
                        row['status'] = 'DISPATCHED'
                    return {'request': self._public(row) if row else None}
                row = self.requests.get(body['id'])
                require(row and row['client_id'] == body['client_id'] and row['status'] == 'DISPATCHED', 'Wrong owner or result already consumed')
                result = body['result']
                require(isinstance(result, dict) and len(json.dumps(result)) < 190000, 'Oversized result')
                require(result.get('asset_id') == row['asset_id'] and result.get('sha256') == row['sha256'], 'Result identity mismatch')
                image = result.get('image')
                if image is not None:
                    require(row['capture'] and isinstance(image, str) and image.startswith('data:image/jpeg;base64,') and len(image) < 160000, 'Invalid capture')
                    try:
                        raw = base64.b64decode(image.split(',', 1)[1], validate=True)
                    except (ValueError, TypeError):
                        raise CoreError('viewer_inspection_invalid', 'Invalid image encoding')
                    require(raw.startswith(b'\xff\xd8') and raw.endswith(b'\xff\xd9'), 'Invalid JPEG envelope')
                if not result.get('error'):
                    for name, value in row['view'].items():
                        require(result.get('applied', {}).get(name) == value, 'View control not acknowledged')
                    if 'light_angle' in row['view']:
                        observed = result.get('light_angle')
                        require(type(observed) in (int, float) and observed == row['view']['light_angle'], 'Key angle not observed')
                    require(not row['capture'] or image is not None, 'Missing requested capture')
                row.update(result=result, status='FAILED' if result.get('error') else 'SUCCEEDED')
                return {'status': row['status'], 'id': row['id']}
            raise CoreError('viewer_inspection_invalid', 'Unknown inspection action')
