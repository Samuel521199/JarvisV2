"""Run the unchanged acceptance gates on an isolated copy during parallel work.

No production databases, credentials, user assets or Git history are copied.
The temporary candidate is discarded after the run; evidence remains at --output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
FOLDERS=('sdk','control','adapters','modules','host','apps','contracts','seed','tests','tools','docs')
EXTRAS=('AGENTS.md','README.md','StartJarvis.bat','VERSION','3DModels/AGENTS.md','3DModels/leFH18/README.txt',
        'config/memory-evaluation.json','config/model-routes.json','config/defaults.toml',
        'packaging/reference-map.json','packaging/runtime-lock.json','evals/text-analyzer.json')


def sources(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for name in FOLDERS if name!='docs' for p in sorted((root/name).rglob('*'))
            if p.is_file() and p.suffix in {'.py','.js','.cjs','.mjs','.json','.html','.css'}}


def supporting_inputs(root):
    paths=[root/name for name in EXTRAS]
    paths.extend(p for p in (root/'user-data/worker-runtime').rglob('*') if p.is_file())
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    before=sources(ROOT);support_before=supporting_inputs(ROOT)
    with tempfile.TemporaryDirectory(prefix='jarvis-frozen-acceptance-') as tmp:
        snapshot=Path(tmp).resolve()
        assert snapshot.parent==Path(tempfile.gettempdir()).resolve() and snapshot.name.startswith('jarvis-frozen-acceptance-')
        ignore=shutil.ignore_patterns('__pycache__','*.pyc','.git','node_modules')
        for name in FOLDERS:shutil.copytree(ROOT/name,snapshot/name,ignore=ignore)
        for name in EXTRAS:
            src=ROOT/name
            if not src.is_file():raise FileNotFoundError('Required acceptance input: '+name)
            dst=snapshot/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        shutil.copytree(ROOT/'user-data/worker-runtime',snapshot/'user-data/worker-runtime')
        after=sources(ROOT);copied=sources(snapshot);support_copied=supporting_inputs(snapshot)
        frozen={'scope':'Frozen local text technical acceptance; not deployment of the shared working tree',
                'source_digests':copied,'source_count':len(copied),'snapshot_directory':str(snapshot),
                'source_stable_while_copying':before==after==copied,
                'supporting_input_digests':support_copied,
                'supporting_inputs_stable_while_copying':support_before==supporting_inputs(ROOT)==support_copied,
                'excluded':['user-data except worker-runtime','.git','3DModels except AGENTS.md and leFH18/README.txt','all other config'],
                'gate_changes':False,'production_deployed':False}
        write(out/'snapshot.json',frozen)
        if not frozen['source_stable_while_copying'] or not frozen['supporting_inputs_stable_while_copying']:
            write(out/'result.json',{'local_verdict':'FAIL','reason':'source_changed_during_copy'})
            print('FAIL: source changed during copy; no tests started. Retry to a new output directory.',flush=True)
            return 1
        print('FROZEN '+str(len(copied))+' source inputs; running original gates',flush=True)
        smoke="from pathlib import Path; import tempfile; from host.core import Core\nwith tempfile.TemporaryDirectory(prefix='jarvis-frozen-smoke-') as data:\n core=Core.initialize(Path(data))\n try: core.registry.probe('text-analyzer')\n finally: core.close()\n"
        with (out/'preflight.log').open('w',encoding='utf-8') as log:
            preflight=subprocess.run([sys.executable,'-c',smoke],cwd=snapshot,timeout=60,
                stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if preflight.returncode:
            write(out/'result.json',{'local_verdict':'FAIL','reason':'frozen_core_preflight_failed'})
            print('FAIL: isolated core initialization or module self-test failed.',flush=True)
            return 1
        with (out/'documentation-preflight.log').open('w',encoding='utf-8') as log:
            docs=subprocess.run([sys.executable,'tools/check_docs.py','--root','.'],cwd=snapshot,timeout=60,
                stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if docs.returncode:
            write(out/'result.json',{'local_verdict':'FAIL','reason':'frozen_documentation_preflight_failed'})
            print('FAIL: frozen documentation dependencies or links are incomplete.',flush=True)
            return 1
        with (out/'acceptance.log').open('w',encoding='utf-8') as log:
            completed=subprocess.run([sys.executable,'-m','tools.accept_completion','--browser','--output',str(out/'run')],
                cwd=snapshot,timeout=1800,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        current=sources(ROOT)
        changed=sorted(n for n in current.keys()|copied.keys() if current.get(n)!=copied.get(n))
        support_now=supporting_inputs(ROOT)
        support_changed=sorted(n for n in support_now.keys()|support_copied.keys() if support_now.get(n)!=support_copied.get(n))
        report=json.loads((out/'run/report.json').read_text('utf-8'))
        supporting_unchanged=supporting_inputs(snapshot)==support_copied
        verdict=report['local_verdict'] if supporting_unchanged else 'FAIL'
        write(out/'result.json',{'local_verdict':verdict,'returncode':completed.returncode,
              'frozen_source_unchanged':report['source_unchanged'],'shared_workspace_changed_sources':changed,
              'frozen_supporting_inputs_unchanged':supporting_unchanged,
              'shared_workspace_changed_supporting_inputs':support_changed,
              'shared_workspace_is_frozen_version':not changed and not support_changed,'production_deployed':False,
              'full_product_verdict':'NOT_ACCEPTED','report':'run/report.html'})
        print(verdict+': '+str(out/'result.json'),flush=True)
        return completed.returncode if supporting_unchanged else 1


if __name__=='__main__':raise SystemExit(main())
