"""Owner-reviewed controller promotion without application adoption or data restore.

The existing installed controller must independently validate the runtime first.
Its checker, baseline, test inventory and test bytes remain the policy anchor.
The atomic JarvisLaunch.py replacement is authoritative; launcher.json is a cache.
"""
import ast
import hashlib
import os
from pathlib import Path
import re
import shutil
import uuid
import zipfile

from control import controller_pin as pin
from control.application_compatibility import require_compatible
from control.application_runtime import LocalApprovals
from control.atomic import write_json
from control.paths import reject_links
from control.recovery.gate import RunLock
from modules.release_recovery.application import Applications,inspect_package
from sdk.controller_bootstrap import modern,embedded
from sdk.protocol import CoreError,canonical,digest,read_json


def policy(root,record):
    pin.verify(root,record);folder=Path(record['controller'])
    tree=ast.parse((folder/'sdk/application_policy.py').read_text(encoding='utf-8'));values={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in {'TESTS','TEST_SUPPORT'}:values[target.id]=ast.literal_eval(node.value)
    if set(values)!={'TESTS','TEST_SUPPORT'} or any(not isinstance(v,list) for v in values.values()):
        raise CoreError('controller_policy','Cannot read the pinned test inventory')
    names=values['TESTS']+values['TEST_SUPPORT']
    if len(names)!=len(set(names)) or any(not isinstance(n,str) or not re.fullmatch(r'[a-zA-Z0-9_]+\.py',n) for n in names):
        raise CoreError('controller_policy','Invalid pinned test files')
    files={n:(folder/n).read_bytes() for n in ['sdk/application_policy.py','tools/check_architecture.py','tools/architecture-baseline.json',*('tests/'+n for n in names)]}
    fingerprint=hashlib.sha256(files['tools/check_architecture.py']+files['tools/architecture-baseline.json']+b''.join(files['tests/'+n] for n in names)).hexdigest()
    return files,fingerprint


def baseline(app,expected_epoch,expected_build):
    state=app.state()
    if (state['phase'] not in {'active','stopped','blocked'} or state['epoch']!=expected_epoch
        or not state['active'] or state['active']['build']!=expected_build):
        raise CoreError('controller_baseline','Application baseline changed; no controller pointer was replaced')
    return state


def save_root(root,record):
    path=root.parent/'JarvisLaunch.py';reject_links(path)
    pending=path.with_name(path.name+'.'+uuid.uuid4().hex+'.pending');reject_links(pending)
    with pending.open('xb') as stream:stream.write(modern(record));stream.flush();os.fsync(stream.fileno())
    os.replace(pending,path)  # Commit point. Never restore an older pointer after this.


def finish(root,record,event):
    errors=[]
    for path,value in [(root/'deployment/controller-protocol.json',{'schema':1,'minimum':record['controller_protocol']}),
                       (root/'deployment/launcher.json',record),(event,{'phase':'committed','record':record})]:
        try:
            if path.name=='controller-protocol.json' and path.exists():
                current=read_json(path)
                if (not isinstance(current,dict) or set(current)!={'schema','minimum'} or current.get('schema')!=1
                    or any(type(v) is not int for v in current.values()) or current['minimum'] not in (1,pin.PROTOCOL)
                    or current['minimum']>value['minimum']):
                    raise CoreError('controller_protocol','Never lower an existing or unknown controller protocol fence')
            write_json(path,value)
        except (OSError,CoreError):errors.append(path.name)
    return {'committed':True,'registration_pending':errors,'record':record,'application_adopted':False}


def backup(root,folder):
    folder.mkdir(parents=True,exist_ok=False)
    for path in [root.parent/'JarvisLaunch.py',root.parent/'StartJarvis.bat',root/'deployment/launcher.json']:
        reject_links(path)
        if path.exists():shutil.copy2(path,folder/path.name)


def publish_files(root,files,*,suffix=''):
    index=canonical({name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(files.items())}).encode()
    ident=hashlib.sha256(index).hexdigest();base=root/'deployment/controllers';reject_links(base)
    folder=base/(ident+suffix);reject_links(folder)
    if folder.exists():
        pin.inventory(root,{'controller':str(folder),'controller_inventory_sha256':ident})
        return ident,folder,index
    pending=base/(ident+'.pending-'+uuid.uuid4().hex);pending.mkdir()
    for name,raw in files.items():
        pin.relative(name);target=pending/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    (pending/'controller-files.json').write_bytes(index);pending.rename(folder)
    pin.inventory(root,{'controller':str(folder),'controller_inventory_sha256':ident})
    return ident,folder,index


def promote(root,build,*,expected_epoch,expected_build,expected_controller,reviewed_source=False):
    if not reviewed_source:raise CoreError('controller_review','Controller promotion requires reviewed first-party source')
    root=Path(root).resolve();reject_links(root)
    with RunLock(root,'application-release'):
        app=Applications(root);before=baseline(app,expected_epoch,expected_build);old=pin.read(root)
        if digest(old)!=expected_controller:raise CoreError('controller_baseline','Controller baseline changed')
        approved=app.approved(build);report=approved['approval']['receipt']['report']
        if any(report.get(k) is not True for k in ['passed','reviewed_source','architecture_passed','tests_passed','runtime_intact']):
            raise CoreError('controller_approval','Independent reviewed-source runtime validation is required')
        overlay,fingerprint=policy(root,old)
        if report.get('policy_sha256')!=fingerprint:
            raise CoreError('controller_policy','Candidate was not checked by the current pinned policy')
        package=Path(approved['path']);actual,manifest=inspect_package(package)
        if actual!=build:raise CoreError('controller_approval','Approved package changed')
        marker=read_json(package/'config/controller-compatibility.json')
        if marker!={'schema':1,'controller_protocol':pin.PROTOCOL} or any(type(v) is not int for v in marker.values()):
            raise CoreError('controller_protocol','Candidate does not declare the independent-controller protocol')
        # Both the controller and current application must handle current data.
        require_compatible(root,package);require_compatible(root,app.approved(expected_build,fresh=False)['path'])
        files={name:(package/name).read_bytes() for name in manifest['files']};files.update(overlay)
        ident,folder,index=publish_files(root,files)
        change=root/'deployment/controller-changes'/uuid.uuid4().hex;backup(root,change)
        archive=change/'controller.zip'
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as stream:
            stream.writestr('controller-files.json',index)
            for name,raw in sorted(files.items()):stream.writestr(name,raw)
        record={'schema':2,'controller_protocol':pin.PROTOCOL,'build':ident,'runtime_source_build':build,'controller':str(folder),
            'controller_inventory_sha256':ident,'data_root':str(root),'port':old['port'],'generation':old.get('generation',0)+1,
            'policy_anchor_build':old.get('policy_anchor_build',old['build']),'policy_sha256':fingerprint,
            'capsule_id':change.name,'recovery_archive':str(archive),'recovery_sha256':pin.sha(archive),'launcher_backup':str(change)}
        record['signature']=LocalApprovals(root).sign(record)
        pin.verify(root,record)
        write_json(change/'event.json',{'phase':'prepared','previous_controller':old,'record':record,'application_state':before})
        # The shared lifecycle lock does not exclude accidental source edits.
        if app.state()!=before or digest(pin.read(root))!=expected_controller or inspect_package(package)[0]!=build:
            raise CoreError('controller_baseline','Baseline or candidate changed before commit')
        require_compatible(root,folder);require_compatible(root,app.approved(expected_build,fresh=False)['path'])
        save_root(root,record)
        result=finish(root,record,change/'event.json')
        if app.state()!=before:raise CoreError('controller_state','Application state changed during controller-only promotion')
        return result


def repair(root,*,expected_controller):
    """Repair derivative registration after a committed atomic launcher switch."""
    root=Path(root).resolve()
    with RunLock(root,'application-release'):
        record=pin.read(root)
        if record['schema']!=2 or record['build']!=expected_controller:
            raise CoreError('controller_baseline','Controller changed before registration repair')
        event=Path(record['launcher_backup'])/'registration-repair.json'
        return finish(root,record,event)


def recover(root,*,expected_controller,expected_epoch,expected_build,archive=None,activation=None):
    """Recover the same qualified controller into a fresh directory; never old data."""
    root=Path(root).resolve();reject_links(root)
    with RunLock(root,'application-release'):
        app=Applications(root);before=baseline(app,expected_epoch,expected_build)
        path=root.parent/'JarvisLaunch.py';reject_links(path)
        raw=path.read_bytes() if path.exists() else b''
        try:record=embedded(raw)
        except CoreError:record=None
        if record is None:
            if activation:reject_links(Path(activation).absolute())
            record=read_json(Path(activation))['record'] if activation else read_json(root/'deployment/launcher.json')
        pin.verify(root,record,files=False)
        if record['schema']!=2 or record['build']!=expected_controller:
            raise CoreError('controller_baseline','Recovery cannot substitute a different or legacy controller')
        source=Path(archive or record['recovery_archive']).resolve();reject_links(source)
        if pin.sha(source)!=record['recovery_sha256']:raise CoreError('controller_recovery','Recovery archive changed')
        with zipfile.ZipFile(source) as stream:
            names=stream.namelist()
            if len(names)!=len(set(names)) or len(names)>12001:raise CoreError('controller_recovery','Invalid recovery member count')
            index=stream.read('controller-files.json')
            if hashlib.sha256(index).hexdigest()!=record['controller_inventory_sha256']:raise CoreError('controller_recovery','Recovery inventory changed')
            from sdk.protocol import decode
            inventory=decode(index)
            if set(names)!=set(inventory)|{'controller-files.json'}:raise CoreError('controller_recovery','Unexpected recovery member')
            files={};total=0
            for name,sha in inventory.items():
                pin.relative(name);info=stream.getinfo(name);total+=info.file_size
                if info.is_dir() or info.file_size>16*1024*1024 or total>256*1024*1024:
                    raise CoreError('controller_recovery','Recovery size exceeds its bound')
                value=stream.read(name)
                if hashlib.sha256(value).hexdigest()!=sha:raise CoreError('controller_recovery','Recovery content changed')
                files[name]=value
        ident,folder,_=publish_files(root,files,suffix='-recovered-'+uuid.uuid4().hex[:12])
        if ident!=expected_controller:raise CoreError('controller_recovery','Recovered controller identity differs')
        require_compatible(root,folder);require_compatible(root,app.approved(expected_build,fresh=False)['path'])
        change=root/'deployment/controller-changes'/uuid.uuid4().hex;backup(root,change)
        restored={**record,'controller':str(folder),'generation':record['generation']+1,'launcher_backup':str(change)}
        restored.pop('signature');restored['signature']=LocalApprovals(root).sign(restored)
        pin.verify(root,restored)
        write_json(change/'event.json',{'phase':'prepared','record':restored,'application_state':before})
        if app.state()!=before or (path.read_bytes() if path.exists() else b'')!=raw:
            raise CoreError('controller_baseline','Baseline changed during recovery')
        save_root(root,restored)
        return finish(root,restored,change/'event.json')


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['promote','repair','recover']);parser.add_argument('--data-root',type=Path,required=True)
    parser.add_argument('--build');parser.add_argument('--expected-controller');parser.add_argument('--expected-controller-token')
    parser.add_argument('--expected-epoch',type=int);parser.add_argument('--expected-build')
    parser.add_argument('--reviewed-source',action='store_true');parser.add_argument('--archive',type=Path);parser.add_argument('--activation',type=Path)
    args=parser.parse_args()
    if args.action=='promote':
        if not args.build or not args.expected_controller_token or args.expected_epoch is None or not args.expected_build:
            parser.error('Promotion requires candidate and exact prepared controller/application bindings')
        result=promote(args.data_root,args.build,expected_epoch=args.expected_epoch,expected_build=args.expected_build,
            expected_controller=args.expected_controller_token,reviewed_source=args.reviewed_source)
    elif args.action=='repair':result=repair(args.data_root,expected_controller=args.expected_controller)
    else:
        if not args.expected_controller or args.expected_epoch is None or not args.expected_build:
            parser.error('Recovery requires the same qualified controller and current application bindings')
        result=recover(args.data_root,expected_controller=args.expected_controller,expected_epoch=args.expected_epoch,
            expected_build=args.expected_build,archive=args.archive,activation=args.activation)
    print(canonical(result))


if __name__=='__main__':main()
