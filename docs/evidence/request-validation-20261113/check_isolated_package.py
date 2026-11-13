"""Use the preinstalled controller on a new empty ledger; never prepare/adopt daily."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time

ROOT=Path(__file__).resolve().parents[3]


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    output=Path(sys.argv[1]).resolve();work=Path(sys.argv[2]).resolve()
    output.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    daily=Path('E:/Jarvis/runtime/user-data');meta=json.loads((daily/'deployment/launcher.json').read_text(encoding='utf-8'))
    controller=Path(meta['controller']).resolve()
    if controller.parent!=daily/'deployment/controllers':raise RuntimeError('Unexpected controller scope')
    inventory=controller/'controller-files.json'
    if sha(inventory)!=meta['controller_inventory_sha256']:raise RuntimeError('Controller inventory changed')
    entries=json.loads(inventory.read_text(encoding='utf-8'))
    for name,digest in entries.items():
        path=(controller/name).resolve()
        if not path.is_relative_to(controller) or sha(path)!=digest:raise RuntimeError('Controller bytes changed')
    environment=os.environ.copy();temporary=work/'temp';temporary.mkdir();environment.update(TEMP=str(temporary),TMP=str(temporary))
    archive=work/'candidate.zip';data=work/'data';data.mkdir()
    # RunLock and the application ledger assume an initialized Jarvis data root.
    # Initialize with the already verified old controller, not candidate code.
    initialize='import sys;sys.path.insert(0,'+repr(str(controller))+');from host.core import Core;Core.initialize('+repr(str(data))+').close()'
    initialized=subprocess.run([sys.executable,'-I','-B','-c',initialize],env=environment,capture_output=True,text=True,encoding='utf-8',timeout=60)
    (output/'initialize.txt').write_text(initialized.stdout+initialized.stderr,encoding='utf-8')
    if initialized.returncode:raise RuntimeError('Frozen-controller fixture initialization failed')
    report={'controller_build':meta['build'],'controller_files_verified':len(entries),
        'source_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
        'isolated_data':str(data),'initialized_with_frozen_controller':True,
        'production_adopted':False,'daily_ready_record_created':False,'steps':[]}
    def save():
        (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def run(action,*args):
        command=[sys.executable,'-X','utf8','-I','-B',str(controller/'apps/development/releases.py'),action,'--data-root',str(data),*map(str,args)]
        started=time.monotonic();result=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True,encoding='utf-8',timeout=240)
        (output/(action+'.txt')).write_text(result.stdout+result.stderr,encoding='utf-8')
        try:value=json.loads(result.stdout)
        except ValueError:value=None
        report['steps'].append({'action':action,'exit_code':result.returncode,'seconds':round(time.monotonic()-started,3),'result':value});save()
        print(json.dumps({'action':action,'exit_code':result.returncode,'seconds':report['steps'][-1]['seconds']}),flush=True)
        if result.returncode:raise SystemExit(result.returncode)
        return value
    built=run('build','--source',ROOT,'--archive',archive,'--version',(ROOT/'VERSION').read_text(encoding='utf-8').strip())
    run('stage','--archive',archive);validated=run('validate','--build',built['build'],'--reviewed-source')
    report['passed']=bool(validated.get('approval'));report['build']=built['build'];save()
    print(json.dumps({'passed':report['passed'],'build':report['build'],'production_adopted':False,'daily_ready_record_created':False}),flush=True)
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
