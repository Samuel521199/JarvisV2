"""The household gate precedes every workbench data and artifact route."""
import threading
import hashlib

from control.family_identity import cookie_token, POLICY
from host.family import FamilyHost
from sdk.protocol import CoreError

LOCK = threading.Lock()
PUBLIC = {'/login', '/family', '/login.js', '/family.js', '/family.css', '/ui.js', '/icons.js',
          '/style.css', '/theme.css', '/brand.js', '/brand.css', '/logo.css', '/brand/core.png', '/brand/icon.png', '/api/family/status', '/api/instance'}
MEMBER_GET = {'/api/session', '/api/family/catalog'}
MEMBER_POST = {'/api/family', '/api/family/logout'}


def service(handler):
    with LOCK:
        if not hasattr(handler.server, 'family'): handler.server.family = FamilyHost(handler.server.data_root)
        return handler.server.family


def actor(handler, touch=True):
    token = cookie_token(handler.headers.get('Cookie'), handler.server.server_port)
    return service(handler).identity.principal(token, touch=touch), token


def gate(handler, path, write=False):
    family = service(handler)
    if not family.identity.enabled: return True
    if not write and path in PUBLIC: return True
    if write and path == '/api/family/login': return True
    principal, _ = actor(handler)
    if not principal:
        if not write and path in {'/', '/settings'}: handler.redirect('/login')
        else: handler.json({'error': 'family_session'}, 401)
        return False
    if principal['role'] == 'owner': return True
    if path in (MEMBER_POST if write else MEMBER_GET): return True
    if not write and path in {'/', '/settings'}: handler.redirect('/family')
    else: handler.json({'error': 'family_forbidden'}, 403)
    return False


def get(handler, path):
    if path == '/api/instance':
        from pathlib import Path
        root = str(Path(handler.server.data_root).resolve()).casefold()
        handler.json({'service': 'jarvis-workbench', 'root_digest': hashlib.sha256(root.encode()).hexdigest(),
                      'boot_id': getattr(handler.server, 'boot_id', ''), 'family_version': '1.0.0'})
        return True
    if path == '/api/family/status':
        family = service(handler)
        principal, _ = actor(handler, touch=False)
        handler.json({'enabled': family.identity.enabled, 'actor': principal, 'policy': POLICY, 'version': '1.0.0'})
        return True
    if path == '/api/family/catalog':
        principal, _ = actor(handler)
        if not principal: raise CoreError('family_session', 'Login required')
        handler.json({'connections': service(handler).catalog()}); return True
    return False


def post(handler, path, value):
    if not path.startswith('/api/family'): return False
    family = service(handler)
    principal, token = actor(handler)
    if path == '/api/family/login':
        if not isinstance(value, dict) or set(value) != {'id', 'password'}: raise CoreError('family_invalid', 'Invalid login')
        if not family.identity.enabled: raise CoreError('family_unavailable', 'Household not enabled')
        issued = family.identity.login(value['id'], value['password'])
        handler.family_cookie = issued
        handler.json({'actor': family.identity.principal(issued)})
    elif path == '/api/family/setup':
        if not isinstance(value, dict) or set(value) != {'password', 'policy'} or value['policy'] != POLICY:
            raise CoreError('family_invalid', 'Review the household policy before setup')
        handler.family_cookie = family.identity.setup(value['password'])
        handler.json({'ok': True})
    elif path == '/api/family/logout':
        if value != {}: raise CoreError('family_invalid', 'Unexpected logout fields')
        family.identity.logout(token); handler.family_cookie = ''; handler.json({'ok': True})
    elif path == '/api/family':
        if not principal: raise CoreError('family_session', 'Login required')
        handler.json(family.command(principal, token, value))
    else: handler.json({'error': 'not_found'}, 404)
    return True
