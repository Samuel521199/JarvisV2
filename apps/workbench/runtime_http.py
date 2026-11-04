"""Authenticated managed-host handoff. No business database restoration."""
import threading

from control.application_runtime import coordination, LocalApprovals
from sdk.protocol import CoreError


def owner_control(handler, path):
    """OS-owner lifecycle authorization; never unlocks the household vault."""
    proof = handler.headers.get('X-Jarvis-Application-Proof', '')
    if not path.startswith('/api/runtime/') or not proof:
        return False
    server = handler.server
    if not getattr(server, 'application_build', ''):
        raise CoreError('application_unmanaged', 'This host is not managed')
    LocalApprovals(server.data_root).verify({'build': server.application_build,
        'epoch': server.application_epoch, 'boot_id': server.boot_id, 'action': path.rsplit('/', 1)[1]}, proof)
    return True


def post(handler, path, body):
    if not path.startswith('/api/runtime/'):
        return False
    server = handler.server
    if not getattr(server, 'application_build', ''):
        raise CoreError('application_unmanaged', 'This host is not managed by the application installer')
    current = coordination(server.data_root)
    if (not current or body != {'build': server.application_build, 'epoch': server.application_epoch}
            or current['build'] != server.application_build or current['epoch'] != server.application_epoch):
        raise CoreError('application_epoch', 'Host identity or generation changed')
    if path == '/api/runtime/health':
        from control.recovery.gate import StopGate
        StopGate(server.data_root).require_running()
        if server.dialogues.closing.is_set() or server.task_runner.state()['status'] == 'failed':
            raise CoreError('application_unhealthy', 'Runtime is closing or its dispatcher failed')
        handler.json({'healthy': True})
    elif path == '/api/runtime/drain':
        if current['phase'] != 'draining':
            raise CoreError('application_phase', 'A durable drain request is required')
        chats, work = server.dialogues.state(), server.task_runner.state()
        busy = bool(chats['running'] or work['active'] or server.background_lane.state()['status'] == 'running')
        handler.json({'drained': not busy})
    elif path == '/api/runtime/shutdown':
        if current['phase'] not in {'draining', 'starting', 'blocked', 'stopped'}:
            raise CoreError('application_phase', 'Host is not scheduled to stop')
        threading.Thread(target=server.shutdown, daemon=True).start()
        handler.json({'stopping': True})
    elif path == '/api/runtime/activate':
        if current['phase'] != 'active':
            raise CoreError('application_phase', 'Adoption has not committed')
        with server.dialogues.lock:
            server.dialogues._pump()
        server.task_runner.wake.set()
        handler.json({'active': True})
    else:
        raise CoreError('application_route', 'Unknown runtime operation')
    return True
