"""Host lifecycle for this checkout's isolated workbench and frozen model proxy.

No production restart, updater timer, credential export, OS settings change or
process termination. Shutdown is through authenticated development APIs only.
"""
import argparse
import hashlib
import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from adapters.development_bridge import exchange
from control.atomic import write_json
from control.credentials import load_envelope
from control.development_profile import read
from control.local_access import read_key
from control.paths import data_root, reject_links
from sdk.protocol import CoreError


ROOT = Path(__file__).resolve().parents[1]
FILES = ['host/development_bridge.py', 'apps/development/bridge.py', 'adapters/models/native.py',
         'adapters/models/native_transport.py', 'adapters/models/windows_signing.py', 'adapters/models/vision.py',
         'control/credentials.py', 'control/development_profile.py', 'control/network.py', 'control/paths.py',
         'control/atomic.py', 'control/recovery/gate.py', 'sdk/protocol.py', 'sdk/pricing.py',
         'modules/preferences/store.py']
FILES += [str(path.relative_to(ROOT)).replace('\\', '/') for path in (
    ROOT / name / '__init__.py' for name in ['host', 'apps', 'apps/development', 'adapters', 'adapters/models',
                                          'control', 'control/recovery', 'sdk', 'modules', 'modules/preferences']) if path.exists()]


def freeze(destination):
    destination = Path(destination).absolute()
    reject_links(destination)
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
    build = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    target = destination / build[:20]
    if not target.exists():
        target.mkdir(parents=True)
        for name in FILES:
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
        write_json(target / 'runtime-manifest.json', {'schema': 1, 'build_id': build, 'files': hashes})
    verify(target)
    return target, build


def verify(path):
    reject_links(path)
    value = json.loads((path / 'runtime-manifest.json').read_text(encoding='utf-8'))
    if set(value['files']) != set(FILES):
        raise ValueError('Unexpected proxy package contents')
    expected = hashlib.sha256(json.dumps(value['files'], sort_keys=True).encode()).hexdigest()
    if value['build_id'] != expected:
        raise ValueError('Invalid proxy package manifest')
    for name, digest in value['files'].items():
        item = path / name
        reject_links(item)
        if hashlib.sha256(item.read_bytes()).hexdigest() != digest:
            raise ValueError('Proxy package integrity failed: ' + name)
    return value


def json_get(url):
    with urllib.request.urlopen(url, timeout=2) as response:
        return json.load(response)


def wait_ready(check, child):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('Development service exited; inspect its local log')
        try:
            return check()
        except Exception:
            time.sleep(.2)
    raise RuntimeError('Development service is not ready; no production process was changed')


def spawn(arguments, logs, name):
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / (name + '.stdout.log')).open('ab') as output, (logs / (name + '.stderr.log')).open('ab') as error:
        return subprocess.Popen([sys.executable, '-I', '-B', *map(str, arguments)], cwd=ROOT,
                                stdin=subprocess.DEVNULL, stdout=output, stderr=error,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def selected_proxy(production, adopt=False):
    selection = production / 'development/proxy-active.json'
    if adopt:
        package, build = freeze(production / 'development/proxy-releases')
        write_json(selection, {'schema': 1, 'package': package.name, 'build_id': build})
    if not selection.exists():
        raise ValueError('No approved frozen proxy; explicitly use --adopt-proxy after review and tests')
    value = json.loads(selection.read_text(encoding='utf-8'))
    build = value.get('build_id', '')
    if (value.get('schema') != 1 or len(build) != 64 or any(c not in '0123456789abcdef' for c in build)
            or value.get('package') != build[:20]):
        raise ValueError('Invalid approved proxy selection')
    package = production / 'development/proxy-releases' / value['package']
    if verify(package)['build_id'] != build:
        raise ValueError('Approved proxy package identity changed')
    return package, build


def start(root, production, port, *, adopt_proxy=False):
    profile = read(root)
    if not profile:
        raise ValueError('Prepare the isolated development profile first')
    secret = load_envelope(production / 'private/development-bridge.dpapi')
    if secret['client_id'] != profile['client_id']:
        raise ValueError('Production and development grants do not match')
    if adopt_proxy:
        _, candidate = freeze(production / 'development/proxy-releases')
        try:
            current = exchange(root, '/status')
        except CoreError as exc:
            if exc.code != 'development_bridge_unavailable':
                raise
        else:
            if current.get('build_id') != candidate:
                raise ValueError('Stop the previous proxy before selecting a different reviewed package')
    package, build = selected_proxy(production, adopt_proxy)
    logs = root / 'logs'
    children = {}
    try:
        status = exchange(root, '/status')
        if status['build_id'] != build:
            raise ValueError('A different frozen proxy is active; stop development services before adopting this build')
    except CoreError as exc:
        if exc.code != 'development_bridge_unavailable':
            raise
        child = spawn([package / 'apps/development/bridge.py', '--production-data', production,
                       '--port', profile['bridge_origin'].rsplit(':', 1)[1]], logs, 'development-bridge')
        status = wait_ready(lambda: exchange(root, '/status'), child)
        if status['build_id'] != build:
            raise ValueError('Unexpected proxy identity; candidate not adopted')
        children['bridge'] = child.pid
    url = 'http://127.0.0.1:' + str(port)
    expected = hashlib.sha256(str(root.resolve()).casefold().encode()).hexdigest()

    def inspect():
        value = json_get(url + '/api/instance')
        if value.get('root_digest') != expected or value.get('service') != 'jarvis-workbench':
            raise ValueError('The development port belongs to a different data root')
        return value

    try:
        inspect()
    except OSError:
        child = spawn([ROOT / 'apps/workbench/server.py', '--port', port, '--data-root', root], logs, 'development-workbench')
        wait_ready(inspect, child)
        children['workbench'] = child.pid
    receipt = {'schema': 1, 'development_origin': url, 'bridge_origin': profile['bridge_origin'],
               'proxy_build': build, 'proxy_package': str(package), 'started_pids': children,
               'production_restarted': False, 'production_data_copied': False}
    write_json(root / 'state/development-runtime.json', receipt)
    return receipt


def stop(root, port):
    import http.cookiejar
    origin = 'http://127.0.0.1:' + str(port)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    key = read_key(root)
    request = urllib.request.Request(origin + '/api/local-access', data=json.dumps({'key': key}).encode(),
                                     headers={'Origin': origin, 'Content-Type': 'application/json'})
    with opener.open(request, timeout=5) as response:
        response.read()
    with opener.open(origin + '/api/session', timeout=5) as response:
        session = json.load(response)
    request = urllib.request.Request(origin + '/api/development/shutdown', data=b'{}',
                                     headers={'Origin': origin, 'Content-Type': 'application/json', 'X-Jarvis-Token': session['token']})
    with opener.open(request, timeout=5) as response:
        workbench = json.load(response)
    wait_closed(port)
    bridge = exchange(root, '/shutdown', {})
    wait_closed(int(read(root)['bridge_origin'].rsplit(':', 1)[1]))
    return {'workbench': workbench, 'bridge': bridge, 'production_stopped': False}


def wait_closed(port):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.5):
                pass
        except OSError:
            return
        time.sleep(.1)
    raise RuntimeError('Development service has not stopped; no process was forcibly terminated')


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status'], nargs='?', default='start')
    parser.add_argument('--production-data', type=Path)
    parser.add_argument('--development-data', type=Path, default=ROOT / 'user-data')
    parser.add_argument('--port', type=int, default=18283)
    parser.add_argument('--open-browser', action='store_true')
    parser.add_argument('--adopt-proxy', action='store_true', help='Explicitly adopt reviewed proxy code; normal starts keep the frozen version')
    args = parser.parse_args(arguments)
    root = data_root(args.development_data)
    production_path = args.production_data or (read(root) or {}).get('production_data')
    if not production_path:
        raise SystemExit('Supply --production-data or configure an isolated development profile first')
    production = data_root(production_path)
    if root == production or root in production.parents or production in root.parents:
        raise SystemExit('Production data cannot be a development target')
    if args.action == 'start':
        result = start(root, production, args.port, adopt_proxy=args.adopt_proxy)
    elif args.action == 'stop':
        result = stop(root, args.port)
    else:
        result = exchange(root, '/status')
    print(json.dumps(result, ensure_ascii=False))
    if args.action == 'start' and args.open_browser:
        import webbrowser
        from urllib.parse import quote
        key = read_key(root)
        if not key:
            raise RuntimeError('Development workbench access key is unavailable')
        webbrowser.open(result['development_origin'] + '/#access=' + quote(key, safe=''))


if __name__ == '__main__':
    main()
