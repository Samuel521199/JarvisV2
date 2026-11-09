"""Reconcile retained evidence and run repository gates; no model/network calls.

Local fixture paths are explicit and contain synthetic data only. This does not
rerun the paid shadow or claim that repaired cases remain unseen.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from sdk.application_policy import TESTS, TEST_SUPPORT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def seeds(work, cases):
    failures = []
    for case in cases:
        path = work / case['id'] / 'state/commitments.sqlite3'
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            n = case['active_count']
            counts = {table: db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                      for table in ('commitments', 'history', 'operations', 'conversation_operations')}
            state = db.execute("SELECT COUNT(*) FROM commitments WHERE status!='OPEN' OR revision!=1 OR posted_at IS NOT NULL").fetchone()[0]
            if any(value != n for value in counts.values()) or state:
                failures.append({'id': case['id'], 'counts': counts, 'changed_states': state})
        finally:
            db.close()
        path = work / case['id'] / 'state/dialogue.sqlite3'
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            if db.execute('SELECT COUNT(*) FROM turns').fetchone()[0]:
                failures.append({'id': case['id'], 'unexpected_persisted_shadow_turn': True})
        finally:
            db.close()
    return {'root': str(work), 'cases': len(cases), 'seed_rows_only': not failures, 'failures': failures}


def command(item):
    name, args = item
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    (HERE / (name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
    record = {'exit_code': result.returncode, 'log': name + '.log'}
    if name == 'architecture':
        record['report'] = json.loads(result.stdout)
    return name, record


if __name__ == '__main__':
    # The documentation gate checks links to this audit while it is being built.
    target = HERE / 'audit.json'
    target.write_text('{"status":"checking"}\n', encoding='utf-8')
    cases = read('cases.json'); plan = read('plan.json'); before = read('offline-before.json')
    after = read('offline-after.json'); live = read('live-result.json'); replay = read('live-replay-after.json')
    rollback = read('rollback-result.json'); regression = read('regression.json'); package = read('package-result.json')
    intent = 'modules/task_resource/commitment_intent.py'
    work = Path('D:/jarvisTest/commitment-shadow-package-20261108-final')
    manifest = json.loads((work / 'package/application.json').read_text(encoding='utf-8'))
    mismatches = [name for name, meta in manifest['files'].items() if sha(ROOT / name) != meta['sha256']]
    policy = hashlib.sha256((ROOT / 'tools/check_architecture.py').read_bytes()
        + (ROOT / 'tools/architecture-baseline.json').read_bytes()
        + b''.join((ROOT / 'tests' / name).read_bytes() for name in TESTS + TEST_SUPPORT)).hexdigest()
    live_cases = [case for case in cases['cases'] if case['id'] in cases['live_ids']]
    fixture_checks = [seeds(Path('D:/jarvisTest/commitment-shadow-offline-final-metrics'), cases['cases']),
                      seeds(Path('D:/jarvisTest/commitment-live-shadow-20261108-r2'), live_cases)]
    checks = {
        'frozen_cases_unchanged': sha(HERE / 'cases.json') == plan['cases_sha256'] == before['cases_sha256'] == after['cases_sha256'],
        'before_sources_bound': before['source_sha256'] == plan['source_sha256'][intent] == live['source_sha256'][intent],
        'after_sources_bound': after['source_sha256'] == replay['source_sha256'] == sha(ROOT / intent),
        'original_live_responses_unchanged': sha(HERE / 'live-result.json') == replay['live_result_sha256'],
        'twelve_real_calls_completed': live['status'] == 'completed' and live['calls_started'] == len(live['outcomes']) == plan['live_call_limit'] == 12
            and len({row['id'] for row in live['outcomes']}) == 12 and all(row['status'] == 'SUCCEEDED' for row in live['outcomes']),
        'replay_added_no_calls': replay['model_calls'] == 0,
        'owned_proxy_stopped': live['owned_proxy_stopped'],
        'shadow_kept_seed_state_only': all(row['seed_rows_only'] for row in fixture_checks),
        'after_safety_gate': all(after['summary'][key] == replay['summary'][key] == value for key, value in plan['safety_gate'].items()),
        'supported_formats_non_regression': after['summary']['supported_automatic_coverage'] >= plan['supported_correct_auto_min_fraction'],
        'old_versions_characterized_incompatible': rollback['status'] == 'passed_characterization' and len(rollback['old_versions']) == 2
            and all(row['data_unchanged'] and not row['feature_compatible'] and row['controller_preflight'] == 'application_data_compatibility' for row in rollback['old_versions']),
        'current_resume_and_stop': rollback['current_preflight']['compatible'] and rollback['stop_preserved'] and all(rollback['new_resume'].values()),
        'rollback_sources_current': all(sha(ROOT / name) == digest for name, digest in rollback['sources_sha256'].items()),
        'related_regression': regression['tests'] == 77 and regression['failures'] == regression['errors'] == regression['skipped'] == 0,
        'independent_package': package['result']['passed'] and package['result']['tests_summary'] == '163 0 0 1' and not mismatches,
        'package_log_intact': sha(HERE / 'package-tests.log') == package['result']['test_log_sha256'],
        'package_archive_intact': sha(work / 'candidate.zip') == package['archive_sha256'],
        'controller_policy_intact': policy == package['result']['policy_sha256'],
    }
    _, navigation = command(('navigation', [sys.executable, 'tools/sync_doc_navigation.py', '--root', '.']))
    with ThreadPoolExecutor(max_workers=3) as pool:
        gates = dict(pool.map(command, [
            ('docs', [sys.executable, 'tools/check_docs.py', '--root', '.']),
            ('architecture', [sys.executable, 'tools/check_architecture.py']),
            ('diff', ['git', 'diff', '--check']),
        ]))
    gates['navigation'] = navigation
    checks.update({name + '_gate': row['exit_code'] == 0 for name, row in gates.items()})
    result = {
        'status': 'passed' if all(checks.values()) else 'failed',
        'completed_utc': datetime.now(timezone.utc).isoformat(),
        'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'environment': {'platform': platform.platform(), 'python': platform.python_version(), 'workspace': str(ROOT)},
        'scope': 'new synthetic samples before repairs, bounded real Google proposals, old-code host characterization; no daily adoption',
        'checks': checks, 'gates': gates, 'fixture_checks': fixture_checks,
        'package_runtime_files': len(manifest['files']), 'package_source_mismatches': mismatches,
        'results': {'offline_before': before['summary'], 'offline_after': after['summary'],
                    'real_before': live['summary'], 'real_replay_after': replay['summary'],
                    'provider_reported_usage': replay['provider_reported_usage_totals']},
        'limitations': ['Repair cases are now development/regression data, not new unseen validation.',
            'Automatic utility is only 11/18 clear requests; English and other paraphrases remain incomplete.',
            'Twelve synthetic model calls are not a general quality benchmark; currency cost is unreconciled.',
            'Two old versions preserve data but lack features. This is not a complete migration/UI matrix.',
            'The current compatibility gate is not installed into the frozen daily controller; production was not adopted.'],
        'evidence_sha256': {path.name: sha(path) for path in sorted(HERE.iterdir()) if path.is_file() and path.name != 'audit.json'},
    }
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'failed_checks': [key for key, value in checks.items() if not value],
                      'gates': {key: value['exit_code'] for key, value in gates.items()}}, ensure_ascii=False))
    raise SystemExit(result['status'] != 'passed')
