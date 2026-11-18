"""Push hints are not approvals; passive time and active recovery stay separate."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from host.core import Core
from control.application_runtime import LocalApprovals
from control.recovery.gate import StopGate
from sdk.protocol import CoreError
from tools import workstation_service as service


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'daily/user-data';self.source=self.base/'dev'
        Core.initialize(self.root).close();LocalApprovals(self.root).initialize()
        self.config={'schema':2,'enabled':True,'auto_updates':True,'daily_data':str(self.root),
            'development_data':str(self.source/'user-data'),'development_autostart':False,
            'backup_root':str(self.base/'backups'),'poll_seconds':3600,'active_seconds':30,
            'offline_restart':False,'source_notification':True,'idle_seconds':60,'observation_seconds':180,
            'restart_limit':3,'completion':{'source':str(self.source),'enabled':True}}
        service.base(self.root).mkdir(parents=True,exist_ok=True)
        service.signed(self.root,service.base(self.root)/'policy.json',self.config)
        self.now=1000;self.schedule=service.Schedule(clock=lambda:self.now)
        self.engine=Mock(journal={'phase':'complete'},completion=None,last_status='ready',source_inspected=True)

    def request(self,**patch_value):
        value={'schema':1,'id':'a'*32,'source':str(self.source),'created':self.now,**patch_value}
        service.signed(self.root,service.base(self.root)/'notification.json',value)

    def test_reviewed_candidate_rechecks_at_budget_reset(self):
        self.engine.completion=Mock(state={'status':'daily_check_limit','next_check_at':1045},process=None)
        self.engine.source_inspected=True
        self.schedule.after_tick(self.engine,True)
        self.assertEqual(self.schedule.delay(self.engine),45)

    def test_passive_source_inspection_is_hourly_not_every_health_tick(self):
        for offset in (0,30,60,120,3599):
            self.now=1000+offset;self.assertFalse(self.schedule.source_due(self.root))
        self.assertEqual(self.schedule.delay(self.engine),1)
        self.now=4600;self.assertTrue(self.schedule.source_due(self.root))
        self.assertFalse(self.schedule.source_due(self.root));self.assertEqual(self.schedule.delay(self.engine),3600)

    def test_signed_notification_wakes_before_hour_and_is_consumed_once(self):
        self.request();self.assertTrue(self.schedule.source_due(self.root))
        self.assertFalse(self.schedule.source_due(self.root))
        self.request(id='b'*32);self.assertTrue(self.schedule.source_due(self.root))

    def test_unsigned_or_wrong_source_notification_does_not_authorize_a_check(self):
        self.request(source=str(self.base/'other'))
        with self.assertRaises(ValueError):self.schedule.source_due(self.root)
        path=service.base(self.root)/'notification.json';value=json.loads(path.read_text())
        value['value']['source']=str(self.source);path.write_text(json.dumps(value))
        with self.assertRaises(CoreError):self.schedule.source_due(self.root)

    def test_expired_hint_does_not_replay_after_restart(self):
        self.request(created=self.now-86401)
        self.assertFalse(self.schedule.source_due(self.root))

    def test_quiet_commit_has_one_due_timer_not_repeated_source_polls(self):
        self.engine.completion=Mock(process=None,state={'status':'waiting_for_quiet_snapshot','stable_since':1000})
        self.schedule.after_tick(self.engine,True);self.assertEqual(self.schedule.delay(self.engine),120)
        self.now=1030;self.assertFalse(self.schedule.source_due(self.root))
        self.now=1120;self.assertTrue(self.schedule.source_due(self.root))

    def test_source_hint_waits_through_owned_transition_then_rechecks(self):
        self.engine.ticket_pending=True
        self.engine.journal={'phase':'observing'};self.engine.last_status='observing'
        self.schedule.after_tick(self.engine,True)
        self.assertIsNone(self.schedule.source_at)
        self.assertEqual(self.schedule.delay(self.engine),30)
        self.now+=180
        self.engine.ticket_pending=False
        self.engine.journal={'phase':'complete'};self.engine.last_status='ready'
        self.schedule.after_tick(self.engine,False)
        self.now+=1
        self.assertTrue(self.schedule.source_due(self.root))
        self.assertFalse(self.schedule.source_due(self.root))

    def test_offline_cancels_pending_source_timer(self):
        self.schedule.source_at=1100;self.engine.last_status='offline_no_update_checks'
        self.schedule.after_tick(self.engine,True)
        self.assertIsNone(self.schedule.source_at);self.assertEqual(self.schedule.delay(self.engine),3600)

    def test_short_timer_is_confined_to_owned_operation(self):
        self.assertEqual(self.schedule.delay(self.engine),3600)
        self.engine.journal={'phase':'observing'};self.assertEqual(self.schedule.delay(self.engine),30)
        self.engine.journal={'phase':'complete'};self.engine.completion=Mock(process=object())
        self.assertEqual(self.schedule.delay(self.engine),30)
        self.engine.completion.process=None;self.engine.last_status='waiting_for_idle'
        self.engine.idle_since=None;self.assertEqual(self.schedule.delay(self.engine),3600)
        self.engine.idle_since=1000;self.assertEqual(self.schedule.delay(self.engine),60)

    def test_waiting_unknown_check_result_has_no_fast_timer(self):
        self.engine.last_status='waiting_for_independent_check_exit';self.engine.completion=Mock(process=None)
        self.assertEqual(self.schedule.delay(self.engine),3600)

    def test_external_maintenance_does_not_rearm_a_stale_quiet_timer(self):
        self.engine.source_inspected=False;self.engine.last_status='maintenance_owned_elsewhere'
        self.engine.completion=Mock(process=None,state={'status':'waiting_for_quiet_snapshot','stable_since':800})
        self.schedule.after_tick(self.engine,True)
        self.assertIsNone(self.schedule.source_at);self.assertEqual(self.schedule.delay(self.engine),3600)

    def test_notifier_never_starts_manager_or_daily_when_event_is_absent(self):
        with patch.object(service,'signal',return_value=False),patch.object(service.subprocess,'Popen') as spawn:
            self.assertFalse(service.notify_completion(self.root)['notified']);spawn.assert_not_called()

    def test_stop_and_disabled_policy_suppress_notification(self):
        StopGate(self.root).stop()
        with patch.object(service,'signal') as signal:
            self.assertFalse(service.notify_completion(self.root)['notified']);signal.assert_not_called()
        service.signed(self.root,service.base(self.root)/'policy.json',{**self.config,'enabled':False})
        self.assertEqual(service.notify_completion(self.root)['reason'],'disabled')

    @unittest.skipUnless(service.os.name=='nt','Windows kernel event')
    def test_real_event_wake_is_auto_reset_and_does_not_require_a_console(self):
        wake=service.WakeSignal(self.root)
        try:
            self.assertFalse(wake.wait(.01));self.assertTrue(service.signal(self.root))
            self.assertTrue(wake.wait(.01));self.assertFalse(wake.wait(.01))
        finally:wake.close()
        self.assertFalse(service.signal(self.root))

    def test_hook_preserves_owner_file_and_custom_hook_configuration(self):
        hooks=self.source/'.git/hooks';hooks.mkdir(parents=True);hook=hooks/'post-commit';hook.write_text('# owner hook')
        with patch.object(service,'load_completion') as completion,patch.object(service.subprocess,'run',return_value=Mock(returncode=1)):
            with self.assertRaisesRegex(ValueError,'owner post-commit'):service.register_notification(self.root)
        self.assertEqual(hook.read_text(),'# owner hook')
        with patch.object(service,'load_completion'),patch.object(service.subprocess,'run',return_value=Mock(returncode=0)):
            with self.assertRaisesRegex(ValueError,'custom Git hooks'):service.register_notification(self.root)

    @unittest.skipUnless(service.os.name=='nt','Windows pythonw notification hook')
    def test_hook_pins_existing_service_and_contains_no_git_or_start_command(self):
        (self.source/'.git/hooks').mkdir(parents=True);(self.root.parent/'JarvisService.py').write_text('# pinned fixture')
        with patch.object(service,'load_completion'),patch.object(service.subprocess,'run',return_value=Mock(returncode=1)):
            receipt=service.register_notification(self.root)
        text=Path(receipt['path']).read_text();self.assertIn('pythonw.exe',text);self.assertIn('--notify-completion',text)
        self.assertNotIn('git ',text);self.assertNotIn('--logon-start',text)
        self.assertEqual(receipt['sha256'],service.digest(Path(receipt['path'])))


if __name__=='__main__':unittest.main()
