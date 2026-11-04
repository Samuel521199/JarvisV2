"""Owner-operated application staging and independent, locally anchored release checks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

from adapters.application_host import WorkbenchProcess
from control.paths import data_root, reject_links
from modules.release_recovery.application import Applications, build, inspect_package, TOPS
from sdk.protocol import CoreError

ROOT = Path(__file__).resolve().parents[1]
TESTS = ['test_model_transport.py', 'test_settings_management.py', 'test_preferences_dialogue.py',
         'test_workbench.py', 'test_local_access.py', 'test_application_runtime.py']


def tracked_runtime(source):
    result = subprocess.run(['git', '-C', str(source), 'ls-files', '-z'], check=True, capture_output=True)
    return [name for name in result.stdout.decode().split('\0') if name and (
        name.split('/')[0] in TOPS or name in {'VERSION', 'tools/architecture-baseline.json'})
        and not name.endswith(('.pyc', '.blend', '.glb', '.fbx'))]


def validator(root, *, reviewed_source=False):
    """Candidate code is executed only after local source review and the static gate.

    This deliberately does not provide an arbitrary-code security sandbox.
    Independent checks/test bodies come from this controller, not the candidate.
    """
    def evaluate(package):
        command = [sys.executable, '-I', '-B', str(ROOT / 'tools/check_architecture.py'),
                   '--root', str(package), '--policy-root', str(ROOT)]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=60)
        try:
            architecture = json.loads(result.stdout)
            errors = architecture['errors']
        except (ValueError, KeyError):
            errors = ['Architecture checker could not inspect the candidate']
        report = {'schema': 1, 'passed': False, 'reviewed_source': reviewed_source,
                  'architecture_passed': result.returncode == 0 and not errors,
                  'architecture_error_count': len(errors), 'architecture_sample': errors[:8],
                  'policy_sha256': hashlib.sha256((ROOT / 'tools/check_architecture.py').read_bytes()
                           + (ROOT / 'tools/architecture-baseline.json').read_bytes()
                           + b''.join((ROOT / 'tests' / name).read_bytes() for name in TESTS)).hexdigest()}
        if not report['architecture_passed'] or not reviewed_source:
            return report
        base = root / 'deployment/validation'
        base.mkdir(exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix='application-check-', dir=base)).resolve()
        try:
            shutil.copytree(package, workspace, dirs_exist_ok=True)
            tests = workspace / 'tests'
            tests.mkdir()
            for name in TESTS:
                (tests / name).write_bytes((ROOT / 'tests' / name).read_bytes())
            script = ('import sys,unittest;sys.path.insert(0,' + repr(str(workspace)) + ');'
                      'loader=unittest.TestLoader();suite=unittest.TestSuite(loader.discover("tests",pattern=n) for n in '
                      + repr(TESTS) + ');r=unittest.TextTestRunner().run(suite);'
                      'print("RESULT",r.testsRun,len(r.failures),len(r.errors),len(r.skipped));'
                      'sys.exit(not r.wasSuccessful())')
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script], cwd=workspace,
                                    capture_output=True, text=True, encoding='utf-8', timeout=120)
            # Test overlays may not change any candidate runtime byte.
            manifest = inspect_package(package)[1]
            intact = all(hashlib.sha256((workspace / name).read_bytes()).hexdigest() == meta['sha256']
                         for name, meta in manifest['files'].items())
            counts = result.stdout.rsplit('RESULT ', 1)[-1].strip()
            report.update(tests_passed=result.returncode == 0, tests_summary=counts[:100], runtime_intact=intact,
                          passed=result.returncode == 0 and intact)
            return report
        finally:
            # Only this freshly generated validation copy is disposable.
            reject_links(workspace)
            if not workspace.is_relative_to(base.resolve()) or not workspace.name.startswith('application-check-'):
                raise CoreError('application_cleanup', 'Validation cleanup escaped its owned workspace')
            shutil.rmtree(workspace)
    return evaluate


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'stage', 'validate', 'adopt', 'update', 'rollback', 'recover', 'start', 'stop', 'status', 'retire', 'unretire'])
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--version')
    parser.add_argument('--build')
    parser.add_argument('--expected-epoch', type=int)
    parser.add_argument('--port', type=int, default=18284)
    parser.add_argument('--reviewed-source', action='store_true')
    args = parser.parse_args(arguments)
    root = data_root(args.data_root)
    app = Applications(root)
    if args.action == 'update':
        epoch = app.state()['epoch']
        archive = args.archive or root / 'deployment/incoming' / (uuid.uuid4().hex + '.zip')
        version = args.version or (args.source / 'VERSION').read_text(encoding='utf-8').strip()
        ident = build(args.source, tracked_runtime(args.source), archive, version)
        app.stage(archive)
        checked = app.validate(ident, validator(root, reviewed_source=args.reviewed_source))
        if not checked.get('approval'):
            print(json.dumps(checked, ensure_ascii=False))
            raise SystemExit(2)
        value = app.adopt(ident, WorkbenchProcess(root, args.port), expected_epoch=epoch)
    elif args.action == 'build':
        if not args.archive or not args.version: parser.error('build requires --archive and --version')
        value = {'build': build(args.source, tracked_runtime(args.source), args.archive, args.version)}
    elif args.action == 'stage':
        if not args.archive: parser.error('stage requires --archive')
        value = app.stage(args.archive)
    elif args.action == 'validate':
        if not args.build: parser.error('validate requires --build')
        value = app.validate(args.build, validator(root, reviewed_source=args.reviewed_source))
    elif args.action == 'status':
        value = app.state()
    elif args.action in {'retire', 'unretire'}:
        if not args.build: parser.error('retirement requires --build')
        value = app.retire(args.build, restore=args.action == 'unretire')
    else:
        driver = WorkbenchProcess(root, args.port)
        if args.action == 'adopt':
            if not args.build: parser.error('adopt requires --build')
            value = app.adopt(args.build, driver, expected_epoch=args.expected_epoch)
        else:
            value = getattr(app, args.action)(driver)
    # Account credentials, access keys, source or private model replies are not printed.
    print(json.dumps(value, ensure_ascii=False))
    if args.action == 'validate' and not value.get('approval'):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
