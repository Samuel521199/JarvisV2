"""Cooperative host admission and local release approvals, independent of business data."""
import base64
import hashlib
import hmac
import secrets

from control.atomic import write_json
from control.credentials import crypt, load_envelope
from control.paths import child
from sdk.protocol import CoreError, canonical, read_json


def coordination(root):
    path = child(root, 'state/application-host.json')
    if not path.exists():
        return None
    value = read_json(path)
    if (not isinstance(value, dict) or value.get('schema') != 1
            or value.get('phase') not in {'starting', 'active', 'draining', 'stopped', 'blocked'}
            or type(value.get('epoch')) is not int or value['epoch'] < 1
            or not isinstance(value.get('build'), str) or len(value['build']) != 64):
        raise CoreError('application_state_invalid', 'Application coordination is invalid; admission remains closed')
    return value


def accepting(root):
    value = coordination(root)
    return value is None or value['phase'] == 'active'


def require_accepting(root):
    if not accepting(root):
        raise CoreError('application_maintenance', 'Application version handoff is in progress')


def publish(root, build, epoch, phase):
    value = {'schema': 1, 'build': build, 'epoch': epoch, 'phase': phase}
    write_json(child(root, 'state/application-host.json'), value)


class LocalApprovals:
    """Owner-local HMAC receipts, not portable publisher signatures or an OS sandbox."""
    def __init__(self, root):
        self.path = child(root, 'private/application-release.dpapi')

    def initialize(self):
        if self.path.exists():
            return
        self.path.parent.mkdir(exist_ok=True)
        payload = crypt(canonical({'key': secrets.token_hex(32)}).encode())
        write_json(self.path, {'schema_version': 1, 'format': 'windows-dpapi-current-user',
                               'payload': base64.b64encode(payload).decode()})

    def sign(self, value):
        key = bytes.fromhex(load_envelope(self.path)['key'])
        return hmac.new(key, canonical(value).encode(), hashlib.sha256).hexdigest()

    def verify(self, value, signature):
        if (not isinstance(signature, str) or not signature.isascii() or len(signature) != 64
                or not hmac.compare_digest(self.sign(value), signature)):
            raise CoreError('application_approval_invalid', 'Local application approval is invalid')
