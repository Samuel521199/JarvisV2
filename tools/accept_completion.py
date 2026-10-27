"""Reproducible, fail-closed acceptance of the implemented local text loop.

python -m tools.accept_completion --browser
Every run freezes its inputs and keeps separate evidence. It never launches the
production data root, restarts a live service, installs dependencies or publishes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
MODULES = ['test_core', 'test_outcomes', 'test_completion_loop', 'test_completion_acceptance',
           'test_concurrency', 'test_assistant_goals', 'test_goal_plans', 'test_workbench', 'test_memory_retrieval',
           'test_workflow_handoff', 'test_work_revisions', 'test_work_budgets', 'test_workflow_closure',
           'test_goal_growth', 'test_memory_development_ui', 'test_session_folders', 'test_memory_domains',
           'test_acceptance_collection', 'test_architecture_boundaries', 'test_quote_acceptance', 'test_quote_requests', 'test_quote_sources', 'test_quote_changes', 'test_quote_rework', 'test_work_recovery', 'test_work_trials', 'test_personal_workflows', 'test_body_evidence', 'test_delivery_shadow']
PENDING = [
    ('生产版本', '本轮只启动临时测试实例；实际服务加载版本及真实数据迁移仍需另行核对。'),
    ('真实工作收益', '尚无匹配旧版与候选版的真实任务对照；质量、人工介入、成本与 JPF 差距仍未测。'),
    ('通用多 Bot', '关联工作的工具动作额度已接通；负责人任期、委派、接管和完整费用预算仍未实现，不能借用线程并发测试签收。'),
    ('通用自愈与自改造', '模块恢复接续不代表自动诊断修码；通用候选发布、恢复和累计非退化仍需验收。'),
    ('长期成长与陪伴', '需要真实使用反馈、延迟复测、跨任务迁移和错误复发记录；加速时钟不能替代长期效果。'),
    ('多机器人', '需要设备、控制适配器及真实停止/断连证据；仿真通过不等于物理验收。')
]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def source_snapshot():
    paths = []
    for folder in ('sdk', 'control', 'adapters', 'modules', 'host', 'apps', 'contracts', 'seed', 'tests', 'tools'):
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and p.suffix in {'.py', '.js', '.cjs', '.mjs', '.json', '.html', '.css'})
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def unique_suite(tests):
    """Imported helper TestCases can be discovered repeatedly: run every ID once."""
    result=unittest.TestSuite();seen={};duplicates=[]
    def visit(items):
        for test in items:
            if isinstance(test,unittest.TestSuite):visit(test);continue
            ident=test.id()
            if ident in seen:
                if type(seen[ident]) is not type(test):
                    raise ValueError('Different test classes share ID: '+ident)
                duplicates.append(ident)
            else:seen[ident]=test;result.addTest(test)
    visit(tests)
    return result,duplicates


def collection():
    loader = unittest.TestLoader()
    result = unittest.TestSuite()
    for module in MODULES:
        result.addTests(loader.discover(str(ROOT / 'tests'), pattern=module + '.py'))
    return unique_suite(result)


def suite():return collection()[0]


def test_ids(tests):
    result = []
    for test in tests:
        result.extend(test_ids(test) if isinstance(test, unittest.TestSuite) else [test.id()])
    return sorted(result)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = {}

    def startTest(self, test):
        self.records[test.id()] = {'id': test.id(), 'status': 'RUNNING', 'started': time.monotonic()}
        super().startTest(test)

    def stopTest(self, test):
        record = self.records[test.id()]
        record['seconds'] = round(time.monotonic() - record.pop('started'), 4)
        super().stopTest(test)

    def addSuccess(self, test):
        self.records[test.id()]['status'] = 'PASS'
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.records[test.id()]['status'] = 'FAIL'
        super().addFailure(test, err)

    def addError(self, test, err):
        self.records[test.id()]['status'] = 'ERROR'
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.records[test.id()].update(status='SKIPPED', reason=reason)
        super().addSkip(test, reason)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.records[test.id()]['status'] = 'FAIL'
        super().addSubTest(test, subtest, err)

    def addExpectedFailure(self, test, err):
        self.records[test.id()]['status'] = 'EXPECTED_FAILURE'
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.records[test.id()]['status'] = 'UNEXPECTED_SUCCESS'
        super().addUnexpectedSuccess(test)


def test_worker(path):
    start = time.monotonic()
    tests,duplicates=collection();frozen=test_ids(tests)
    result = unittest.TextTestRunner(verbosity=1, resultclass=RecordedResult).run(tests)
    passed = bool(result.records) and all(r['status'] == 'PASS' for r in result.records.values())
    passed = (passed and result.wasSuccessful() and not result.skipped
              and sorted(result.records)==frozen and result.testsRun==len(frozen))
    report = {'passed': passed, 'run': result.testsRun, 'failures': len(result.failures),
              'errors': len(result.errors), 'skipped': len(result.skipped),
              'frozen_test_ids':frozen,'deduplicated_imported_occurrences':duplicates,
              'seconds': round(time.monotonic() - start, 3), 'cases': list(result.records.values()),
              'failure_details': [{'id': t.id(), 'trace': text} for t, text in result.failures + result.errors]}
    write_json(path, report)
    return 0 if passed else 1


def run_step(out, name, command, timeout=180):
    start = time.monotonic()
    print('RUN ' + name, flush=True)
    result = {'id': name, 'status': 'FAIL', 'command': command, 'log': name + '.log'}
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    try:
        process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=timeout,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        result.update(returncode=process.returncode, status='PASS' if process.returncode == 0 else 'FAIL')
        log = process.stdout + '\n' + process.stderr
    except subprocess.TimeoutExpired as exc:
        result['reason'] = 'timeout'
        log = str(exc) + '\n' + str(exc.stdout or '') + '\n' + str(exc.stderr or '')
    except OSError as exc:
        result['reason'] = type(exc).__name__
        log = str(exc)
    (out / result['log']).write_text(log, encoding='utf-8')
    result['seconds'] = round(time.monotonic() - start, 3)
    print(result['status'] + ' ' + name, flush=True)
    return result


def document(out, report):
    esc = html.escape
    tests=json.loads((out/'tests.json').read_text('utf-8')) if (out/'tests.json').exists() else {}
    pairs=json.loads((out/'paired/results.json').read_text('utf-8')) if (out/'paired/results.json').exists() else {}
    passed_checks=sum(c['status']=='PASS' for c in report['checks'])
    evidence_links=' · '.join(f'<a href="{name}">{label}</a>' for name,label in
        [('closure/browser.json','当前版本与原会话界面证据'),('paired/results.json','六组策略对照'),
         ('performance.json','原观察器开销')] if (out/name).is_file())
    metrics=f'<div class="metrics"><div><b>{report.get("tests_run") or 0}</b><br>不同回归用例</div><div><b>{passed_checks}/{len(report["checks"])}</b><br>联合验收条件通过</div><div><b>{len(pairs.get("pairs",[])) if isinstance(pairs.get("pairs"),list) else pairs.get("pairs",0)}</b><br>合成配对任务</div><div><b>未测</b><br>综合质量与长期成长收益</div></div>'
    rows = ''.join('<tr><td>' + esc(r['id']) + '</td><td class="' + r['status'].lower() + '">' +
                   r['status'] + '</td><td>' + (f'<a href="{esc(r["log"])}">日志</a>' if r.get('log') else esc(r.get('reason', ''))) +
                   '</td></tr>' for r in report['checks'])
    pending = ''.join('<li><strong>' + esc(k) + '</strong>：' + esc(v) + '</li>' for k, v in PENDING)
    title = {'PASS': '本地文本技术验收通过', 'FAIL': '本地文本技术验收未通过', 'INCOMPLETE': '本地文本技术验收不完整'}[report['local_verdict']]
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Jarvis 验收记录</title><style>body{{font:16px/1.65 system-ui;margin:40px auto;max-width:1000px;padding:0 24px;color:#1b3044;background:#f4f7fa}}h1{{line-height:1.3}}.card{{padding:20px;background:white;border:1px solid #ccd8e2;border-radius:10px;margin:20px 0}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #dce4eb}}.pass{{color:#167147}}.fail{{color:#b52c2c}}.incomplete{{color:#8b6100}}a{{color:#145e99}}li{{margin:12px 0}}code{{overflow-wrap:anywhere}}.metrics,.flow{{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0}}.metrics>div,.flow>span{{flex:1 1 160px;padding:16px;border:1px solid #ccd8e2;border-radius:8px;background:white}}.metrics b{{font-size:30px;color:#145e99}}.flow>span{{background:#e8f1f8}}@media(max-width:650px){{body{{padding:0 12px}}td{{overflow-wrap:anywhere}}}}</style>
<h1>{title}</h1><p>范围：本地纯文本交接、返工、共享额度、当前版结案、条件方法与恢复接续。<strong>完整 Jarvis 产品尚未验收，生产未部署。</strong></p>
{metrics}
<div class="card"><h2>这轮补齐了哪些连接</h2><div class="flow"><span>① 修改整份计划<br>分析最早变化处</span><span>② 核对前段依据<br>生成关联草稿</span><span>③ 原许可与共享额度<br>执行受影响后段</span><span>④ 核验当前版本<br>聊天与工作台一致</span><span>⑤ 迟到纠正或反证<br>重新打开并回到修改</span></div><p>原始输入或目标改变时从头重做；结构相同且证据有效才复用。分析和经验都不能授予执行权限。100% 条件检查不能替代缺少证据的综合质量分。</p></div>
<div class="card"><strong>运行编号：</strong><code>{esc(report['run_id'])}</code><br>UTC：{esc(report['created_at'])}<br>环境：{esc(report['platform'])} / Python {esc(report['python'])}<br>源码保持不变：{report['source_unchanged']}<br>质量提升、token 收益与长期成长：未测，不能以测试通过率代替。</div>
<div class="card"><h2>硬条件逐项判断</h2><table><tr><th>检查</th><th>结果</th><th>证据</th></tr>{rows}</table></div>
<div class="card"><h2>当前不能签收的范围</h2><ul>{pending}</ul></div>
<p>{evidence_links}</p>
<p><a href="report.json">完整机器记录</a> · <a href="plan.json">运行前冻结计划</a> · <a href="tests.json">逐项测试</a> · <a href="real-task-trial-template.json">待填写的真实任务试验模板</a></p></html>'''
    (out / 'report.html').write_text(page, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='A new directory; existing runs are never overwritten')
    parser.add_argument('--browser', action='store_true', help='Require existing Node/Playwright/Edge; no install')
    parser.add_argument('--test-report', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.test_report:
        return test_worker(args.test_report)
    created = datetime.now(timezone.utc).isoformat()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    out = (args.output or ROOT / 'docs/evidence/completion-acceptance-v1' / run_id).resolve()
    out.mkdir(parents=True, exist_ok=False)
    before = source_snapshot()
    frozen_tests = test_ids(suite())
    plan = {'version': 'completion-acceptance-v1', 'run_id': run_id, 'created_at': created,
            'workflow_revision':'workflow-shadow-1.13.0',
            'scope': 'local text loop technical acceptance only', 'test_ids': frozen_tests, 'source_digests': before,
            'gates': ['every frozen test passes; no skip or missing test', 'source unchanged during run',
                      'architecture and documents pass', 'frozen observer budgets pass', 'all thirteen browser workflows pass'],
            'browser_requested': args.browser, 'production_deployed': False, 'product_acceptance': 'NOT_ACCEPTED'}
    write_json(out / 'plan.json', plan)
    budget = json.loads((ROOT / 'docs/evidence/completion-loop-1.0.0/budget.json').read_text('utf-8'))
    write_json(out / 'budget.json', budget)
    write_json(out / 'real-task-trial-template.json', {
        'status': 'DRAFT_NOT_RUN', 'protocol': 'docs/delivery-validation.md#forecast-experiment-freeze',
        'rubric': 'docs/delivery-validation.md#task-score-rubric', 'baseline_version': None, 'candidate_version': None,
        'task_set_digest': None, 'rubric_version': None, 'predeclared_thresholds': None, 'fixed_reference_version': None,
        'trials': [], 'required_trial_fields': ['task_id', 'requirements_digest', 'configuration', 'input_digest',
        'output_digest', 'model_tool_knowledge_versions', 'hard_conditions', 'dimension_scores', 'Q', 'duration',
        'all_tokens_and_costs', 'avoidable_interventions', 'required_decisions', 'failure_and_unknown',
        'knowledge_actually_used', 'late_feedback', 'evidence_links'], 'quality_gain': None, 'prediction_delta': None})
    checks = [run_step(out, 'regression', [sys.executable, '-m', 'tools.accept_completion', '--test-report', str(out / 'tests.json')], 900)]
    test_report = json.loads((out / 'tests.json').read_text('utf-8')) if (out / 'tests.json').exists() else {}
    complete = (test_report.get('passed') is True and sorted(r['id'] for r in test_report.get('cases', [])) == frozen_tests
                and len(frozen_tests) == len(set(frozen_tests)) > 0)
    checks.append({'id': 'frozen_test_set', 'status': 'PASS' if complete else 'FAIL', 'reason': 'No missing, skipped or substituted tests'})
    checks.append(run_step(out, 'architecture', [sys.executable, 'tools/check_architecture.py']))
    checks.append(run_step(out, 'documentation', [sys.executable, 'tools/check_docs.py', '--root', '.']))
    checks.append(run_step(out, 'paired_rework_tasks', [sys.executable,'-m','tools.probe_work_budget','--output',str(out/'paired')],240))
    perf = [sys.executable, '-m', 'tools.probe_outcomes', '--output', str(out)]
    checks.append(run_step(out, 'performance_and_observer_ui' if args.browser else 'performance', perf + (['--browser'] if args.browser else [])))
    if args.browser:
        checks.append(run_step(out, 'completion_ui', perf + ['--browser-only', '--completion-ui']))
        for name in ('browser.json', 'completion-browser.json'):
            data = json.loads((out / name).read_text('utf-8')) if (out / name).exists() else {}
            checks.append({'id': name, 'status': 'PASS' if data.get('passed') is True and data.get('errors') == [] else 'FAIL'})
        for name,module,flags in [('handoff','probe_handoff_ui',[]),('rework','probe_rework_ui',[]),
                                  ('budget','probe_rework_ui',['--budget']),('closure','probe_rework_ui',['--closure']),('quote','probe_quote_ui',[]),
                                  ('quote_request','probe_quote_ui',['--requests']),('quote_sources','probe_quote_ui',['--sources']),('quote_changes','probe_quote_ui',['--changes']),('quote_rework','probe_quote_ui',['--inheritance']),('recovery','probe_quote_ui',['--recovery']),('delivery_shadow','probe_delivery_shadow_ui',[])]:
            checks.append(run_step(out,name+'_ui',[sys.executable,'-m','tools.'+module,'--output',str(out/name),*flags],180))
            path=out/name/'browser.json'
            data=json.loads(path.read_text('utf-8')) if path.exists() else {}
            checks.append({'id':name+'_browser_evidence','status':'PASS' if data.get('passed') is True and data.get('errors')==[] else 'FAIL'})
    else:
        checks.append({'id': 'browser_workflows', 'status': 'INCOMPLETE', 'reason': 'Re-run with --browser to inspect actual UI workflows'})
    after = source_snapshot()
    unchanged = before == after
    checks.append({'id': 'source_unchanged', 'status': 'PASS' if unchanged else 'FAIL'})
    verdict = 'FAIL' if any(c['status'] == 'FAIL' for c in checks) else 'INCOMPLETE' if any(c['status'] != 'PASS' for c in checks) else 'PASS'
    report = {'version': plan['version'], 'run_id': run_id, 'created_at': created,
              'plan_sha256': hashlib.sha256((out / 'plan.json').read_bytes()).hexdigest(),
              'platform': platform.platform(), 'python': platform.python_version(), 'source_unchanged': unchanged,
              'changed_sources': sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p)),
              'checks': checks, 'tests_run': test_report.get('run'), 'local_verdict': verdict,
              'full_product_verdict': 'NOT_ACCEPTED', 'pending': dict(PENDING), 'quality_score': None,
              'learning_gain': None, 'production_deployed': False}
    write_json(out / 'report.json', report)
    document(out, report)
    print(json.dumps({'local_verdict': verdict, 'full_product_verdict': 'NOT_ACCEPTED', 'report': str(out / 'report.html')}, ensure_ascii=False))
    return {'PASS': 0, 'FAIL': 1, 'INCOMPLETE': 2}[verdict]


if __name__ == '__main__':
    raise SystemExit(main())
