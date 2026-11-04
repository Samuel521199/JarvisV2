"""Code-only application A/B lifecycle. Business databases are never restored or copied."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import time
import uuid
import zipfile

from control.application_runtime import LocalApprovals, publish, coordination
from control.atomic import write_json
from control.paths import child, reject_links
from control.recovery.gate import RunLock, StopGate
from sdk.protocol import CoreError, canonical, read_json

ENTRY = 'apps/workbench/server.py'
LIMIT = 256 * 1024 * 1024
TOPS = {'sdk', 'control', 'adapters', 'modules', 'host', 'apps', 'config', 'contracts', 'seed', 'external', 'packaging'}


def relative(name):
    if not isinstance(name, str):
        raise CoreError('application_path', 'Invalid application path type')
    path = PurePosixPath(name)
    if (not isinstance(name, str) or '\\' in name or ':' in name or path.is_absolute()
            or any(p in {'', '.', '..', 'user-data', '.git', '.venv', '__pycache__', 'target', 'private'}
                   or p.endswith(('.', ' ')) or any(ord(c) < 32 for c in p)
                   or p.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                      *('COM'+str(i) for i in range(1, 10)), *('LPT'+str(i) for i in range(1, 10)),
                      'COM¹', 'COM²', 'COM³', 'LPT¹', 'LPT²', 'LPT³'} for p in path.parts)
            or path.as_posix() != name or len(name) > 240):
        raise CoreError('application_path', 'Invalid application package path')
    if name not in {'VERSION', 'tools/architecture-baseline.json'} and path.parts[0] not in TOPS:
        raise CoreError('application_path', 'Path is outside the application runtime')
    return path


def inspect_package(folder):
    reject_links(folder)
    manifest = read_json(folder / 'application.json')
    if (set(manifest) != {'schema', 'version', 'entry', 'files', 'data_schema'} or manifest['schema'] != 1
            or manifest['entry'] != ENTRY or manifest['data_schema'] != 7
            or not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', manifest.get('version', ''))
            or not isinstance(manifest['files'], dict) or not 2 <= len(manifest['files']) <= 10000
            or ENTRY not in manifest['files'] or 'VERSION' not in manifest['files']):
        raise CoreError('application_manifest', 'Invalid application manifest or unsupported data schema')
    total = 0
    for name, metadata in manifest['files'].items():
        relative(name)
        path = folder / name
        reject_links(path)
        if (not path.is_file() or set(metadata) != {'sha256', 'size'}
                or type(metadata['size']) is not int or metadata['size'] < 0
                or metadata['size'] != path.stat().st_size
                or hashlib.sha256(path.read_bytes()).hexdigest() != metadata['sha256']):
            raise CoreError('application_integrity', 'Application file integrity failed')
        total += metadata['size']
        if total > LIMIT:
            raise CoreError('application_size', 'Application exceeds local installation limit')
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    if actual != set(manifest['files']) | {'application.json'}:
        raise CoreError('application_integrity', 'Application contains unmanifested files')
    if (folder / 'VERSION').read_text(encoding='utf-8').strip() != manifest['version']:
        raise CoreError('application_version', 'Runtime version and manifest version differ')
    build = hashlib.sha256(canonical(manifest).encode()).hexdigest()
    return build, manifest


def build(source, names, destination, version):
    """Construct a data archive from an explicit tracked source inventory; never run it."""
    source, destination = Path(source).resolve(), Path(destination).absolute()
    reject_links(destination)
    files, payload = {}, {}
    for name in sorted(set(names)):
        relative(name)
        path = source / name
        reject_links(path)
        raw = path.read_bytes()
        if len(raw) > 16 * 1024 * 1024:
            raise CoreError('application_size', 'Runtime file exceeds 16 MiB')
        files[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
        payload[name] = raw
    manifest = {'schema': 1, 'version': version, 'entry': ENTRY, 'data_schema': 7, 'files': files}
    if sum(m['size'] for m in files.values()) > LIMIT:
        raise CoreError('application_size', 'Application exceeds local installation limit')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream, zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo('application.json'), canonical(manifest), compress_type=zipfile.ZIP_DEFLATED)
        for name, raw in payload.items():
            archive.writestr(zipfile.ZipInfo(name), raw, compress_type=zipfile.ZIP_DEFLATED)
    return hashlib.sha256(canonical(manifest).encode()).hexdigest()


class Applications:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.base = child(self.root, 'deployment')
        self.base.mkdir(exist_ok=True)
        reject_links(self.base / 'control.sqlite3')
        if not (self.base / 'control.sqlite3').exists() and coordination(self.root) is not None:
            raise CoreError('application_journal_missing', 'Managed host state exists without its control journal; do not reset its generation')
        self.approvals = LocalApprovals(self.root)
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS packages(build TEXT PRIMARY KEY,body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS status(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,body TEXT NOT NULL);''')
            db.execute('INSERT OR IGNORE INTO status VALUES(1,?)', (canonical({'schema': 1, 'epoch': 0,
                'phase': 'stopped', 'active': None, 'previous': None, 'pending': None, 'pending_epoch': None, 'error': None}),))

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.base / 'control.sqlite3', timeout=5, isolation_level=None)
        connection.execute('PRAGMA synchronous=FULL')
        try:
            yield connection
        finally:
            connection.close()

    def state(self):
        with self.db() as db:
            return json.loads(db.execute('SELECT body FROM status WHERE id=1').fetchone()[0])

    def save(self, state, event):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE status SET body=? WHERE id=1', (canonical(state),))
            db.execute('INSERT INTO events(body) VALUES(?)', (canonical({'time': time.time(), 'event': event,
                                                                       'state': state}),))
            db.commit()
        selected = state['pending'] if state.get('pending_epoch') is not None else state['active']
        if selected:
            publish(self.root, selected['build'], selected.get('epoch', state['epoch']), state['phase'])
        elif coordination(self.root):
            publish(self.root, coordination(self.root)['build'], state['epoch'], state['phase'])

    def record(self, build):
        if not isinstance(build, str) or not re.fullmatch('[a-f0-9]{64}', build):
            raise CoreError('application_build', 'Invalid build identity')
        with self.db() as db:
            row = db.execute('SELECT body FROM packages WHERE build=?', (build,)).fetchone()
        if row is None:
            raise CoreError('application_missing', 'Application package is not staged')
        return json.loads(row[0])

    @contextmanager
    def staging(self):
        parent = self.base / 'staging'
        incoming = parent / uuid.uuid4().hex
        incoming.mkdir(parents=True)
        try:
            yield incoming
        finally:
            if incoming.exists():
                reject_links(incoming)
                if not incoming.resolve().is_relative_to(parent.resolve()) or not re.fullmatch('[a-f0-9]{32}', incoming.name):
                    raise CoreError('application_cleanup', 'Staging cleanup escaped its owned directory')
                shutil.rmtree(incoming)

    def stage(self, archive):
        with RunLock(self.root, 'application-release'), self.staging() as incoming:
            total, seen = 0, set()
            with zipfile.ZipFile(archive) as package:
                if len(package.infolist()) > 10001:
                    raise CoreError('application_size', 'Too many package members')
                for entry in package.infolist():
                    name = entry.filename
                    if name != 'application.json':
                        relative(name)
                    identity = name.casefold()
                    if (identity in seen or entry.is_dir() or stat.S_ISLNK(entry.external_attr >> 16)
                            or entry.flag_bits & 1 or entry.file_size > 16 * 1024 * 1024):
                        raise CoreError('application_archive', 'Invalid or duplicate package member')
                    seen.add(identity)
                    total += entry.file_size
                    if total > LIMIT:
                        raise CoreError('application_size', 'Expanded application exceeds its limit')
                    path = incoming / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(entry) as stream:
                        raw = stream.read(entry.file_size + 1)
                    if len(raw) != entry.file_size:
                        raise CoreError('application_archive', 'Package member size changed')
                    path.write_bytes(raw)
            ident, manifest = inspect_package(incoming)
            with self.db() as db:
                old = db.execute('SELECT body FROM packages WHERE build=?', (ident,)).fetchone()
            if old and json.loads(old[0]).get('retired'):
                raise CoreError('application_retired', 'Restore the recorded retired package explicitly')
            # Content-addressed staging is distinct from active A/B slots.
            destination = self.base / 'packages' / ident
            destination.parent.mkdir(exist_ok=True)
            reject_links(destination)
            if not destination.resolve().is_relative_to((self.base / 'packages').resolve()):
                raise CoreError('application_path', 'Package escaped its content store')
            if destination.exists():
                inspect_package(destination)
            else:
                incoming.rename(destination)
            body = {'build': ident, 'version': manifest['version'], 'path': str(destination), 'approval': None}
            with self.db() as db:
                db.execute('INSERT OR IGNORE INTO packages VALUES(?,?)', (ident, canonical(body)))
            return self.record(ident)

    def validate(self, ident, validator):
        with RunLock(self.root, 'application-release'):
            record = self.record(ident)
            if record.get('retired'):
                raise CoreError('application_retired', 'Restore retired code before revalidation')
            actual, manifest = inspect_package(Path(record['path']))
            if actual != ident:
                raise CoreError('application_integrity', 'Staged package identity changed')
            report = validator(Path(record['path']))
            if inspect_package(Path(record['path']))[0] != ident:
                raise CoreError('application_integrity', 'Validation changed the candidate')
            record['report'] = report
            if report.get('passed') is True:
                self.approvals.initialize()
                receipt = {'build': ident, 'data_schema': manifest['data_schema'], 'report': report,
                           'validated_at': time.time()}
                record['approval'] = {'receipt': receipt, 'mac': self.approvals.sign(receipt)}
            else:
                record['approval'] = None
            with self.db() as db:
                db.execute('UPDATE packages SET body=? WHERE build=?', (canonical(record), ident))
            return record

    def approved(self, ident, *, fresh=True):
        record = self.record(ident)
        if record.get('retired'):
            raise CoreError('application_retired', 'Retired code cannot be adopted')
        actual, _ = inspect_package(Path(record['path']))
        proof = record.get('approval')
        if record.get('retired') or actual != ident or not proof or proof['receipt']['build'] != ident:
            raise CoreError('application_not_approved', 'Independent validation is required')
        self.approvals.verify(proof['receipt'], proof['mac'])
        if fresh and time.time() - proof['receipt']['validated_at'] > 86400:
            raise CoreError('application_approval_expired', 'Revalidate the application before adoption')
        return record

    def adopt(self, ident, driver, *, rollback=False, expected_epoch=None):
        with RunLock(self.root, 'application-release'):
            StopGate(self.root).require_running()
            state = self.state()
            if expected_epoch is not None and state['epoch'] != expected_epoch:
                raise CoreError('application_epoch', 'Active baseline changed while the candidate was being checked')
            if state['phase'] not in {'active', 'stopped'}:
                raise CoreError('application_recovery_required', 'Resolve the interrupted handoff first')
            if rollback and (not state['previous'] or state['previous']['build'] != ident):
                raise CoreError('application_rollback', 'Only the recorded previous version can be restored')
            restarting = state['phase'] == 'stopped' and state['active'] and state['active']['build'] == ident
            candidate = self.approved(ident, fresh=not (rollback or restarting))
            if state['phase'] == 'active' and state['active'] and state['active']['build'] == ident:
                return state
            old = state['active']
            running = state['phase'] == 'active'
            selected = {'build': ident, 'version': candidate['version'],
                        'slot': 'B' if old and old['slot'] == 'A' else 'A'}
            state.update(phase='draining', pending=selected, pending_epoch=None, error=None)
            self.save(state, 'handoff_requested')
            if old and running:
                try:
                    driver.drain(old, state['epoch'])
                    driver.stop(old, state['epoch'])
                except Exception:
                    state.update(phase='blocked', error='old_host_not_stopped')
                    self.save(state, 'handoff_blocked')
                    raise CoreError('application_drain_blocked', 'Old host was not stopped; candidate was not launched') from None
            state.update(epoch=state['epoch'] + 1, phase='starting', pending_epoch=state['epoch'] + 1)
            selected['epoch'] = state['epoch']
            self.save(state, 'candidate_starting')
            try:
                StopGate(self.root).require_running()
                driver.start(candidate, selected, state['epoch'])
                driver.health(selected, state['epoch'])
            except Exception:
                return self._restore(state, driver, 'candidate_unhealthy')
            state.update(phase='active', active=selected, previous=old, pending=None, pending_epoch=None)
            self.save(state, 'candidate_adopted')
            driver.activate(selected, state['epoch'])
            return state

    def _restore(self, state, driver, reason):
        pending = state['pending']
        if pending and reason == 'candidate_unhealthy':
            record = self.record(pending['build'])
            record.update(approval=None, adoption_failure={'reason': reason, 'epoch': state['epoch'], 'time': time.time()})
            with self.db() as db:
                db.execute('UPDATE packages SET body=? WHERE build=?', (canonical(record), pending['build']))
        try:
            if pending and state.get('pending_epoch') is not None:
                driver.stop(pending, state['pending_epoch'])
        except Exception:
            state.update(phase='blocked', error='candidate_not_stopped')
            self.save(state, 'recovery_blocked')
            raise CoreError('application_recovery_blocked', 'Candidate exit is unconfirmed; old host was not relaunched') from None
        old = state['active']
        state.update(error=reason)
        if not old:
            state.update(phase='stopped', pending=None, pending_epoch=None)
            self.save(state, 'initial_install_failed')
            return state
        StopGate(self.root).require_running()
        self.approved(old['build'], fresh=False)
        old = {**old, 'epoch': state['epoch'] + 1}
        state.update(epoch=state['epoch'] + 1, phase='starting', pending=old, pending_epoch=old['epoch'])
        self.save(state, 'baseline_restoring')
        try:
            driver.start(self.record(old['build']), old, state['epoch'])
            driver.health(old, state['epoch'])
        except Exception:
            state.update(phase='blocked', error='baseline_unhealthy')
            self.save(state, 'baseline_restore_failed')
            raise CoreError('application_recovery_blocked', 'Baseline health could not be confirmed') from None
        state.update(phase='active', active=old, pending=None, pending_epoch=None)
        self.save(state, 'baseline_restored')
        driver.activate(old, state['epoch'])
        return state

    def recover(self, driver):
        with RunLock(self.root, 'application-release'):
            state = self.state()
            StopGate(self.root).require_running()
            self.save(state, 'controller_reconciled')
            if state['phase'] in {'draining', 'starting', 'blocked'}:
                if state['active'] and state.get('pending_epoch') is None:
                    state.update(phase='draining')
                    self.save(state, 'drain_retried')
                    driver.drain(state['active'], state['active']['epoch'])
                    driver.stop(state['active'], state['active']['epoch'])
                return self._restore(state, driver, 'interrupted_handoff')
            if state['phase'] == 'active':
                driver.health(state['active'], state['epoch'])
                driver.activate(state['active'], state['epoch'])
            return state

    def retire(self, ident, *, restore=False):
        with RunLock(self.root, 'application-release'):
            state = self.state()
            if any(value and value['build'] == ident for value in (state['active'], state['previous'], state['pending'])):
                raise CoreError('application_in_use', 'Active, previous and in-flight versions cannot be retired')
            record = self.record(ident)
            original, retired = self.base / 'packages' / ident, self.base / 'retired' / ident
            source, destination = (retired, original) if restore else (original, retired)
            if bool(record.get('retired')) == (not restore) and not record.get('retirement_pending'):
                return record
            record.update(retired=True, retirement_pending=True)
            with self.db() as db: db.execute('UPDATE packages SET body=? WHERE build=?', (canonical(record), ident))
            if source.exists():
                reject_links(source); reject_links(destination)
                if not source.resolve().is_relative_to(self.base.resolve()) or not destination.resolve().is_relative_to(self.base.resolve()):
                    raise CoreError('application_path', 'Retirement escaped the owned code store')
                inspect_package(source)
                destination.parent.mkdir(exist_ok=True)
                source.rename(destination)
            if inspect_package(destination)[0] != ident:
                raise CoreError('application_integrity', 'Retired package identity changed')
            record.update(path=str(destination), retired=not restore, retirement_pending=False)
            with self.db() as db: db.execute('UPDATE packages SET body=? WHERE build=?', (canonical(record), ident))
            return record

    def rollback(self, driver):
        previous = self.state()['previous']
        if not previous:
            raise CoreError('application_rollback', 'No previous adopted version is available')
        return self.adopt(previous['build'], driver, rollback=True)

    def stop(self, driver):
        with RunLock(self.root, 'application-release'):
            state = self.state()
            if state['phase'] != 'active' or not state['active']:
                raise CoreError('application_phase', 'Resolve the current transition before stopping')
            state.update(phase='draining')
            self.save(state, 'owner_stop_requested')
            driver.drain(state['active'], state['epoch'])
            driver.stop(state['active'], state['epoch'])
            state.update(phase='stopped')
            self.save(state, 'owner_stopped')
            return state

    def start(self, driver):
        with RunLock(self.root, 'application-release'):
            StopGate(self.root).require_running()
            state = self.state()
            if state['phase'] not in {'active', 'stopped'} or not state['active']:
                raise CoreError('application_recovery_required', 'Adopt a version or resolve the interrupted handoff first')
            self.approved(state['active']['build'], fresh=False)
            self.save(state, 'owner_start_requested')
            if driver.running(state['active'], state['epoch']):
                if state['phase'] != 'active':
                    raise CoreError('application_state_invalid', 'A stopped host still owns the listener')
                driver.activate(state['active'], state['epoch'])
                return state
            driver.stop(state['active'], state['epoch'])
            return self._restore(state, driver, None)
