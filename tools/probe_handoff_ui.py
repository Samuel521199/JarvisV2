"""Real goal components and HTTP admission on disposable, model-free fixture data."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from host.core import Core
from tools.probe_concurrency import Fixture
from tools.probe_workflow_audit import publish, create


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='jarvis-handoff-ui-') as tmp:
        root=Path(tmp);fixture=Fixture(root)
        fixture.server.development_runner=SimpleNamespace(state=lambda:{'status':'idle'})
        try:
            shutil.copytree(Path(__file__).resolve().parents[1]/'user-data/worker-runtime',root/'worker-runtime')
            core=Core(root)
            try:
                publish(core)
                ids=[create(root,'ui-'+str(i),'比较报价，预算最多100且交付不超过5天；保留来源。') for i in range(2)]
                (out/'fixture.json').write_text(json.dumps({'ids':ids,'settings':core.preferences.public(core.credentials.available)},ensure_ascii=False),encoding='utf-8')
                subprocess.run(['node',str(Path(__file__).with_name('probe_handoff_ui.cjs')),fixture.base,str(out)],check=True,timeout=90)
                calls=core.db.one('SELECT COUNT(*) AS n FROM model_calls')['n']
                (out/'runtime.json').write_text(json.dumps({'model_calls':calls,'task_count':core.db.one('SELECT COUNT(*) AS n FROM tasks')['n'],
                    'production_deployed':False,'scope':'real goal components and HTTP/scheduler on synthetic inputs'},indent=2),encoding='utf-8')
                if calls:raise RuntimeError('Unexpected model call')
            finally:core.close()
        finally:fixture.close()


if __name__=='__main__':main()
