"""Offline diagnostic of real-work handoffs; reproduced gaps are not product passes.

Uses synthetic quotes and a deliberately limited, independently verified tool.
Proposals are supplied by the fixture; this does not test language understanding.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import tempfile
import time

from host import goals, goal_context, memory
from host.completion import command as completion_command, refresh
from host.core import Core
from modules.task_resource.scheduling import Scheduling
from sdk.protocol import CoreError, decode
from tools.probe_concurrency import configure

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['host/assistant.py', 'host/goals.py', 'host/goal_context.py', 'host/goal_growth.py',
           'host/core.py', 'host/completion.py', 'host/memory.py', 'host/task_scheduler.py',
           'modules/task_resource/plans.py', 'modules/task_resource/ledger.py',
           'modules/task_resource/completion.py', 'modules/task_resource/scheduling.py',
           'modules/context_knowledge/episodes.py', 'modules/evaluation/outcomes.py',
           'apps/workbench/goals.js', 'tools/probe_workflow_audit.py']
INPUT = 'A|120|5|source-A\nB|90|8|source-B'
OUTPUT = '最低报价：B\n' + INPUT
GOAL = '比较报价：预算最多100，交付最多5天；无同时满足者必须明确说明，保留来源。'
ORACLE = '无同时满足预算100及5天交付的报价。'
CODE = '''def run(text):
    rows = text.splitlines()
    best = rows[0].split('|')
    for row in rows[1:]:
        fields = row.split('|')
        if int(fields[1]) < int(best[1]):
            best = fields
    return '最低报价：' + best[0] + '\\n' + text
'''


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def snapshots():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def error_code(fn, *args):
    try:
        fn(*args)
    except CoreError as exc:
        return exc.code
    return None


def publish(core):
    cases = [{'input': INPUT, 'expected': OUTPUT},
             {'input': 'C|70|9|source-C', 'expected': '最低报价：C\nC|70|9|source-C'},
             {'input': 'D|50|9|source-D\nE|60|2|source-E', 'expected': '最低报价：D\nD|50|9|source-D\nE|60|2|source-E'}]
    spec = {'schema': 'jarvis.development.v1', 'request_id': 'audit-cheapest-tool',
            'principal_id': 'owner.local', 'scope_id': 'personal', 'grant_id': 'audit-unused',
            'goal': 'Select cheapest quote only; retain original rows; does not check delivery constraints',
            'capability': 'plugin.audit-cheapest.v1', 'description': 'Select minimum numeric price from name|price|days|source rows.',
            'public_cases': cases[:1], 'evaluation_cases': cases[1:], 'sample_input': INPUT,
            'limits': {'max_attempts': 1, 'max_model_calls': 1, 'max_seconds': 120}}
    candidate = {'schema': 'jarvis.code-candidate.v1', 'summary': 'Synthetic audit fixture, price comparison only',
                 'files': [{'path': 'main.py', 'content': CODE}]}
    ident = core.packages.stage(candidate, spec)
    result = core.packages.verify(ident)
    if not result['passed']:
        raise RuntimeError('Audit fixture tool failed its independent package checks')
    core.packages.activate(ident, 0)
    return ident


def create(root, key, goal, *, questions=None):
    ident = goals.command(root, {'action': 'create', 'request': {'request_id': 'audit-' + key,
                            'goal': goal, 'input_text': INPUT, 'provider': 'auto', 'model': '', 'reasoning': 'default'}})['id']
    detail = goals.command(root, {'action': 'detail', 'id': ident})
    proposal = {'schema': 'jarvis.goal-plan.v1', 'summary': 'Synthetic manual proposal; no model called',
                'input_text': INPUT, 'steps': [{'title': 'Compare price and preserve source rows',
                'capability': 'plugin.audit-cheapest.v1', 'source': 'input', 'expected': 'Minimum price only'}],
                'questions': questions or []}
    goals.command(root, {'action': 'edit', 'id': ident, 'revision': detail['plan']['revision'], 'proposal': proposal})
    return ident


def approve(root, ident, check=None, expected=None):
    detail = goals.command(root, {'action': 'detail', 'id': ident})
    value = {'action': 'approve', 'id': ident, 'revision': detail['plan']['revision']}
    if check:
        value['acceptance'] = {'coverage': 'complete', 'criteria': [
            {'id': 'report', 'step_id': 'step-1', 'check': check, 'expected': expected}]}
    return goals.command(root, value)['task_id']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    before = snapshots()
    save(out / 'plan.json', {'version': 'workflow-audit-1', 'created_at': time.time(), 'source_digests': before,
         'input': INPUT, 'limited_tool_output': OUTPUT, 'business_goal': GOAL, 'business_oracle': ORACLE,
         'scope': 'synthetic local control-path diagnostics; not semantic model or whole-product acceptance',
         'production_changes': False, 'paid_model_calls': 0})
    observations = []

    def observe(ident, title, observed, expected, interpretation):
        observations.append({'id': ident, 'title': title, 'observed': observed, 'expected_current_behavior': expected,
                             'reproduced': observed == expected, 'interpretation': interpretation})

    with tempfile.TemporaryDirectory(prefix='jarvis-workflow-audit-') as tmp:
        root = Path(tmp).resolve()
        if root.parent != Path(tempfile.gettempdir()).resolve():
            raise RuntimeError('Unexpected disposable data location')
        configure(root)
        runtime = ROOT / 'user-data/worker-runtime'
        if not runtime.is_dir():
            raise RuntimeError('Existing independent worker runtime required; no install or legacy fallback')
        shutil.copytree(runtime, root / 'worker-runtime')
        core = Core(root)
        try:
            package_id = publish(core)
            good = create(root, 'good-report', '只比较最低价格，保留报价和来源。')
            observe('WF-01', 'Reviewed proposal still requires admission',
                    {'status': goals.command(root, {'action': 'detail', 'id': good})['plan']['status'],
                     'tasks': core.db.one('SELECT COUNT(*) AS n FROM tasks')['n']},
                    {'status': 'REVIEW', 'tasks': 0}, 'Existing explicit admission boundary; no standing routine-task mandate here')
            task = approve(root, good, 'text_equals', OUTPUT)
            core.close(); core = Core(root)
            observe('WF-02', 'Durable gap between approval and separate queue request',
                    {'task_status': core.tasks.get(task)['status'], 'queued': len(Scheduling(core.db).pending())},
                    {'task_status': 'READY', 'queued': 0}, 'UI normally issues a second start call; missing that call leaves admitted work unqueued after reopen')
            Scheduling(core.db).enqueue([task]); core.run_task(task)
            observe('WF-03', 'Exact declared result can be verified', refresh(core, task)['state'], 'VERIFIED',
                    'Supported local execution and declared-condition verification, not general source research')
            actions_before = core.tasks.actions(task)
            detail = goals.command(root, {'action': 'detail', 'id': good})
            amended = error_code(goal_context.amend, core, good, detail['plan']['revision'], GOAL, INPUT)
            observe('WF-04', 'Late constraint cannot amend admitted/completed goal',
                    {'error': amended, 'actions_unchanged': core.tasks.actions(task) == actions_before},
                    {'error': 'conflict', 'actions_unchanged': True}, 'Correctly preserves history; linked selective rework still needs implementation')
            result = refresh(core, task)
            observe('WF-05', 'Report goal does not enter text-statistics method reuse',
                    {'method_available': result['method_available'], 'reuse_error': error_code(completion_command, core,
                     {'action': 'experience_reuse', 'id': task, 'request_id': 'audit-later-report', 'text': INPUT}),
                     'goal_memory_source_available': error_code(memory.goal_source, root, good) is None},
                    {'method_available': False, 'reuse_error': 'experience_changed', 'goal_memory_source_available': True},
                    'Existing goal memory candidate is distinct from a verified, reusable report method')
            for key, check, expected, predicted in [('weak', 'text_contains', '最低报价：B', 'VERIFIED'),
                                                  ('strong', 'text_equals', ORACLE, 'NEEDS_CORRECTION'),
                                                  ('unspecified', None, None, 'UNSPECIFIED')]:
                ident = create(root, key, GOAL); tid = approve(root, ident, check, expected)
                core.run_task(tid); completion = refresh(core, tid)
                actual = decode(core.tasks.actions(tid)[0]['result'])['text']
                observe('WF-06-' + key, 'Same insufficient business result under different declared conditions',
                        {'completion': completion['state'], 'actual': actual, 'business_conditions_satisfied': actual == ORACLE},
                        {'completion': predicted, 'actual': OUTPUT, 'business_conditions_satisfied': False},
                        'Weak declared coverage can pass a known-inadequate business result; stronger requirements reject it; no criteria leaves it unspecified')
                if key == 'weak':
                    observe('WF-06-memory', 'Weakly verified report can supply a goal memory candidate',
                            error_code(memory.goal_source, root, ident) is None, True,
                            'Candidate is still subject to explicit memory review; its source gate does not independently prove all business requirements')
                    completion_command(core, {'action': 'completion_feedback', 'id': tid, 'request_id': 'audit-correction',
                        'fingerprint': completion['fingerprint'], 'kind': 'reject', 'note': 'B needs 8 days, exceeding the 5-day requirement'})
                    observe('WF-07', 'Late feedback changes closure without rewriting execution',
                            {'execution': core.tasks.get(tid)['status'], 'completion': refresh(core, tid)['state'],
                             'goal_memory_source_error': error_code(memory.goal_source, root, ident)},
                            {'execution': 'SUCCEEDED', 'completion': 'NEEDS_CORRECTION', 'goal_memory_source_error': 'memory_source_changed'},
                            'Feedback propagation exists; automatic selective repair is a separate missing step')
            literal = create(root, 'literal-format', '只比较最低价格，保留报价和来源；措辞不限。')
            literal_task = approve(root, literal, 'text_equals', '最低报价为B。\n' + INPUT)
            core.run_task(literal_task)
            observe('WF-06-literal', 'Overly literal conditions reject an adequate price-only result',
                    {'completion': refresh(core, literal_task)['state'], 'actual': decode(core.tasks.actions(literal_task)[0]['result'])['text']},
                    {'completion': 'NEEDS_CORRECTION', 'actual': OUTPUT},
                    'The price-only business goal is met; the declared exact-string criterion imposes extra wording. This is criterion calibration, not a broken string comparison')
            blocked = create(root, 'optional-question', '比较价格；样式用默认即可。', questions=['可选配色尚未选择'])
            observe('WF-08', 'Flat unanswered questions block all admission',
                    {'status': goals.command(root, {'action': 'detail', 'id': blocked})['plan']['status'],
                     'approval_error': error_code(approve, root, blocked)},
                    {'status': 'NEEDS_INPUT', 'approval_error': 'conflict'},
                    'Current plan has no per-question dependency or optionality; NEEDS_INPUT fails the REVIEW-state guard before the inner plan_incomplete check')
            names = [r['name'] for r in core.db.all("SELECT name FROM sqlite_master WHERE type='table'")]
            columns = {table: [r['name'] for r in core.db.all('PRAGMA table_info(' + table + ')')]
                       for table in ('goal_plans', 'tasks', 'actions', 'task_dispatch')}
            save(out / 'schema-observation.json', {'tables': names, 'columns': columns,
                 'scope': 'selected current runtime schema; interpretation also relies on documented proposed ownership contracts'})
            calls = core.db.one('SELECT COUNT(*) AS n FROM model_calls')['n']
            save(out / 'trace.json', {'events': core.db.all('SELECT seq,task_id,kind,data,occurred FROM events ORDER BY seq'),
                  'package_id': package_id, 'model_calls': calls})
        finally:
            core.close()
    unchanged = before == snapshots()
    report = {'version': 'workflow-audit-1', 'python': platform.python_version(), 'platform': platform.platform(),
              'observations': observations, 'diagnostics_reproduced': all(r['reproduced'] for r in observations),
              'source_unchanged': unchanged, 'model_calls': calls, 'production_deployed': False,
              'full_workflow_complete': False, 'quality_gain': None,
              'interpretation': 'A reproduced limitation is a finding, not a product acceptance pass.'}
    save(out / 'report.json', report)
    print(json.dumps({'reproduced': report['diagnostics_reproduced'], 'observations': len(observations),
                      'source_unchanged': unchanged, 'full_workflow_complete': False, 'output': str(out)}))
    return 0 if report['diagnostics_reproduced'] and unchanged and calls == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
