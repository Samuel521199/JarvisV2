"""Offline control-latency check with real HTTP and two background jobs."""
import json
from pathlib import Path
import tempfile
import time

from host.core import Core
from tools.probe_concurrency import Fixture, plan, distribution


def main():
    with tempfile.TemporaryDirectory(prefix='jarvis-control-probe-') as temp:
        fixture = Fixture(Path(temp))
        try:
            fixture.set_load(True)
            core = Core(fixture.root)
            try:
                ident = core.tasks.submit(plan('control-only'))
                core.tasks.state(ident, 'WAITING')
            finally: core.close()
            samples = []
            revision = 0
            for number in range(200):
                start = time.monotonic()
                result = fixture.call('/api/scheduler/priority', {'id': ident, 'revision': revision,
                    'priority': number % 4, 'importance': 2, 'due_at': None, 'reason': 'Offline explicit command'})
                samples.append((time.monotonic()-start)*1000)
                revision = result['revision']
            active = fixture.runner.state()['active']
            if not active: raise RuntimeError('Background did not remain active')
            target = active[0]; start = time.monotonic()
            fixture.call('/api/operations', {'action': 'task_cancel', 'id': target})
            cancel_ack = (time.monotonic()-start)*1000
            core = Core(fixture.root)
            try:
                while time.monotonic()-start < 5:
                    row = core.tasks.get(target)
                    if row['status'] not in {'READY', 'RUNNING'}: break
                    time.sleep(.005)
                cancelled = row['cancel'] == 1 and row['status'] in {'CANCELLED', 'WAITING'}
                cancel_checkpoint = (time.monotonic()-start)*1000
            finally: core.close()
            before = fixture.completed
            end = time.monotonic()+3
            while fixture.completed <= before and time.monotonic() < end: time.sleep(.01)
            stats = distribution(samples)
            report = {'version': 'bounded-concurrency-1.0.0', 'paid_model_calls': 0,
                'scope': 'explicit priority HTTP commands under bounded deterministic task load; one selected cancellation',
                'priority_ms': stats, 'priority_raw_ms': samples, 'cancel_ack_ms': cancel_ack,
                'cancel_checkpoint_ms': cancel_checkpoint, 'max_overlap': fixture.max_overlap,
                'checks': {'200_commands': len(samples) == 200, 'p95_le_200ms': stats['p95'] <= 200,
                    'p99_le_500ms': stats['p99'] <= 500, 'selected_cancel_recorded': cancelled,
                    'other_work_continues': fixture.completed > before, 'two_steps_overlap': fixture.max_overlap >= 2},
                'not_verified': ['natural-language command recognition', 'remote cancellation latency', 'arbitrary non-preemptible tool']}
            Path('docs/evidence/concurrency-1.0.0/control.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
            print(json.dumps({k: v for k, v in report.items() if k != 'priority_raw_ms'}))
        finally: fixture.close()


if __name__ == '__main__': main()
