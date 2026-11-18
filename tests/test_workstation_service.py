"""Daily automation must not inherit development changes or defeat owner stop."""
import copy,json,os
from pathlib import Path
import tempfile,unittest
from unittest.mock import Mock,patch

from host.core import Core
from modules.release_recovery.application import Applications,build,inspect_package
from adapters.application_host import WorkbenchProcess
from control.atomic import write_json
from control.application_runtime import LocalApprovals
from control.recovery.gate import StopGate
from sdk.protocol import CoreError
from tools import workstation_service as service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'daily/user-data';self.dev=self.base/'dev/user-data'
        Core.initialize(self.root).close();Core.initialize(self.dev).close();LocalApprovals(self.root).initialize()
        self.config={'schema':2,'enabled':True,'auto_updates':True,'daily_data':str(self.root),'development_data':str(self.dev),
            'development_autostart':False,'backup_root':str(self.base/'backups'),'poll_seconds':3600,
            'active_seconds':30,'offline_restart':False,'source_notification':True,'idle_seconds':60,
            'observation_seconds':180,'restart_limit':3}
        service.base(self.root).mkdir(parents=True,exist_ok=True)
        service.signed(self.root,service.base(self.root)/'policy.json',self.config)
        self.state={'phase':'active','epoch':3,'active':{'build':'a'*64,'version':'a','slot':'A','epoch':3},
            'previous':{'build':'z'*64,'epoch':2},'pending':None}

    def engine(self):
        e=object.__new__(service.Engine);e.root=self.root;e.folder=service.base(self.root);e.config=copy.deepcopy(self.config)
        e.operator=Mock();e.port=18282;e.driver=Mock();e.driver.running.return_value=True
        e.app=Mock();e.app.state.return_value=copy.deepcopy(self.state);e.clock=lambda:1000
        e.started=True;e.idle_since=None;e.bad=0;e.error_count=0;e.journal={'phase':'idle','restarts':[]}
        e.idle=Mock(return_value=True)
        return e

    def ticket(self,build='b'*64):
        prepared={'build':build,'daily_data':str(self.root),'source':str(self.base/'source'),'expected_epoch':3,'files':{}}
        value={'schema':1,'id':'x'*32,'daily_data':str(self.root),'development_data':str(self.dev),
            'prepared':prepared,'baseline':self.state['active'],'expires':2000,'created':999}
        service.signed(self.root,service.base(self.root)/'ticket.json',value)
        return value

    @unittest.skipUnless(os.name=='nt','Windows sharing mode must be reproduced')
    def test_atomic_control_publish_retries_transient_windows_reader(self):
        import ctypes
        from ctypes import wintypes
        abi=ctypes.WinDLL('kernel32',use_last_error=True)
        abi.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        abi.CreateFileW.restype=wintypes.HANDLE
        abi.CloseHandle.argtypes=[wintypes.HANDLE]
        target=self.base/'control.json';write_json(target,{'phase':'active'})
        handle=abi.CreateFileW(str(target),0x80000000,1,None,3,0,None)
        self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
        from control import atomic
        replace=atomic.os.replace
        rejected=[]
        def locked_once(src,dst):
            try:return replace(src,dst)
            except PermissionError as error:
                rejected.append(error.winerror)
                abi.CloseHandle(handle)
                raise
        with patch.object(atomic.os,'replace',side_effect=locked_once):
            try:write_json(target,{'phase':'draining'})
            finally:
                if not rejected:abi.CloseHandle(handle)
        self.assertTrue(rejected)
        self.assertEqual(service.read(target),{'phase':'draining'})

    def test_recovered_baseline_only_consumes_exact_interrupted_ticket(self):
        ticket=self.ticket()
        for matches in (False,True):
            e=self.engine()
            e.journal.update(phase='attention',error='PermissionError',baseline=self.state['active'],
                             ticket=ticket['id'],target=ticket['prepared']['build'])
            active={**self.state['active'],'epoch':4}
            e.app.state.return_value={**self.state,'epoch':4,'active':active,'error':'interrupted_handoff'}
            control={'phase':'active','build':active['build'],'epoch':4 if matches else 3}
            with patch.object(service,'coordination',return_value=control):
                e.tick()
            e.operator.apply.assert_not_called()
            self.assertEqual(e.journal['phase'],'rejected' if matches else 'attention')
            if matches:
                self.assertEqual(e.journal['error'],'baseline_recovered')
                self.assertEqual(e.journal['original_error'],'PermissionError')

    def test_attention_reconciles_only_receipted_owner_adoption(self):
        initial=self.ticket();baseline=self.state['active']
        previous={**baseline,'epoch':4}
        target={'build':initial['prepared']['build'],'epoch':5,'version':'b','slot':'B'}
        ticket={**initial,'id':'m'*32,'baseline':previous,'prepared':{**initial['prepared'],'expected_epoch':4}}
        service.signed(self.root,service.base(self.root)/'ticket.json',ticket)
        current={**self.state,'epoch':5,'active':target,'previous':previous,'error':None}
        record={'build':target['build'],'before':{'active':previous},'after':current,'passed':True,
                'backup':{'folder':str(self.base/'backup')}}
        path=self.dev/'state/workstation-last-update.json'
        for valid in (False,True):
            write_json(path,{**record,'passed':valid})
            e=self.engine()
            e.journal.update(phase='attention',error='PermissionError',baseline=baseline,
                             ticket=initial['id'],target=target['build'])
            e.app.state.return_value=current
            with patch.object(service,'coordination',return_value={'phase':'active','build':target['build'],'epoch':5}):
                e.tick()
            e.operator.apply.assert_not_called()
            self.assertEqual(e.journal['phase'],'complete' if valid else 'attention')
            if valid:
                self.assertEqual(e.journal['ticket'],ticket['id'])
                self.assertEqual(e.journal['interrupted_ticket'],initial['id'])
                self.assertEqual(e.journal['error'],'manual_adoption_confirmed')

    def test_policy_tamper_fails_closed(self):
        path=service.base(self.root)/'policy.json';value=service.read(path);value['value']['auto_updates']=False;write_json(path,value)
        with self.assertRaises(CoreError):service.policy(self.root)

    def test_policy_cannot_enable_development_autostart(self):
        self.config['development_autostart']=True;service.signed(self.root,service.base(self.root)/'policy.json',self.config)
        with self.assertRaises(ValueError):service.policy(self.root)

    def test_backup_inside_daily_is_refused(self):
        self.config['backup_root']=str(self.root/'backups');service.signed(self.root,service.base(self.root)/'policy.json',self.config)
        with self.assertRaises(ValueError):service.policy(self.root)

    def test_only_one_service_per_root(self):
        with service.lease(self.root):
            with self.assertRaises(OSError):
                with service.lease(self.root):pass

    def test_stop_and_latch_never_restart_or_update(self):
        for latch in (False,True):
            StopGate(self.root).stop(latch=latch);e=self.engine();e.tick()
            e.driver.running.assert_not_called();e.operator.start_daily.assert_not_called();e.operator.apply.assert_not_called()

    def test_manual_application_stop_does_not_restart(self):
        e=self.engine();e.started=False;e.app.state.return_value={**self.state,'phase':'stopped'};e.tick()
        e.operator.start_daily.assert_not_called();self.assertEqual(service.read(e.folder/'status.json')['status'],'manual_stop')

    def test_missing_active_host_does_not_restart_or_inspect_source(self):
        e=self.engine();e.started=False;e.driver.running.return_value=False;e.completion=Mock(state={});e.tick()
        e.operator.start_daily.assert_not_called();e.completion.tick.assert_not_called();e.completion.poll.assert_not_called()
        e.completion.close.assert_called_once()
        self.assertEqual(service.read(e.folder/'status.json')['status'],'offline_no_update_checks')
        e.operator.start_development.assert_not_called()

    def test_login_start_is_explicit_and_separate_from_offline_supervision(self):
        e=self.engine();e.driver.running.return_value=False;e.logon_start()
        e.operator.start_daily.assert_called_once_with(self.root)
        e=self.engine();e.app.state.return_value={**self.state,'phase':'stopped'};e.logon_start()
        e.operator.start_daily.assert_not_called()

    def test_online_health_tick_does_not_imply_source_inspection(self):
        e=self.engine();e.completion=Mock(state={});e.tick(check_source=False)
        e.completion.poll.assert_called_once();e.completion.tick.assert_not_called()

    def test_new_policy_refuses_fast_passive_poll_or_offline_restart(self):
        for patch_value in ({'poll_seconds':30},{'offline_restart':True},{'source_notification':False}):
            service.signed(self.root,service.base(self.root)/'policy.json',{**self.config,**patch_value})
            with self.assertRaises(ValueError):service.policy(self.root)

    def test_restarts_are_bounded_and_reserved_before_failure(self):
        e=self.engine();e.journal['restarts']=[998,999,1000];self.assertFalse(e.restart());e.operator.start_daily.assert_not_called()
        self.assertEqual(e.journal['phase'],'attention')
        e=self.engine();e.operator.start_daily.side_effect=RuntimeError('fail')
        with self.assertRaises(RuntimeError):e.restart()
        self.assertEqual(service.read(e.folder/'journal.json')['restarts'],[1000])

    def test_other_maintenance_owner_not_disturbed(self):
        for phase in ['draining','starting','blocked']:
            e=self.engine();e.completion=Mock(state={});e.app.state.return_value={**self.state,'phase':phase};e.tick()
            e.driver.running.assert_not_called();e.operator.start_daily.assert_not_called()
            e.completion.close.assert_called_once();e.completion.poll.assert_not_called();e.completion.tick.assert_not_called()

    def test_already_consumed_and_quarantined_not_replayed(self):
        ticket=self.ticket()
        for journal in [{'phase':'complete','ticket':ticket['id']},{'phase':'quarantined','failed_build':ticket['prepared']['build']}]:
            e=self.engine();e.journal.update(journal);e.tick();e.operator.apply.assert_not_called()

    def test_consumed_completion_ticket_stays_ready_after_documentation_commit(self):
        ticket=self.ticket();ticket['prepared']['completion_commit']='old-reviewed-head'
        service.signed(self.root,service.base(self.root)/'ticket.json',ticket)
        e=self.engine();e.completion=Mock();e.completion.state={'head':'documentation-head','status':'no_runtime_change'}
        e.journal.update(phase='complete',ticket=ticket['id']);e.tick()
        self.assertEqual(service.read(e.folder/'status.json')['status'],'ready');e.operator.apply.assert_not_called()
        # A genuinely new ticket still needs its matching independent checker
        # to exit successfully; consuming an old ticket grants no new admission.
        e.journal.pop('ticket');e.tick()
        self.assertEqual(service.read(e.folder/'status.json')['status'],'waiting_for_independent_check_exit')
        e.operator.apply.assert_not_called()

    def test_unsigned_ticket_refused(self):
        self.ticket();path=service.base(self.root)/'ticket.json';envelope=service.read(path);envelope['value']['prepared']['build']='c'*64;write_json(path,envelope)
        e=self.engine()
        with self.assertRaises(CoreError):e.tick()
        e.operator.apply.assert_not_called()

    def test_multiple_failures_keep_older_builds_quarantined(self):
        e=self.engine();e.save(phase='quarantined',failed_build='b'*64);e.save(phase='quarantined',failed_build='c'*64)
        self.assertEqual(set(e.journal['quarantined_builds']),{'b'*64,'c'*64})
        self.ticket(build='b'*64);e.tick();e.operator.apply.assert_not_called()

    def test_only_proven_parked_waits_are_allowed(self):
        from modules.mail.store import MailStore
        store=MailStore(self.root)
        try:
            job=store.job('fixture-waiting-network','read',{'message_id':'synthetic'})[0]
            store.update(job['id'],status='WAITING_NETWORK')
            row={'id':job['id'],'source':'mail','operation':'read','state':'waiting'}
            sample={'activity':{'drained':True},'counts':{'waiting':1,'running':0,'queued':0,'external':0,'unknown':0},
                    'items':[row],'sources':[{'status':'connected'}]}
            self.assertTrue(service.quiet_for_handoff(self.root,sample))
            for change in ({'activity':{'drained':False}},{'items':[]},{'sources':[{'status':'unavailable'}]},
                           {'items':[dict(row,operation='send')]},{'counts':dict(sample['counts'],queued=1)}):
                self.assertFalse(service.quiet_for_handoff(self.root,{**sample,**change}))
            store.update(job['id'],effect_started=True)
            self.assertFalse(service.quiet_for_handoff(self.root,sample))
            task={'id':'unrequested','source':'tasks','state':'waiting','raw_status':'READY'}
            self.assertTrue(service.quiet_for_handoff(self.root,{**sample,'items':[task]}))
            self.assertFalse(service.quiet_for_handoff(self.root,{**sample,'items':[dict(task,raw_status='WAITING')]}))
        finally:store.close()

    def test_superseded_ticket_is_rejected_even_if_worker_state_was_lost(self):
        ticket=self.ticket();ticket['prepared']['completion_commit']='d'*40
        service.signed(self.root,service.base(self.root)/'ticket.json',ticket)
        e=self.engine();e.completion=Mock(state={})
        e.app.state.return_value={**self.state,'epoch':4};e.tick()
        self.assertEqual(e.journal['error'],'stale_baseline')
        e.operator.apply.assert_not_called()

    def test_busy_and_newly_idle_host_not_updated(self):
        self.ticket();e=self.engine();e.idle.return_value=False;e.tick();self.assertIsNone(e.idle_since)
        e.idle.return_value=True;e.tick();self.assertEqual(e.idle_since,1000);e.operator.apply.assert_not_called()

    def test_live_ticket_and_completion_worker_do_not_compete_for_release_lock(self):
        self.ticket();e=self.engine();e.completion=Mock(state={},process=None)
        e.idle_since=940
        with patch.object(e,'transition',side_effect=lambda _:e.journal.update(phase='observing',target='a'*64,
                                                                                adopted_epoch=3,observe_until=1180)) as transition:
            e.completion.process=object()
            e.tick()
            transition.assert_not_called();e.completion.tick.assert_not_called()
            self.assertEqual(e.last_status,'waiting_for_independent_check_exit')
            e.completion.process=None;e.idle_since=940
            e.tick()
            transition.assert_called_once();e.completion.tick.assert_not_called()
            e.tick()
            e.completion.tick.assert_not_called()
            e.journal['ticket']='x'*32;e.clock=lambda:1180
            e.tick()
            e.completion.tick.assert_called_once();self.assertEqual(e.journal['phase'],'complete')

    def test_obsolete_completion_ticket_cannot_block_a_new_reviewed_commit(self):
        ticket=self.ticket();ticket['prepared']['completion_commit']='d'*40
        service.signed(self.root,service.base(self.root)/'ticket.json',ticket)
        e=self.engine();e.completion=Mock(state={'head':'e'*40,'status':'failed'},process=None)
        e.tick()
        e.completion.tick.assert_called_once()
        e.operator.apply.assert_not_called()
        self.assertEqual(e.last_status,'waiting_for_independent_check_exit')

    def test_expired_or_changed_baseline_before_stop(self):
        ticket=self.ticket();e=self.engine()
        for change in [{'expires':999},{'prepared':{**ticket['prepared'],'expected_epoch':2}},{'baseline':{**ticket['baseline'],'build':'c'*64}}]:
            with self.assertRaises(ValueError):e.transition({**ticket,**change})
        e.operator.apply.assert_not_called()

    def test_changed_source_before_transition_does_not_stop(self):
        ticket=self.ticket();e=self.engine();e.operator.require_prepared.side_effect=ValueError('Source changed')
        with self.assertRaises(ValueError):e.transition(ticket)
        e.operator.apply.assert_not_called()

    def test_disk_space_failure_precedes_apply(self):
        ticket=self.ticket();e=self.engine();e.app.approved.return_value={'path':str(self.base)}
        with patch.object(service,'require_compatible'),patch.object(service.shutil,'disk_usage',return_value=Mock(free=0)):
            with self.assertRaisesRegex(ValueError,'space'):e.transition(ticket)
        e.operator.apply.assert_not_called()

    def test_interrupted_transition_is_never_replayed(self):
        e=self.engine();e.journal.update(phase='applying',ticket='x'*32,target='b'*64,baseline=self.state['active']);e.tick()
        self.assertEqual(e.journal['phase'],'attention');e.operator.apply.assert_not_called()

    def test_success_enters_observation_and_completes(self):
        e=self.engine();e.journal.update(phase='observing',target='a'*64,adopted_epoch=3,observe_until=999);e.tick()
        self.assertEqual(e.journal['phase'],'complete');e.operator.apply.assert_not_called()

    def test_observation_does_not_rollback_other_update(self):
        e=self.engine();e.journal.update(phase='observing',target='b'*64,adopted_epoch=2,observe_until=999);e.tick()
        self.assertEqual(e.journal['phase'],'attention');e.app.adopt.assert_not_called()

    def test_late_crash_rolls_back_bound_baseline_and_quarantines(self):
        e=self.engine();target={**self.state,'epoch':4,'active':{'build':'b'*64,'epoch':4},'previous':self.state['active']}
        e.app.state.return_value=target;e.app.approved.return_value={'path':str(self.base)}
        e.app.adopt.return_value={**self.state,'epoch':5};e.driver.running.return_value=False
        e.journal.update(phase='observing',target='b'*64,adopted_epoch=4,baseline=self.state['active'],observe_until=2000)
        with patch.object(service,'require_compatible'):
            for _ in range(3):e.tick()
        e.app.adopt.assert_called_once_with('a'*64,e.driver,rollback=True,expected_epoch=4)
        self.assertEqual(e.journal['phase'],'quarantined');e.operator.start_daily.assert_not_called()

    def test_restarted_manager_keeps_observed_epoch_until_three_failures_rollback(self):
        e=self.engine();e.started=False
        target={**self.state,'epoch':4,'active':{'build':'b'*64,'epoch':4},'previous':self.state['active']}
        e.app.state.return_value=target;e.driver.running.return_value=False
        e.app.approved.return_value={'path':str(self.base)};e.app.adopt.return_value=copy.deepcopy(self.state)
        e.journal.update(phase='observing',target='b'*64,adopted_epoch=4,baseline=self.state['active'],observe_until=2000)
        with patch.object(service,'require_compatible'):
            for expected in (1,2):
                e.tick();self.assertEqual(e.bad,expected);e.app.adopt.assert_not_called();e.operator.start_daily.assert_not_called()
            e.tick()
        e.app.adopt.assert_called_once_with('a'*64,e.driver,rollback=True,expected_epoch=4)
        self.assertEqual(e.journal['phase'],'quarantined');e.operator.start_daily.assert_not_called()

    def test_incompatible_baseline_never_launched(self):
        e=self.engine();target={**self.state,'epoch':4,'active':{'build':'b'*64,'epoch':4},'previous':self.state['active']}
        e.app.state.return_value=target;e.app.approved.return_value={'path':str(self.base)}
        e.journal.update(target='b'*64,baseline=self.state['active'])
        with patch.object(service,'require_compatible',side_effect=CoreError('compatibility','unsupported')):
            with self.assertRaises(CoreError):e.rollback(target,'bad')
        e.app.adopt.assert_not_called()

    def test_queue_binds_signed_approved_package_and_cannot_replace_inflight(self):
        app=Applications(self.root);source=self.base/'source';(source/'apps/workbench').mkdir(parents=True)
        (source/'VERSION').write_text('v1');(source/'apps/workbench/server.py').write_text('# synthetic fixture')
        ident=build(source,['VERSION','apps/workbench/server.py'],self.base/'a.zip','v1');app.stage(self.base/'a.zip')
        app.validate(ident,lambda p:{'passed':True,'reviewed_source':True,'scope':'synthetic unit only'})
        current={**self.state,'active':{**self.state['active'],'build':ident}};app.save(current,'fixture-baseline')
        manifest=inspect_package(Path(app.record(ident)['path']))[1]
        prepared={'build':ident,'expected_epoch':3,'daily_data':str(self.root),'files':{n:v['sha256'] for n,v in manifest['files'].items()}}
        result=service.queue(self.root,self.dev,prepared);self.assertTrue(result['queued'])
        ticket=service.verified(self.root,service.base(self.root)/'ticket.json');self.assertEqual(ticket['prepared'],prepared)
        write_json(service.base(self.root)/'journal.json',{'ticket':ticket['id'],'phase':'applying'})
        with self.assertRaisesRegex(ValueError,'owns'):service.queue(self.root,self.dev,prepared)
        with self.assertRaises(ValueError):service.queue(self.root,self.dev,{**prepared,'files':{}})

    def test_installed_bootstrap_detects_modified_operator_before_import(self):
        from tools import workstation
        helper=self.base/'helper';helper.mkdir();(helper/'placeholder.py').write_text('# unit fixture')
        write_json(helper/'controller-files.json',{'placeholder.py':service.digest(helper/'placeholder.py')})
        with patch.object(workstation,'roots',return_value=(self.root,self.dev)),patch.object(workstation,'controller',return_value=(helper,18282)),patch('tools.workstation_completion.repository',return_value={'source':str(self.dev.parent),'head':'a'*40,'branch':'fixture'}):
            receipt=service.install(self.root,self.dev,self.base/'backups')
        bootstrap=Path(receipt['bootstrap']);compile(bootstrap.read_text(),str(bootstrap),'exec')
        capsule=service.base(self.root)/'capsules'/receipt['capsule'];(capsule/'operator.py').write_text('raise RuntimeError("must not execute")')
        import subprocess,sys
        result=subprocess.run([sys.executable,'-I','-B',str(bootstrap),'--once'],capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0);self.assertIn('Service changed',result.stderr)
        self.assertNotIn('must not execute',result.stderr)

    def test_completion_ticket_waits_for_confirmed_worker_exit(self):
        ticket=self.ticket();ticket['prepared']['completion_commit']='d'*40
        service.signed(self.root,service.base(self.root)/'ticket.json',ticket)
        e=self.engine();e.completion=Mock();e.completion.state={'head':'d'*40,'status':'checking'};e.tick()
        self.assertEqual(service.read(e.folder/'status.json')['status'],'waiting_for_independent_check_exit')
        e.operator.apply.assert_not_called()

    @unittest.skipUnless(os.name=='nt','Windows startup registry adapter')
    def test_startup_registration_roundtrip_preserves_owner_changes(self):
        import sys
        (self.root.parent/'JarvisService.py').write_text('# synthetic bootstrap')
        values={};fake=Mock();fake.HKEY_CURRENT_USER=1;fake.KEY_READ=2;fake.KEY_WRITE=4;fake.REG_SZ=1
        handle=Mock();handle.__enter__=Mock(return_value=handle);handle.__exit__=Mock(return_value=False)
        fake.CreateKeyEx.return_value=handle;fake.OpenKey.return_value=handle
        def get(key,name):
            if name not in values:raise FileNotFoundError()
            return values[name],1
        fake.QueryValueEx.side_effect=get
        fake.SetValueEx.side_effect=lambda key,name,reserved,kind,value:values.__setitem__(name,value)
        fake.DeleteValue.side_effect=lambda key,name:values.pop(name)
        with patch.dict(sys.modules,{'winreg':fake}),patch.dict(os.environ,{'LOCALAPPDATA':str(self.base/'local')}):
            receipt=service.register_startup(self.root);self.assertFalse(receipt['development_autostart'])
            self.assertEqual(receipt['scope'],'current-user-logon');self.assertIn('pythonw.exe',receipt['command'])
            compile(Path(receipt['shim']).read_text(),receipt['shim'],'exec')
            service.register_startup(self.root)
            self.assertIsNone(service.read(service.base(self.root)/'startup-backup.json')['previous'])
            values[receipt['name']]='owner edit'
            with self.assertRaisesRegex(ValueError,'changed'):service.unregister_startup(self.root)
            self.assertEqual(values[receipt['name']],'owner edit')
            values[receipt['name']]=receipt['command'];service.unregister_startup(self.root);self.assertEqual(values,{})


class NativeAutomationTests(unittest.TestCase):
    def test_actual_owned_candidate_exit_rolls_back_without_reverting_data(self):
        """Real local fixture processes; never stop a daily/development process."""
        import socket,time
        from tools import workstation
        with tempfile.TemporaryDirectory(prefix='jarvis-auto-fixture-') as directory:
            base=Path(directory).resolve();root=base/'daily/user-data';dev=base/'dev/user-data'
            Core.initialize(root).close();Core.initialize(dev).close();app=Applications(root)
            source_root=Path(__file__).resolve().parents[1]
            names=['control/application_runtime.py','control/credentials.py','control/atomic.py','control/paths.py',
                'control/recovery/gate.py','sdk/protocol.py']
            versions=[]
            for version in ('auto-fixture-v1','auto-fixture-v2'):
                source=base/version;(source/'apps/workbench').mkdir(parents=True)
                (source/'VERSION').write_text(version)
                (source/'apps/workbench/server.py').write_bytes((source_root/'tests/fixtures/application_host.py').read_bytes())
                import shutil
                for name in names:
                    path=source/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source_root/name,path)
                archive=base/(version+'.zip');ident=build(source,[*names,'VERSION','apps/workbench/server.py'],archive,version)
                app.stage(archive);app.validate(ident,lambda p:{'passed':True,'reviewed_source':True,'scope':'real process fixture, not product release approval'})
                versions.append(ident)
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            driver=WorkbenchProcess(root,port,timeout=3)
            sentinel=root/'state/owner-data.json';sentinel.write_text('{"revoked":true,"revision":7}')
            original=sentinel.read_bytes()
            from modules.mail.store import MailStore
            mail=MailStore(root)
            job=mail.job('fixture-safe-wait','read',{'message_id':'synthetic'})[0]
            original_wait=mail.update(job['id'],status='WAITING_NETWORK');mail.close()
            sample={'activity':{'drained':True},'counts':{'waiting':1,'running':0,'queued':0,'external':0,'unknown':0},
                    'items':[{'id':job['id'],'source':'mail','operation':'read','state':'waiting'}]}
            try:
                app.adopt(versions[0],driver)
                config={'schema':2,'enabled':True,'auto_updates':True,'daily_data':str(root),'development_data':str(dev),
                    'development_autostart':False,'backup_root':str(base/'backups'),'poll_seconds':3600,
                    'active_seconds':30,'offline_restart':False,'source_notification':True,'idle_seconds':60,
                    'observation_seconds':180,'restart_limit':3}
                service.base(root).mkdir(parents=True);service.signed(root,service.base(root)/'policy.json',config)
                baseline=copy.deepcopy(app.state()['active']);e=object.__new__(service.Engine)
                e.root=root;e.folder=service.base(root);e.config=config;e.app=app;e.driver=driver;e.clock=time.time
                e.started=True;e.bad=0;e.error_count=0;e.idle_since=None;e.port=port;e.operator=workstation
                e.journal={'phase':'idle','restarts':[]}
                now=[time.time()];e.clock=lambda:now[0]
                e.idle=lambda:service.quiet_for_handoff(root,sample)
                target=Path(app.record(versions[1])['path']);manifest=inspect_package(target)[1]
                prepared={'build':versions[1],'expected_epoch':app.state()['epoch'],'daily_data':str(root),
                    'source':str(base/'auto-fixture-v2'),'files':{n:v['sha256'] for n,v in manifest['files'].items()}}
                def source_check(actual_root,record):
                    self.assertEqual(record,prepared);self.assertEqual(app.state()['epoch'],record['expected_epoch'])
                    self.assertTrue(all(service.digest(Path(record['source'])/n)==sha for n,sha in record['files'].items()))
                def release(actual_root,action,*options):
                    if action=='status':return app.state()
                    if action=='adopt':return app.adopt(options[1],driver,expected_epoch=options[3])
                    if action=='install-launcher':return {'scope':'fixture keeps its original launcher'}
                    raise AssertionError(action)
                ticket={'id':'synthetic-native','daily_data':str(root),'development_data':str(dev),
                    'prepared':prepared,'baseline':baseline,'expires':time.time()+600}
                # Only controller CLI transport and source Git inventory are
                # adapted to this Git-free fixture; real stop/backup/adopt/health.
                with patch.object(workstation,'controller',return_value=(base,port)),patch.object(workstation,'require_prepared',side_effect=source_check),patch.object(workstation,'release',side_effect=release),patch.object(workstation,'start_daily',side_effect=lambda root:driver.health(app.state()['active'],app.state()['epoch'])):
                    service.signed(root,service.base(root)/'ticket.json',ticket)
                    e.tick();self.assertEqual(e.idle_since,now[0])
                    now[0]+=60;e.tick()
                adopted=app.state();self.assertEqual(e.journal['phase'],'observing')
                backup=Path(json.loads((dev/'state/workstation-last-update.json').read_text())['backup']['folder'])
                self.assertEqual((backup/'state/owner-data.json').read_bytes(),original)
                # Exactly the child fixture created by this test. No PID guessing.
                child=driver.processes[adopted['epoch']];child.terminate();child.wait(timeout=5)
                for _ in range(3):e.tick()
                self.assertEqual(app.state()['active']['build'],versions[0]);self.assertEqual(e.journal['phase'],'quarantined')
                self.assertEqual(sentinel.read_bytes(),original);driver.health(app.state()['active'],app.state()['epoch'])
                for data in (root,backup):
                    mail=MailStore(data)
                    try:self.assertEqual(mail.get(job['id']),original_wait)
                    finally:mail.close()
                self.assertEqual(e.journal['failed_build'],versions[1])
                # Once observation has ended, an ordinary missing daily process
                # is not an invitation to inspect Git or start the application.
                restored=app.state();child=driver.processes[restored['epoch']]
                child.terminate();child.wait(timeout=5);e.completion=Mock(state={})
                e.tick(check_source=True)
                self.assertEqual(service.read(service.base(root)/'status.json')['status'],'offline_no_update_checks')
                e.completion.tick.assert_not_called();e.completion.poll.assert_not_called()
                self.assertFalse(driver.running(restored['active'],restored['epoch']))
                self.assertEqual(sentinel.read_bytes(),original)
            finally:
                current=app.state()
                if current['phase']=='active':app.stop(driver)
                # A second controller can stop an old fixture host; reap every
                # exact child we created, including those stopped over HTTP.
                for child in driver.processes.values():child.wait(timeout=5)


if __name__=='__main__':unittest.main()
