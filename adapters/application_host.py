"""Real process driver for managed loopback workbenches. Never force-kills an old host."""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

from control.local_access import read_key
from control.application_runtime import LocalApprovals
from control.paths import reject_links
from sdk.protocol import CoreError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class WorkbenchProcess:
    def __init__(self, root, port=18284, timeout=30):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise CoreError('application_port', 'Invalid managed host port')
        self.root = Path(root).resolve()
        self.port, self.timeout = port, timeout
        self.origin = 'http://127.0.0.1:' + str(port)
        self.processes = {}
        self.opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.token = None

    def metadata(self):
        with self.opener.open(self.origin + '/api/instance', timeout=2) as response:
            return json.loads(response.read(16384))

    def identity(self, selected, epoch):
        value = self.metadata()
        expected = hashlib.sha256(str(self.root).casefold().encode()).hexdigest()
        if (value.get('service') != 'jarvis-workbench' or value.get('root_digest') != expected
                or value.get('application_build') != selected['build'] or value.get('application_epoch') != epoch):
            raise CoreError('application_host_identity', 'Managed port belongs to a different root, build or generation')
        return value

    def request(self, selected, epoch, action):
        metadata = self.identity(selected, epoch)
        proof = LocalApprovals(self.root).sign({'build': selected['build'], 'epoch': epoch,
                                               'boot_id': metadata['boot_id'], 'action': action})
        request = urllib.request.Request(self.origin + '/api/runtime/' + action,
            data=json.dumps({'build': selected['build'], 'epoch': epoch}).encode(),
            headers={'Origin': self.origin, 'Content-Type': 'application/json', 'X-Jarvis-Application-Proof': proof})
        with self.opener.open(request, timeout=5) as response:
            return json.loads(response.read(16384))

    def start(self, record, selected, epoch):
        # A live/unknown listener is never overwritten or killed.
        with socket.socket() as probe:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'): probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(('127.0.0.1', self.port))
        database = self.root / 'state/core.sqlite3'
        connection = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            if connection.execute('PRAGMA user_version').fetchone()[0] != 7:
                raise CoreError('application_schema', 'Only unchanged core schema 7 is supported')
        finally:
            connection.close()
        package = Path(record['path'])
        reject_links(package)
        logs = self.root / 'deployment/logs'
        logs.mkdir(exist_ok=True)
        with (logs / (str(epoch) + '.stdout.log')).open('ab') as out, (logs / (str(epoch) + '.stderr.log')).open('ab') as error:
            process = subprocess.Popen([sys.executable, '-I', '-B', str(package / 'apps/workbench/server.py'),
                                        '--data-root', str(self.root), '--port', str(self.port),
                                        '--application-build', selected['build'], '--application-epoch', str(epoch)],
                                       cwd=package, stdin=subprocess.DEVNULL, stdout=out, stderr=error,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.processes[epoch] = process
        self.token = None

    def health(self, selected, epoch):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            process = self.processes.get(epoch)
            if process and process.poll() is not None:
                raise CoreError('application_start_failed', 'Candidate process exited; inspect its private diagnostic log')
            try:
                self.identity(selected, epoch)
                self.request(selected, epoch, 'health')
                return
            except CoreError:
                raise
            except (OSError, ValueError):
                time.sleep(.1)
        raise CoreError('application_health_timeout', 'Candidate health was not confirmed')

    def drain(self, selected, epoch):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.request(selected, epoch, 'drain')['drained']:
                return
            time.sleep(.1)
        raise CoreError('application_drain_timeout', 'Host still has running work')

    def stop(self, selected, epoch):
        process = self.processes.get(epoch)
        if process is not None and process.poll() is not None:
            return
        try:
            self.request(selected, epoch, 'shutdown')
        except urllib.error.HTTPError:
            raise
        except OSError:
            if process is None:
                # A restarted controller must also prove the host lease is free.
                from control.recovery.gate import RunLock
                with RunLock(self.root, 'workbench-host'): pass
                return
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if process is not None and process.poll() is None:
                time.sleep(.1)
                continue
            try:
                with socket.create_connection(('127.0.0.1', self.port), timeout=.5):
                    pass
            except OSError:
                from control.recovery.gate import RunLock
                with RunLock(self.root, 'workbench-host'): pass
                return
            time.sleep(.1)
        raise CoreError('application_exit_unconfirmed', 'Host exit is unconfirmed; no process was forcibly terminated')

    def activate(self, selected, epoch):
        self.request(selected, epoch, 'activate')

    def running(self, selected, epoch):
        try:
            self.identity(selected, epoch)
            self.request(selected, epoch, 'health')
            return True
        except urllib.error.HTTPError:
            raise
        except OSError:
            from control.recovery.gate import RunLock
            with RunLock(self.root, 'workbench-host'): pass
            return False
