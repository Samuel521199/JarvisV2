"""Controller-only transitions use synthetic signed packages and real filesystem commits."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from host.core import Core
from host import application_controller as controllers
from host.application_installation import install
from control import controller_pin as pin
from control.recovery.gate import RunLock,StopGate
from modules.release_recovery.application import Applications,build
from sdk.controller_bootstrap import embedded
from sdk.protocol import CoreError,digest,read_json,PROJECT


class Driver:
    def __init__(self):self.events=[]
    def start(self,*_):self.events.append('start')
    def health(self,*_):pass
    def drain(self,*_):self.events.append('drain')
    def stop(self,*_):self.events.append('stop')
    def activate(self,*_):pass


class ControllerTransitions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.home=self.base/'installation';self.root=self.home/'user-data'
        self.root.mkdir(parents=True);Core.initialize(self.root).close();self.app=Applications(self.root);self.driver=Driver()
        self.old=self.candidate('old');self.app.validate(self.old,lambda _: {'passed':True});self.app.adopt(self.old,self.driver)
        install(self.root,self.home,Path(self.app.record(self.old)['path']))
        self.before=self.app.state();self.old_record=pin.read(self.root);self.token=digest(self.old_record)
        self.policy,self.policy_sha=controllers.policy(self.root,self.old_record)
        self.new=self.candidate('new',modern=True)
        self.app.validate(self.new,lambda _:self.report())
        (self.root/'state/business-sentinel').write_bytes(b'preserve current business, rights and corrections')

    def candidate(self,name,modern=False):
        source=self.base/(name+'-source');source.mkdir()
        for top in ['control','sdk']:shutil.copytree(PROJECT/top,source/top,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        # Empty test policy is a synthetic fixture, never a production qualification.
        (source/'sdk/application_policy.py').write_text('TESTS=[]\nTEST_SUPPORT=[]\n')
        (source/'VERSION').write_text(name);(source/'apps/workbench').mkdir(parents=True)
        (source/'apps/workbench/server.py').write_text('# synthetic server fixture')
        (source/'apps/workbench/launch.py').write_text('print("SYNTHETIC_CONTROLLER_LAUNCHED")\n')
        (source/'tools').mkdir();(source/'tools/architecture-baseline.json').write_text('{}')
        if modern:
            (source/'config').mkdir()
            for file in ['controller-compatibility.json','conditional-advice-compatibility.json']:
                shutil.copyfile(PROJECT/'config'/file,source/'config'/file)
            # Exercise the real native policy overlay path, not only a
            # synthetic controller without a Studio3D source inventory.
            native=source/'modules/skills/studio3d/worker-programs.json'
            native.parent.mkdir(parents=True)
            native.write_text(json.dumps({'sources':{'sdk/application_policy.py':'candidate-policy'}}))
        files=[p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()]
        archive=self.base/(name+'.zip');ident=build(source,files,archive,name);self.app.stage(archive);return ident

    def report(self):return {'passed':True,'reviewed_source':True,'architecture_passed':True,'tests_passed':True,
        'runtime_intact':True,'policy_sha256':self.policy_sha,'scope':'synthetic protocol fixture, no independent runtime tests'}

    def promote(self,**changes):
        args={'expected_epoch':self.before['epoch'],'expected_build':self.old,'expected_controller':self.token,'reviewed_source':True}
        args.update(changes);return controllers.promote(self.root,self.new,**args)

    def launch(self):return subprocess.run([sys.executable,'-I','-B',str(self.home/'JarvisLaunch.py'),'--no-browser'],capture_output=True,text=True)

    def test_promotion_changes_controller_not_application_and_keeps_frozen_policy(self):
        result=self.promote();record=result['record'];self.assertTrue(result['committed']);self.assertEqual(result['registration_pending'],[])
        self.assertEqual(self.app.state(),self.before);self.assertEqual(self.driver.events,['start'])
        self.assertNotEqual(record['build'],self.old);self.assertEqual(record['runtime_source_build'],self.new)
        for name,raw in self.policy.items():self.assertEqual((Path(record['controller'])/name).read_bytes(),raw)
        import hashlib
        native=read_json(Path(record['controller'])/'modules/skills/studio3d/worker-programs.json')
        self.assertEqual(native['sources']['sdk/application_policy.py'],hashlib.sha256(self.policy['sdk/application_policy.py']).hexdigest())
        launched=self.launch();self.assertEqual(launched.returncode,0,launched.stderr)
        self.assertIn('SYNTHETIC_CONTROLLER_LAUNCHED',launched.stdout)
        self.assertEqual((self.root/'state/business-sentinel').read_bytes(),b'preserve current business, rights and corrections')

    def test_stale_epoch_build_controller_and_unreviewed_source_never_replace_pointer(self):
        old=(self.home/'JarvisLaunch.py').read_bytes()
        for changes in [{'expected_epoch':99},{'expected_build':'0'*64},{'expected_controller':'0'*64},{'reviewed_source':False}]:
            with self.subTest(changes=changes),self.assertRaises(CoreError):self.promote(**changes)
            self.assertEqual((self.home/'JarvisLaunch.py').read_bytes(),old)
        self.assertEqual(self.app.state(),self.before)

    def test_other_policy_approval_is_not_current_independent_qualification(self):
        self.app.validate(self.new,lambda _:self.report()|{'policy_sha256':'0'*64})
        with self.assertRaises(CoreError):self.promote()
        self.assertEqual(pin.read(self.root),self.old_record)

    def test_failure_before_atomic_commit_keeps_original_bootstrap_and_cache(self):
        old=(self.home/'JarvisLaunch.py').read_bytes();cache=(self.root/'deployment/launcher.json').read_bytes()
        with patch.object(controllers,'save_root',side_effect=OSError('synthetic commit failure')),self.assertRaises(OSError):self.promote()
        self.assertEqual((self.home/'JarvisLaunch.py').read_bytes(),old)
        self.assertEqual((self.root/'deployment/launcher.json').read_bytes(),cache)
        self.assertFalse((self.root/'deployment/controller-protocol.json').exists())

    def test_committed_launcher_remains_authoritative_when_cache_write_fails(self):
        actual=controllers.write_json
        def fail(path,value):
            if path==self.root/'deployment/launcher.json':raise OSError('synthetic cache fault')
            return actual(path,value)
        with patch.object(controllers,'write_json',side_effect=fail):result=self.promote()
        self.assertIn('launcher.json',result['registration_pending'])
        self.assertEqual(read_json(self.root/'deployment/launcher.json')['schema'],1)
        self.assertEqual(pin.read(self.root)['build'],result['record']['build'])
        from tools.workstation import controller
        self.assertEqual(controller(self.root)[0],Path(result['record']['controller']))
        self.assertEqual(self.launch().returncode,0)
        repaired=controllers.repair(self.root,expected_controller=result['record']['build'])
        self.assertEqual(repaired['registration_pending'],[]);self.assertEqual(read_json(self.root/'deployment/launcher.json')['schema'],2)

    def test_tampered_controller_is_refused_then_recovered_to_fresh_verified_copy(self):
        record=self.promote()['record'];folder=Path(record['controller']);(folder/'apps/workbench/launch.py').write_text('print("MUST_NOT_EXECUTE")')
        broken=self.launch();self.assertNotEqual(broken.returncode,0);self.assertNotIn('MUST_NOT_EXECUTE',broken.stdout)
        with self.assertRaises(CoreError):pin.read(self.root)
        gate=StopGate(self.root);gate.stop();token=gate.token()
        result=controllers.recover(self.root,expected_controller=record['build'],expected_epoch=self.before['epoch'],expected_build=self.old)
        self.assertNotEqual(result['record']['controller'],record['controller']);self.assertTrue(folder.exists())
        self.assertEqual(pin.read(self.root)['build'],record['build']);self.assertEqual(gate.token(),token)
        self.assertEqual(self.app.state(),self.before);self.assertEqual(self.launch().returncode,0)

    def test_recovery_refuses_wrong_identity_or_changed_archive(self):
        record=self.promote()['record'];root=(self.home/'JarvisLaunch.py').read_bytes()
        with self.assertRaises(CoreError):controllers.recover(self.root,expected_controller='0'*64,expected_epoch=self.before['epoch'],expected_build=self.old)
        archive=Path(record['recovery_archive']);archive.write_bytes(archive.read_bytes()+b'changed')
        with self.assertRaises(CoreError):controllers.recover(self.root,expected_controller=record['build'],expected_epoch=self.before['epoch'],expected_build=self.old)
        self.assertEqual((self.home/'JarvisLaunch.py').read_bytes(),root)

    def test_corrupt_bootstrap_and_cache_recover_only_with_signed_activation_evidence(self):
        record=self.promote()['record'];activation=Path(record['launcher_backup'])/'event.json'
        (self.home/'JarvisLaunch.py').write_text('# interrupted bootstrap')
        (self.root/'deployment/launcher.json').write_text('{}')
        result=controllers.recover(self.root,expected_controller=record['build'],expected_epoch=self.before['epoch'],expected_build=self.old,activation=activation)
        self.assertTrue(result['committed']);self.assertEqual(self.launch().returncode,0)

    def test_application_installation_does_not_rebind_an_independent_controller(self):
        record=self.promote()['record'];raw=(self.home/'JarvisLaunch.py').read_bytes()
        result=install(self.root,self.home,Path(self.app.record(self.old)['path']))
        self.assertEqual(result['build'],record['build']);self.assertEqual((self.home/'JarvisLaunch.py').read_bytes(),raw)

    def test_live_release_lock_and_unknown_protocol_refuse_transitions(self):
        with RunLock(self.root,'application-release'),self.assertRaises(CoreError):self.promote()
        record=self.promote()['record'];path=self.root/'deployment/controller-protocol.json';path.write_text(json.dumps({'schema':1,'minimum':pin.PROTOCOL+1}))
        with self.assertRaises(CoreError):pin.read(self.root)
        with self.assertRaises(CoreError):controllers.recover(self.root,expected_controller=record['build'],expected_epoch=self.before['epoch'],expected_build=self.old)
        self.assertEqual(read_json(path)['minimum'],pin.PROTOCOL+1)

    def test_late_data_change_is_checked_before_controller_commit(self):
        original=controllers.publish_files
        def changed(*args,**kwargs):
            result=original(*args,**kwargs)
            from modules.context_knowledge.knowledge import Knowledge
            core=Core(self.root)
            try:Knowledge(core.db).save({'id':'','scope':'personal','title':'Synthetic method','text':'{"schema":"jarvis.method-card.v1"}','providers':[],'paused':False},0)
            finally:core.close()
            return result
        with patch.object(controllers,'publish_files',side_effect=changed),self.assertRaises(CoreError):self.promote()
        self.assertEqual(pin.read(self.root),self.old_record);self.assertEqual(self.app.state(),self.before)

    def test_unmanifested_import_is_refused_before_controller_code_runs(self):
        record=self.promote()['record'];folder=Path(record['controller'])
        (folder/'sqlite3.py').write_text('print("MUST_NOT_IMPORT");raise RuntimeError("injected")')
        launched=self.launch();self.assertNotEqual(launched.returncode,0)
        self.assertNotIn('MUST_NOT_IMPORT',launched.stdout)
        self.assertIn('Unexpected controller files',launched.stderr)

    def test_missing_bootstrap_cannot_reinstall_legacy_below_protocol_floor(self):
        record=self.promote()['record'];(self.home/'JarvisLaunch.py').unlink()
        with self.assertRaises(CoreError):install(self.root,self.home,Path(self.app.record(self.old)['path']))
        self.assertFalse((self.home/'JarvisLaunch.py').exists())
        recovered=controllers.recover(self.root,expected_controller=record['build'],expected_epoch=self.before['epoch'],expected_build=self.old)
        self.assertEqual(pin.read(self.root)['build'],recovered['record']['build'])

    def test_active_controller_source_cannot_be_retired_as_unused_application_code(self):
        record=self.promote()['record']
        with self.assertRaises(CoreError):self.app.retire(self.new)
        self.assertEqual(pin.read(self.root)['build'],record['build'])
        self.assertFalse(self.app.record(self.new).get('retired'))

    def test_withdrawn_source_qualification_cannot_be_revived_by_recovery_capsule(self):
        record=self.promote()['record'];package=self.app.record(self.new);package['approval']=None
        from sdk.protocol import canonical
        with self.app.db() as db:db.execute('UPDATE packages SET body=? WHERE build=?',(canonical(package),self.new))
        with self.assertRaises(CoreError):pin.read(self.root)
        self.assertNotEqual(self.launch().returncode,0)
        with self.assertRaises(CoreError):controllers.recover(self.root,expected_controller=record['build'],expected_epoch=self.before['epoch'],expected_build=self.old)
        self.assertEqual(self.app.state(),self.before)


    def test_protocol_floor_advances_and_current_verifier_rejects_legacy_record(self):
        old=(self.home/'JarvisLaunch.py').read_bytes()
        write=self.root/'deployment/controller-protocol.json'
        result=self.promote();committed=(self.home/'JarvisLaunch.py').read_bytes()
        self.assertEqual(result['record']['controller_protocol'],pin.PROTOCOL)
        self.assertEqual(read_json(write),{'schema':1,'minimum':pin.PROTOCOL})
        (self.home/'JarvisLaunch.py').write_bytes(old)
        with self.assertRaises(CoreError):pin.read(self.root)
        (self.home/'JarvisLaunch.py').write_bytes(committed)
        self.assertEqual(pin.read(self.root)['build'],result['record']['build'])


    def test_registration_repair_raises_an_older_floor_without_replacing_root(self):
        record=self.promote()['record'];path=self.root/'deployment/controller-protocol.json'
        root=(self.home/'JarvisLaunch.py').read_bytes()
        path.write_text('{"schema":1,"minimum":2}')
        repaired=controllers.repair(self.root,expected_controller=record['build'])
        self.assertEqual(repaired['registration_pending'],[])
        self.assertEqual(read_json(path)['minimum'],pin.PROTOCOL)
        self.assertEqual((self.home/'JarvisLaunch.py').read_bytes(),root)
        path.write_text(json.dumps({'schema':1,'minimum':pin.PROTOCOL+1}))
        with self.assertRaises(CoreError):controllers.repair(self.root,expected_controller=record['build'])
        self.assertEqual(read_json(path)['minimum'],pin.PROTOCOL+1)

    def test_protocol2_record_is_known_before_floor3_and_rejected_afterwards(self):
        from control.application_runtime import LocalApprovals
        record=self.promote()['record'];prior={**record,'controller_protocol':2}
        prior.pop('signature');prior['signature']=LocalApprovals(self.root).sign(prior)
        floor=self.root/'deployment/controller-protocol.json'
        # Isolate record/floor semantics; this synthetic protocol2 record does
        # not claim that the protocol3 file inventory is a protocol2 binary.
        floor.write_text('{"schema":1,"minimum":2}')
        self.assertEqual(pin.verify(self.root,prior,files=False)['controller_protocol'],2)
        floor.write_text('{"schema":1,"minimum":3}')
        with self.assertRaises(CoreError) as error:pin.verify(self.root,prior,files=False)
        self.assertEqual(error.exception.code,'controller_protocol')
        self.assertEqual(pin.read(self.root)['controller_protocol'],pin.PROTOCOL)


if __name__=='__main__':unittest.main()
