"""Offline, disposable result-observer benchmark and browser fixture."""
import argparse
import json
import platform
from pathlib import Path
import subprocess
import tempfile
import time
import sys
from types import SimpleNamespace

from host.core import Core
from host.outcomes import service
from sdk.protocol import decode
from tools.probe_concurrency import Fixture, plan, distribution


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--browser-only', action='store_true')
    parser.add_argument('--completion-ui', action='store_true')
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    budget = {'version':'outcome-observer-1.0.0', 'scope':'synthetic local text, no semantic quality claim',
              'pairs':30, 'foreground_pairs':10, 'task_p95_added_ms_max':25,
              'loaded_foreground_input_p95_ms_max':200, 'loaded_foreground_reply_added_p95_ms_max':100,
              'paid_model_calls':0, 'frozen_at':time.time()}
    budget_path = args.output/'budget.json'
    if budget_path.exists():
        budget = json.loads(budget_path.read_text(encoding='utf-8'))
    else: budget_path.write_text(json.dumps(budget,indent=2)+'\n',encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='jarvis-outcomes-probe-') as tmp:
        root = Path(tmp); fixture = Fixture(root)
        fixture.server.development_runner = SimpleNamespace(state=lambda:{'status':'idle'})
        server_errors, disconnected = [], []
        original_error = fixture.server.handle_error
        def record_error(request, address):
            exc = sys.exc_info()[1]
            if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
                disconnected.append(type(exc).__name__)
            else:
                server_errors.append(type(exc).__name__); original_error(request, address)
        fixture.server.handle_error = record_error
        try:
            core = Core(root); observer = service(core); timings = {False:[],True:[]}; raw = []
            try:
                if args.browser_only:
                    for name in (('intact',) if args.completion_ui else ('intact','missing')):
                        request=plan('outcome-ui-'+name);request['goal']='Outcome UI '+name+' artifact'
                        ident=core.tasks.submit(request);core.run_task(ident)
                        if name=='missing':
                            receipt=decode(core.tasks.actions(ident)[-1]['result']);(root/receipt['relative_path']).unlink()
                    script='probe_completion_ui.cjs' if args.completion_ui else 'probe_outcomes_ui.cjs'
                    subprocess.run(['node',str(Path(__file__).with_name(script)),fixture.base,str(args.output.resolve())],check=True,timeout=90)
                    if server_errors: raise RuntimeError('Unexpected HTTP fixture error')
                    return
                for i in range(budget['pairs']+2):
                    row = {}
                    for enabled in ([False,True] if i%2==0 else [True,False]):
                        observer.configure(enabled)
                        ident = core.tasks.submit(plan('observer-'+str(i)+'-'+str(enabled)))
                        started = time.perf_counter(); result = core.run_task(ident)
                        elapsed = (time.perf_counter()-started)*1000
                        assert result['status']=='SUCCEEDED'
                        if i>=2: timings[enabled].append(elapsed); row[str(enabled)] = elapsed
                    if i>=2: raw.append(row)
                foreground = {False:[],True:[]}
                fixture.set_load(True)
                for i in range(budget['foreground_pairs']):
                    for enabled in ([False,True] if i%2==0 else [True,False]):
                        observer.configure(enabled); foreground[enabled].append(fixture.response())
                fixture.set_load(False); observer.configure(True)
                good = plan('outcome-ui-good'); good['goal']='Outcome UI intact artifact'
                bad = plan('outcome-ui-missing'); bad['goal']='Outcome UI missing artifact'
                good_id = core.tasks.submit(good); core.run_task(good_id)
                bad_id = core.tasks.submit(bad); core.run_task(bad_id)
                receipt = decode(core.tasks.actions(bad_id)[-1]['result'])
                (root/receipt['relative_path']).unlink()
                assert observer.refresh(bad_id)['state']=='ISSUES'
                stats = {str(k):distribution(v) for k,v in timings.items()}
                front = {str(k):{field:distribution([r[field] for r in rows]) for field in ('input_ms','reply_ms','dispatch_ms')}
                         for k,rows in foreground.items()}
                checks = {'task_added_p95_budget':stats['True']['p95']-stats['False']['p95']<=budget['task_p95_added_ms_max'],
                          'foreground_input_budget':front['True']['input_ms']['p95']<=budget['loaded_foreground_input_p95_ms_max'],
                          'foreground_reply_added_budget':front['True']['reply_ms']['p95']-front['False']['reply_ms']['p95']<=budget['loaded_foreground_reply_added_p95_ms_max'],
                          'model_calls_zero':core.db.one('SELECT COUNT(*) AS n FROM model_calls')['n']==0}
                result = {'version':budget['version'],'recorded_at':time.time(),'python':platform.python_version(),
                          'platform':platform.platform(),'budget_file':'budget.json','checks':checks,'task_ms':stats,
                          'foreground_ms':front,'raw_task_pairs':raw,'raw_foreground':{str(k):v for k,v in foreground.items()},
                          'quality_score':None,'quality_prediction_delta':None,
                          'not_verified':['semantic goal scoring','full autonomous waiting/recovery','multi Bot ownership',
                                          'knowledge utility improvement','real cloud load','long soak','physical robots']}
                (args.output/'performance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                print(json.dumps({'checks':checks,'task_ms':stats,'foreground_ms':front}),flush=True)
                if args.browser:
                    subprocess.run(['node',str(Path(__file__).with_name('probe_outcomes_ui.cjs')),fixture.base,str(args.output.resolve())],check=True,timeout=90)
                result['server_errors'] = server_errors
                result['browser_navigation_disconnects'] = disconnected
                result['checks']['server_errors_zero'] = not server_errors
                (args.output/'performance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                if not all(checks.values()): raise SystemExit('Measured observer budget failed')
            finally: core.close()
        finally: fixture.close()


if __name__=='__main__': main()
