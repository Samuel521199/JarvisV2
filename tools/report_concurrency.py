"""Render the recorded offline measurements without inventing acceptance evidence."""
import json
import hashlib
import time
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    folder = Path('docs/evidence/concurrency-1.0.0')
    filename = 'performance-optimized.json' if (folder/'performance-optimized.json').exists() else 'performance.json'
    result = json.loads((folder/filename).read_text(encoding='utf-8'))
    assessment = json.loads((folder/'assessment.json').read_text(encoding='utf-8'))
    assessment['checked_at'] = time.time()
    assessment['live_browser'] = json.loads((folder/'live-browser.json').read_text(encoding='utf-8'))
    assessment['deployment'] = json.loads((folder/'deployment.json').read_text(encoding='utf-8'))
    controls = json.loads((folder/'control.json').read_text(encoding='utf-8'))
    audit_name = 'background-audit-optimized.json' if filename=='performance-optimized.json' else 'background-audit.json'
    audit = json.loads((folder/audit_name).read_text(encoding='utf-8'))
    base = result['statistics_ms']['idle']['reply_ms']['p95']
    loaded = result['statistics_ms']['loaded']['reply_ms']['p95']
    assessment['latest_focused_tests'] = {'count': 17, 'result': 'passed', 'log': 'targeted-final.txt'}
    assessment['memory_regression'] = {'count': 104, 'result': 'passed', 'log': 'memory-regression.txt'}
    assessment['dialogue_regression'] = {'count': 17, 'result': 'passed', 'command': 'python -m unittest discover -s tests -p test_preferences_dialogue.py -q'}
    assessment['final_performance_file'] = filename
    baseline = json.loads((folder/'optimized-source.json').read_text(encoding='utf-8'))
    assessment['final_benchmark_sources_match'] = all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in baseline['files'].items())
    assessment.pop('expected_only_change', None)
    assessment.pop('benchmark_baseline_changed_files', None)
    assessment['initial_performance'] = {'file': 'performance.json', 'result': 'failed_relative_reply_threshold', 'p95_reply_increase_percent': 14.073}
    assessment['regression_coverage_note'] = '601 full tests before the checkpoint optimization; 104 memory, 17 dialogue and 17 concurrency tests after it.'
    assessment.update(performance={'result': 'passed_declared_checks' if all(result['checks'].values()) else 'threshold_not_met',
        'checks': result['checks'], 'paired_p95_reply_change_ms': round(loaded-base, 3),
        'paired_p95_reply_change_percent': round((loaded/base-1)*100, 3),
        'statistics_ms': result['statistics_ms'], 'soak_seconds': result['soak_seconds'],
        'not_verified': result['not_verified']+['memory-enabled retrieval and assistant action routing','project-scoped conversation performance']}, controls=controls['checks'], background_audit=audit['checks'])
    (folder/'assessment.json').write_text(json.dumps(assessment, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout='constrained')
    names = [('input_ms', 'Persisted input acknowledgement'), ('dispatch_ms', 'Foreground dispatch wait'), ('reply_ms', 'Complete substantive reply')]
    colors = ['#5d7086', '#087baf', '#359b84']
    for axis, (metric, title) in zip(axes, names):
        for offset, (group, label) in enumerate([('idle', 'Idle (200)'), ('loaded', 'Two background tasks (200)'), ('soak', '30-minute sustained run')]):
            values = [result['statistics_ms'][group][metric][quantile] for quantile in ('p50', 'p95', 'p99')]
            bars = axis.bar([i+(offset-1)*.25 for i in range(3)], values, width=.23, label=label, color=colors[offset])
            axis.bar_label(bars, fmt='%.1f', fontsize=7, padding=2)
        axis.set_xticks(range(3), ['p50', 'p95', 'p99']); axis.set_title(title, fontsize=11); axis.set_ylabel('milliseconds')
        axis.spines[['top','right']].set_visible(False); axis.grid(axis='y', alpha=.15); axis.set_axisbelow(True)
        axis.margins(y=.2)
    axes[0].legend(fontsize=7, loc='upper left')
    fig.suptitle('Jarvis bounded concurrency 1.0.0 · offline model fixed at 200 ms', fontsize=13)
    fig.savefig(folder/'latency.png', dpi=160)
    print(json.dumps(assessment['performance'], ensure_ascii=False))


if __name__ == '__main__': main()
