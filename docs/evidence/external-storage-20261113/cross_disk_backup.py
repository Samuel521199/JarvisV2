"""Explicit stopped cross-disk snapshot and inert restore rehearsal; no task replay."""
from pathlib import Path
import json,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
from host.development_runtime import start as start_dev,stop as stop_dev
from control.paths import reject_links
from tools import workstation
from tools.migrate_codex_home import independent_disks
from tools.recovery_snapshot import snapshot,restore


def main():
    if ROOT!=Path('E:/Jarvis/dev').resolve():raise RuntimeError('Use the canonical E source')
    private=Path(sys.argv[1]).resolve();private.mkdir(parents=True,exist_ok=False)
    entrypoints=private/'operator-root';entrypoints.mkdir()
    for path in Path('E:/Jarvis').iterdir():
        if path.is_file():reject_links(path);shutil.copy2(path,entrypoints/path.name)
    destination=Path('D:/Jarvis-Recovery/jarvis/2026-11-14-r1/snapshot')
    rehearsal=Path('E:/Jarvis/validation/restore-from-D-20261114-r1')
    if destination.exists() or rehearsal.exists():raise FileExistsError('Keep previous recovery evidence; do not overwrite')
    daily=Path('E:/Jarvis/runtime/user-data');dev=ROOT/'user-data';before=workstation.state(daily)
    report={'started':time.time(),'disks':independent_disks(),'source_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
        'daily_before':before,'excluded_active_Codex_home':'C:/Users/samuel/.codex; offline copy required',
        'roots':{'installation':'E:/Jarvis/runtime','development':'E:/Jarvis/dev','models':'E:/Jarvis/models','projects':'E:/Jarvis/projects','operator':str(entrypoints)},
        'daily_adopted':False,'restored_tasks_started':False}
    def save():
        destination.parent.mkdir(parents=True,exist_ok=True)
        (destination.parent/'progress.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (private/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    daily_online=bool(workstation.instance(18282));dev_online=bool(workstation.instance(18283))
    dev_stopped=daily_stopped=False
    try:
        if dev_online:stop_dev(dev,18283);dev_stopped=True
        if daily_online:
            workstation.conditional_stop(daily,before['epoch'],before['active']['build']);daily_stopped=True
        report.update(daily_stop_confirmed=daily_stopped,development_stop_confirmed=dev_stopped);save()
        print('Managed services quiesced; capturing D recovery point',flush=True)
        if any((ROOT/'.git'/name).exists() for name in ['index.lock','packed-refs.lock','HEAD.lock']):raise RuntimeError('Git writer is active; keep sources')
        report['snapshot']=snapshot({k:Path(v) for k,v in report['roots'].items()},destination,managed_root=daily,
            missing_projects=['SilverHairCharacter','PaK38'],additional_managed_roots=[dev])
        save();print(json.dumps({'snapshot_complete':True,**report['snapshot']}),flush=True)
    except BaseException as error:
        report['capture_error']=type(error).__name__+': '+str(error);save();raise
    finally:
        # Restart only services whose normal stop was confirmed above. Never
        # infer a terminal process merely from an HTTP timeout.
        for name,stopped,start in [('daily',daily_stopped,lambda:workstation.start_daily(daily)),
                                   ('development',dev_stopped,lambda:start_dev(dev,daily,18283))]:
            if stopped:
                try:report[name+'_restart']=start()
                except Exception as error:report[name+'_restart_error']=type(error).__name__+': '+str(error)
        save()
    if any(k.endswith('_restart_error') for k in report):raise RuntimeError('Service restart requires reconciliation; original data retained')
    report['restore']=restore(destination,rehearsal);report['daily_after']=workstation.state(daily)
    report['daily_online_after']=bool(workstation.instance(18282));report['development_online_after']=bool(workstation.instance(18283))
    report['passed']=report['restore']['byte_exact'] and not report['restore']['work_started'] and report['daily_online_after'] and report['development_online_after']
    save();destination.parent.joinpath('verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'restored_files':report['restore']['files'],'restored_sqlite':report['restore']['sqlite_integrity_ok'],
        'daily_epoch':report['daily_after']['epoch'],'restored_tasks_started':False}),flush=True)
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
