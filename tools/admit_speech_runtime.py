"""Explicit owner-reviewed one-time STT policy extension, never automatic adoption.

The new checker is derived from an exact installed checker, with its old test
inventory/bytes preserved and eight fixed boundary tests added. Only an approved
copy of the current application is used as policy source, not unfinished code.
"""
import argparse,ast,hashlib,json,shutil,subprocess,sys,uuid,zipfile
from pathlib import Path
from control import controller_pin as pin
from control.application_compatibility import require_compatible
from control.application_runtime import LocalApprovals
from control.atomic import write_json
from control.paths import reject_links
from control.recovery.gate import RunLock,StopGate
from host import application_controller as controllers
from modules.release_recovery.application import Applications,build,inspect_package
from sdk.protocol import canonical,digest,PROJECT
from tools.speech_dependency_policy import extend,declaration

TEST='test_speech_dependency_admission.py'
TEST_SHA='4028cc8c22d185dca705780065efa642675ba1af4a8e5bf1c3ef4a32b210e9de'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def overlay(original,test):
    if sha(test)!=TEST_SHA:raise ValueError('Speech boundary tests differ from the reviewed inventory')
    values={}
    for node in ast.parse(original['sdk/application_policy.py'].decode()).body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in ('TESTS','TEST_SUPPORT'):values[target.id]=ast.literal_eval(node.value)
    if set(values)!={'TESTS','TEST_SUPPORT'} or TEST in values['TESTS']:raise ValueError('Unknown or already extended test inventory')
    result=dict(original)
    result['tools/check_architecture.py']=extend(original['tools/check_architecture.py'])
    result['sdk/application_policy.py']=(
        '"""Pinned original regression inventory plus reviewed speech boundary cases."""\n'
        +'TESTS = '+repr(values['TESTS']+[TEST])+'\nTEST_SUPPORT = '+repr(values['TEST_SUPPORT'])+'\n').encode()
    result['tests/'+TEST]=test
    fingerprint=sha(result['tools/check_architecture.py']+result['tools/architecture-baseline.json']+
        b''.join(result['tests/'+name] for name in values['TESTS']+[TEST]+values['TEST_SUPPORT']))
    return result,fingerprint


def validate(folder,root,ident,log):
    result=subprocess.run([sys.executable,'-X','utf8','-I','-B',str(folder/'apps/development/releases.py'),'validate',
        '--data-root',str(root),'--build',ident,'--reviewed-source'],capture_output=True,timeout=180,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    log.write_bytes(result.stdout+b'\n'+result.stderr)
    if result.returncode:raise ValueError('Independent policy qualification failed; preserve '+str(log))
    checked=json.loads(result.stdout)
    if not checked.get('approval'):raise ValueError('Independent policy qualification did not approve the source')
    return checked['approval']['receipt']['report']


def admit(root,*,expected_controller,expected_epoch,expected_build,reviewed_policy=False):
    if not reviewed_policy:raise ValueError('The explicit new speech import policy requires source review')
    root=Path(root).resolve();reject_links(root);StopGate(root).require_running()
    app=Applications(root);before=controllers.baseline(app,expected_epoch,expected_build);old=pin.read(root)
    if digest(old)!=expected_controller:raise ValueError('Controller changed before speech admission')
    original,old_fingerprint=controllers.policy(root,old)
    updated,new_fingerprint=overlay(original,(PROJECT/'tests'/TEST).read_bytes())
    current=app.approved(expected_build,fresh=False);package=Path(current['path'])
    _,manifest=inspect_package(package);require_compatible(root,package)
    change=root/'deployment/controller-changes'/uuid.uuid4().hex
    controllers.backup(root,change);source=change/'source';source.mkdir()
    for name in manifest['files']:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(package/name,target)
    (source/'VERSION').write_text(manifest['version']+'-speech-policy',encoding='utf-8')
    (source/'modules/local_models/speech-runtime.json').write_bytes(declaration())
    # The source package retains its original SDK policy. The fixed new test
    # inventory belongs to the independent controller overlay, not the app.
    names=[p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()]
    ident=build(source,names,change/'source.zip',(source/'VERSION').read_text())
    app.stage(change/'source.zip')
    audit={'schema':1,'policy_extension':'speech-workers.v1','reviewed_policy':True,'previous_controller':old,
           'old_policy_sha256':old_fingerprint,'new_policy_sha256':new_fingerprint,'source_build':ident,
           'application_state':before,'old_tests_preserved':True,'supplemental_test_sha256':TEST_SHA}
    write_json(change/'speech-admission.json',audit)
    audit['old_policy_qualification']=validate(Path(old['controller']),root,ident,change/'old-policy-validation.log')
    files={name:(source/name).read_bytes() for name in names};files.update(updated)
    native='modules/skills/studio3d/worker-programs.json'
    if native in files:
        value=json.loads(files[native]);value['sources']['sdk/application_policy.py']=sha(files['sdk/application_policy.py'])
        files[native]=(json.dumps(value,indent=2)+'\n').encode()
    controller_id,folder,inventory=controllers.publish_files(root,files)
    audit['new_policy_qualification']=validate(folder,root,ident,change/'speech-policy-validation.log')
    if audit['new_policy_qualification'].get('policy_sha256')!=new_fingerprint:raise ValueError('Speech policy fingerprint mismatch')
    write_json(change/'speech-admission.json',audit)
    with RunLock(root,'application-release'):
        StopGate(root).require_running()
        if app.state()!=before or digest(pin.read(root))!=expected_controller:raise ValueError('Baseline changed during policy qualification')
        app.approved(ident);require_compatible(root,folder);require_compatible(root,package)
        archive=change/'controller.zip'
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as stream:
            stream.writestr('controller-files.json',inventory)
            for name,raw in sorted(files.items()):stream.writestr(name,raw)
        protocol=old.get('controller_protocol',json.loads((package/'config/controller-compatibility.json').read_bytes())['controller_protocol'])
        record={'schema':2,'controller_protocol':protocol,'build':controller_id,
            'runtime_source_build':ident,'controller':str(folder),'controller_inventory_sha256':controller_id,
            'data_root':str(root),'port':old['port'],'generation':old.get('generation',0)+1,
            'policy_anchor_build':old.get('policy_anchor_build',old['build']),'policy_sha256':new_fingerprint,'capsule_id':change.name,
            'recovery_archive':str(archive),'recovery_sha256':pin.sha(archive),'launcher_backup':str(change)}
        record['signature']=LocalApprovals(root).sign(record);pin.verify(root,record)
        write_json(change/'event.json',{'phase':'prepared','previous_controller':old,'record':record,
            'application_state':before,'policy_extension':'speech-workers.v1'})
        controllers.save_root(root,record)
        result=controllers.finish(root,record,change/'event.json')
        if app.state()!=before:raise ValueError('Application changed during policy-only registration')
        return {**result,'policy_extension':'speech-workers.v1','application_unchanged':True,'evidence':str(change/'speech-admission.json')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--daily-data',type=Path,required=True);parser.add_argument('--expected-controller',required=True)
    parser.add_argument('--expected-epoch',type=int,required=True);parser.add_argument('--expected-build',required=True)
    parser.add_argument('--reviewed-policy',action='store_true');args=parser.parse_args()
    print(canonical(admit(args.daily_data,expected_controller=args.expected_controller,expected_epoch=args.expected_epoch,
        expected_build=args.expected_build,reviewed_policy=args.reviewed_policy)))


if __name__=='__main__':main()
