"""Single-PC setup must preserve authority, source freeze and backup boundaries."""
import copy,json
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch

from control.atomic import write_json
from control.development_profile import write_secret
from host.core import Core
from host.development_runtime import start
from modules.release_recovery.application import Applications,build
from sdk.protocol import CoreError
from tools import workstation


LIVE_CHECK=workstation.require_live_daily

class WorkstationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve()
        self.daily=self.base/'daily/user-data';self.dev=self.base/'development/user-data'
        for root in [self.daily,self.dev]:Core.initialize(root).close()
        guard=patch.object(workstation,'require_live_daily');guard.start();self.addCleanup(guard.stop)
        self.grant={'client_id':'a'*32,'token':'synthetic-local-grant','allowed_providers':['vertex'],
            'daily_call_limit':64,'max_output_tokens':4096}
        for root in [self.daily,self.dev]:write_secret(root/'private/development-bridge.dpapi',self.grant)
        self.profile={'schema':1,'kind':'development','client_id':'a'*32,'external_actions':False,
            'allowed_providers':['vertex'],'bridge_origin':'http://127.0.0.1:18482','production_data':str(self.base/'old/user-data')}
        write_json(self.dev/'config/development.json',self.profile)

    def test_wrong_daily_path_and_port_collision_refused_before_spawn(self):
        with patch('host.development_runtime.spawn') as spawned:
            with self.assertRaisesRegex(ValueError,'different daily'):start(self.dev,self.daily,18283)
            self.profile['production_data']=str(self.daily);write_json(self.dev/'config/development.json',self.profile)
            with self.assertRaisesRegex(ValueError,'different ports'):start(self.dev,self.daily,18482)
            spawned.assert_not_called()

    def test_same_client_id_with_different_token_cannot_start_proxy(self):
        self.profile['production_data']=str(self.daily);write_json(self.dev/'config/development.json',self.profile)
        changed=copy.deepcopy(self.grant);changed['token']='different-secret';write_secret(self.daily/'private/development-bridge.dpapi',changed)
        with patch('host.development_runtime.spawn') as spawned:
            with self.assertRaisesRegex(ValueError,'grants do not match'):start(self.dev,self.daily,18283)
            spawned.assert_not_called()

    def test_link_repair_preserves_grants_and_existing_development_data(self):
        sentinel=self.dev/'state/sentinel.txt';sentinel.write_text('existing development task')
        before={root:(root/'private/development-bridge.dpapi').read_bytes() for root in [self.daily,self.dev]}
        with patch.object(workstation,'controller',return_value=(self.base,18282)),patch('tools.workstation.http.client.HTTPConnection') as connect:
            connect.return_value.connect.side_effect=ConnectionRefusedError()
            result=workstation.repair_link(self.daily,self.dev)
        self.assertTrue(result['grant_preserved']);self.assertEqual(sentinel.read_text(),'existing development task')
        for root in before:self.assertEqual((root/'private/development-bridge.dpapi').read_bytes(),before[root])
        self.assertEqual(json.loads((self.dev/'config/development.json').read_text())['production_data'],str(self.daily))
        self.assertEqual(len(list((self.dev/'state/workstation-link-backups').glob('*.json'))),1)

    def test_link_repair_refuses_mismatched_grant_and_live_proxy(self):
        original=(self.dev/'config/development.json').read_bytes()
        with patch.object(workstation,'controller',return_value=(self.base,18282)),patch('tools.workstation.http.client.HTTPConnection'):
            with self.assertRaisesRegex(ValueError,'Stop the existing'):workstation.repair_link(self.daily,self.dev)
        changed=copy.deepcopy(self.grant);changed['token']='wrong';write_secret(self.daily/'private/development-bridge.dpapi',changed)
        with self.assertRaisesRegex(ValueError,'grants do not match'):workstation.repair_link(self.daily,self.dev)
        self.assertEqual((self.dev/'config/development.json').read_bytes(),original)

    def test_changed_source_and_epoch_reject_before_maintenance(self):
        path=self.base/'source';path.mkdir();(path/'VERSION').write_text('v1')
        record={'daily_data':str(self.daily),'expected_epoch':7,'source':str(path),'files':{'VERSION':workstation.sha(path/'VERSION')}}
        with patch.object(workstation,'state',return_value={'epoch':8}):
            with self.assertRaisesRegex(ValueError,'baseline changed'):workstation.require_prepared(self.daily,record)
        (path/'VERSION').write_text('v2')
        with patch.object(workstation,'state',return_value={'epoch':7}),patch.object(workstation,'tracked_runtime',return_value=['VERSION']):
            with self.assertRaisesRegex(ValueError,'Source changed'):workstation.require_prepared(self.daily,record)

    def test_backup_requires_stopped_host_and_external_destination(self):
        Applications(self.daily)
        with self.assertRaisesRegex(ValueError,'outside daily'):workstation.backup(self.daily,self.daily/'backups')
        with patch.object(workstation,'state',return_value={'phase':'active'}):
            with self.assertRaisesRegex(ValueError,'Stop the managed'):workstation.backup(self.daily,self.base/'bad-backup')
        (self.daily/'state/sentinel.txt').write_text('preserve current facts')
        target=self.base/'backup';result=workstation.backup(self.daily,target)
        self.assertGreater(result['sqlite_integrity_ok'],0)
        self.assertEqual((target/'state/sentinel.txt').read_text(),'preserve current facts')
        self.assertEqual((target/'private/development-bridge.dpapi').read_bytes(),(self.daily/'private/development-bridge.dpapi').read_bytes())

    def test_prepare_refuses_untracked_runtime_instead_of_partial_delivery(self):
        with patch.object(workstation,'tracked_runtime',return_value=['VERSION']),patch('tools.workstation.subprocess.check_output',return_value=b'host/new_feature.py\0'),patch.object(workstation,'release') as release:
            with self.assertRaisesRegex(ValueError,'untracked runtime'):workstation.prepare(self.daily,self.dev,self.base)
            release.assert_not_called()

    def test_backup_failure_restarts_only_untouched_stopped_baseline(self):
        baseline={'build':'a'*64,'version':'synthetic','slot':'A','epoch':2}
        prepared={'daily_data':str(self.daily),'expected_epoch':2,'source':str(self.base),'build':'b'*64,'files':{}}
        write_json(self.dev/'state/workstation-update.json',prepared)
        before={'phase':'active','epoch':2,'active':baseline};after={**before,'phase':'stopped'}
        with patch.object(workstation,'require_prepared'),patch.object(workstation,'state',side_effect=[before,after,after]),patch.object(workstation,'release',return_value=before) as release,patch.object(workstation,'preflight'),patch.object(workstation,'conditional_stop') as stop,patch.object(workstation,'backup',side_effect=OSError('synthetic disk full')),patch.object(workstation,'start_daily') as restart:
            with self.assertRaisesRegex(OSError,'disk full'):workstation.apply(self.daily,self.dev)
        restart.assert_called_once_with(self.daily)
        self.assertEqual([call.args[1] for call in release.call_args_list],['status'])
        stop.assert_called_once_with(self.daily,2,'a'*64)

    def prepare_source(self):
        source=self.base/'source';(source/'apps/workbench').mkdir(parents=True)
        (source/'VERSION').write_text('v1');(source/'apps/workbench/server.py').write_text('# synthetic runtime')
        return source,['VERSION','apps/workbench/server.py']

    def exercise_prepare(self,mutation_phase=None):
        source,names=self.prepare_source();events=[];built={}
        def release(root,action,*options):
            events.append(action)
            if action=='build':
                if mutation_phase=='build':(source/'VERSION').write_text('v2')
                archive=Path(options[options.index('--archive')+1])
                built['id']=build(source,names,archive,(source/'VERSION').read_text())
                return {'build':built['id']}
            if action=='validate':
                if mutation_phase=='validate':(source/'VERSION').write_text('v2')
                return {'approval':{'receipt':{'report':{'passed':True}}}}
            return {}
        prepared=self.dev/'state/workstation-update.json';prepared.write_text('{"prior":"keep"}')
        with patch.object(workstation,'tracked_runtime',return_value=names),patch.object(workstation.subprocess,'check_output',return_value=b''),patch.object(workstation,'state',return_value={'epoch':7}),patch.object(workstation,'release',side_effect=release):
            if mutation_phase:
                with self.assertRaisesRegex(ValueError,'Source changed during candidate'):workstation.prepare(self.daily,self.dev,source)
                self.assertEqual(json.loads(prepared.read_text()),{'prior':'keep'})
                if mutation_phase=='build':self.assertEqual(events,['build'])
            else:
                result=workstation.prepare(self.daily,self.dev,source);record=json.loads(prepared.read_text())
                self.assertEqual(record['build'],built['id']);self.assertEqual(result['expected_epoch'],7)
                self.assertEqual(record['files'],{name:workstation.sha(source/name) for name in names})
                workstation.require_prepared(self.daily,record)
                (source/'VERSION').write_text('v2')
                with self.assertRaisesRegex(ValueError,'Source changed'):workstation.require_prepared(self.daily,record)

    def test_edit_during_build_never_stages_mixed_snapshot(self):self.exercise_prepare('build')

    def test_edit_during_validation_does_not_bind_untested_source(self):self.exercise_prepare('validate')

    def test_preparation_binds_built_manifest_and_later_edit_invalidates(self):self.exercise_prepare()

    def test_controller_preparation_preserves_application_ready_record_and_binds_both_baselines(self):
        source,names=self.prepare_source();before={'epoch':7,'phase':'active','active':{'build':'a'*64}}
        pointer={'schema':1,'build':'old'};built={}
        oldready=self.dev/'state/workstation-update.json';oldready.write_text('{"prior":"preserve"}')
        def release(root,action,*options):
            if action=='build':
                archive=Path(options[options.index('--archive')+1]);built['id']=build(source,names,archive,'v1');return {'build':built['id']}
            if action=='validate':return {'approval':{'receipt':{'report':{'passed':True}}}}
            return {}
        with patch.object(workstation,'tracked_runtime',return_value=names),patch.object(workstation.subprocess,'check_output',return_value=b''),patch.object(workstation,'state',return_value=before),patch.object(workstation,'release',side_effect=release),patch('control.controller_pin.read',return_value=pointer),patch('host.application_controller.promote',return_value={'committed':True}) as promote:
            workstation.prepare(self.daily,self.dev,source,controller_only=True)
            ready=json.loads((self.dev/'state/workstation-controller-update.json').read_text())
            from sdk.protocol import digest
            self.assertEqual(ready['expected_controller'],digest(pointer));self.assertEqual(ready['expected_build'],'a'*64)
            self.assertEqual(json.loads(oldready.read_text()),{'prior':'preserve'})
            workstation.apply_controller(self.daily,self.dev,reviewed_source=True)
            promote.assert_called_once_with(self.daily,built['id'],expected_epoch=7,expected_build='a'*64,expected_controller=digest(pointer),reviewed_source=True)
            (source/'VERSION').write_text('v2')
            with self.assertRaisesRegex(ValueError,'Source changed'):workstation.apply_controller(self.daily,self.dev,reviewed_source=True)
            self.assertEqual(promote.call_count,1)

    def test_newer_status_is_not_stopped_by_stale_apply(self):
        before={'phase':'active','epoch':2,'active':{'build':'a'*64}}
        newer={'phase':'active','epoch':3,'active':{'build':'b'*64}}
        write_json(self.dev/'state/workstation-update.json',{'build':'c'*64,'expected_epoch':2})
        with patch.object(workstation,'require_prepared'),patch.object(workstation,'state',return_value=before),patch.object(workstation,'release',return_value=newer),patch.object(workstation,'conditional_stop') as stop:
            with self.assertRaisesRegex(ValueError,'baseline changed'):workstation.apply(self.daily,self.dev)
        stop.assert_not_called()

    def test_late_baseline_change_is_rejected_by_conditional_stop(self):
        before={'phase':'active','epoch':2,'active':{'build':'a'*64}}
        write_json(self.dev/'state/workstation-update.json',{'build':'c'*64,'expected_epoch':2})
        with patch.object(workstation,'require_prepared'),patch.object(workstation,'state',return_value=before),patch.object(workstation,'release',return_value=before),patch.object(workstation,'preflight'),patch.object(workstation,'conditional_stop',side_effect=CoreError('application_epoch','baseline changed')),patch.object(workstation,'backup') as backup,patch.object(workstation,'start_daily') as restart:
            with self.assertRaises(CoreError):workstation.apply(self.daily,self.dev)
        backup.assert_not_called();restart.assert_not_called()


    def test_persisted_active_registration_after_shutdown_is_not_live(self):
        with patch.object(workstation,'controller',return_value=(self.base,18282)),patch.object(workstation,'state',return_value={'phase':'active','epoch':7,'active':{'build':'a'*64}}),patch('adapters.application_host.WorkbenchProcess') as driver:
            driver.return_value.running.return_value=False
            with self.assertRaisesRegex(ValueError,'system restart'):LIVE_CHECK(self.daily)
            driver.return_value.identity.assert_not_called()

if __name__=='__main__':unittest.main()
