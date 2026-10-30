"""Narrow authenticated loopback client. No production credentials or databases."""
import json
import urllib.error
import urllib.request
import uuid

from control.development_profile import client_secret, read
from control.network import NetworkGate
from sdk.protocol import CoreError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def exchange(root, path, body=None):
    profile = read(root)
    if not profile or path not in {'/status', '/catalog', '/model', '/shutdown'}:
        raise CoreError('development_bridge_denied', 'Not an approved development interface')
    secret = client_secret(root)
    if secret.get('client_id') != profile['client_id']:
        raise CoreError('development_bridge_denied', 'Development client binding changed')
    headers = {'Authorization': 'Bearer ' + secret['token'], 'X-Jarvis-Client': profile['client_id']}
    payload = None
    if body is not None:
        payload = json.dumps(body).encode()
        if len(payload) > 65536:
            raise CoreError('development_input_limit', 'Development request exceeds its limit')
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(profile['bridge_origin'] + path, data=payload, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=130) as response:
            raw = response.read(262145)
        if len(raw) > 262144:
            raise CoreError('development_output_limit', 'Development response exceeds its limit')
        return json.loads(raw)
    except urllib.error.HTTPError as error:
        raise CoreError('development_bridge_rejected', 'Shared development service rejected this request') from None
    except (OSError, ValueError):
        raise CoreError('development_bridge_unavailable', 'Shared development service is unavailable; no direct fallback') from None


def complete(root, route, messages, checkpoint, *, json_mode=False, reference_png=None, reference_pngs=None):
    profile = read(root)
    if (route['id'] not in profile['allowed_providers'] or reference_png is not None
            or reference_pngs is not None):
        return {'status': 'REJECTED', 'code': 'development_route_not_allowed'}
    if NetworkGate(root).read()['blocked']:
        return {'status': 'REJECTED', 'code': 'network_disabled'}
    checkpoint()
    result = exchange(root, '/model', {'request_id': uuid.uuid4().hex, 'provider': route['id'],
                                     'model': route['model'], 'messages': messages, 'json_mode': json_mode,
                                     'reasoning': route['parameters']})
    checkpoint()
    if not isinstance(result, dict) or result.get('status') not in {'SUCCEEDED', 'INVALID', 'REJECTED', 'UNKNOWN'}:
        raise CoreError('development_bridge_reply', 'Invalid shared model result')
    return result
