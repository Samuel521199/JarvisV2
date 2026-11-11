"""Small independent-controller checks; no optional worker/model installation."""
import tempfile,time,unittest,json,uuid
from pathlib import Path
from host.core import Core
from host import standing_work
from modules.task_resource.standing import Standing,policy,timestamp,quiet,acceptance
from control.application_compatibility import require_compatible
from sdk.protocol import CoreError,PROJECT


def policy_fixture(**changes):
    return {'start_at':'2026-11-10T12:00:00+08:00','interval_seconds':3600,'max_runs':3,'max_action_units':20,
        'max_attempts':3,'quiet_start':1320,'quiet_end':480,'utc_offset_minutes':480,'notification_interval_seconds':60,
        'cloud_model_budget_usd':0,**changes}


class StandingContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.core=Core.initialize(self.root);self.addCleanup(self.core.close)
    def rejected(self,fn,*args):
        with self.assertRaises(CoreError):fn(*args)
    def test_time_and_paid_or_unbounded_policy_rejected(self):
        for value in ('tomorrow','2026-11-10T10:00','2026-11-10T10:00:00','2026-02-30T10:00:00Z'):self.rejected(timestamp,value)
        for key,value in [('max_attempts',4),('max_runs',101),('max_action_units',1001),('interval_seconds',1),('cloud_model_budget_usd',1),('cloud_model_budget_usd',float('nan')),('max_runs',True)]:self.rejected(policy,policy_fixture(**{key:value}))
        self.assertEqual(policy(policy_fixture())['cloud_model_budget_usd'],0)
    def test_no_implicit_migration_on_view(self):
        self.assertEqual(standing_work.read(self.root)['items'],[])
        self.assertIsNone(self.core.db.one("SELECT * FROM meta WHERE key='standing_schema'"))
    def test_paused_draft_cannot_resume_as_an_initial_grant(self):
        store=Standing(self.core.db);ident='standing-'+uuid.uuid4().hex
        store.put({'id':ident,'revision':1,'status':'DRAFT','granted':False})
        paused=standing_work.command(self.root,{'action':'pause','request_id':uuid.uuid4().hex,'id':ident,'revision':1})
        self.rejected(standing_work.command,self.root,{'action':'resume','request_id':uuid.uuid4().hex,'id':ident,'revision':paused['revision']})
        self.assertFalse(store.get(ident)['granted'])
    def test_unknown_store_schema_and_legacy_package_fail_closed(self):
        Standing(self.core.db);self.assertTrue(require_compatible(self.root,PROJECT)['compatible'])
        self.rejected(require_compatible,self.root,self.root/'absent-package')
        self.core.db.connection.execute("UPDATE meta SET value='999' WHERE key='standing_schema'");self.rejected(Standing,self.core.db)
    def test_no_command_or_acceptance_field_can_smuggle_external_authority(self):
        before=self.core.db.all('SELECT * FROM grants')
        self.rejected(standing_work.command,self.root,{'action':'create','approved':True})
        bad={'coverage':'complete','criteria':[{'id':'x','step_id':'step-1','check':'shell','expected':'anything'}],'requirements':[]}
        self.rejected(acceptance,bad,[{'capability':'plugin.local.v1'}])
        self.assertEqual(self.core.db.all('SELECT * FROM grants'),before)
    def test_quiet_midnight_and_disabled_window(self):
        self.assertTrue(quiet(policy_fixture(),timestamp('2026-11-10T23:10:00+08:00')))
        self.assertFalse(quiet(policy_fixture(),timestamp('2026-11-10T08:00:00+08:00')))
        self.assertFalse(quiet(policy_fixture(quiet_start=0,quiet_end=0),time.time()))
    def test_notification_held_is_not_acknowledgeable(self):
        from modules.continuity.attention import Attention
        row={'source':'standing','id':'s','state':'finished','notification_held':True};store=Attention(self.root)
        try:
            store.project([row]);self.assertFalse(row['attention']['unread']);self.rejected(store.acknowledge,row,row['attention']['version'])
            row['notification_held']=False;store.project([row]);self.assertTrue(row['attention']['unread'])
        finally:store.close()

    def test_development_model_gate_does_not_open_general_external_access(self):
        from control.network import NetworkGate
        profile={'schema':1,'kind':'development','external_actions':False,'client_id':uuid.uuid4().hex,'bridge_origin':'http://127.0.0.1:18482','allowed_providers':['google']}
        (self.root/'config/development.json').write_text(json.dumps(profile),encoding='utf-8');gate=NetworkGate(self.root)
        self.rejected(gate.require_online);gate.require_model_online()
        gate.update({'revision':gate.read()['revision'],'blocked':True});self.rejected(gate.require_model_online)

if __name__=='__main__':unittest.main()
