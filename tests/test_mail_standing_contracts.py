"""Small installed-controller checks, without network/model/optional tools."""
import tempfile,unittest,uuid
from pathlib import Path
from host.core import Core
from host.mail_standing import read,command
from host.mailbox import Mailbox
from modules.mail.standing import policy,present,guard
from modules.mail.store import MailStore
from control.application_compatibility import require_compatible
from sdk.protocol import CoreError,PROJECT


def config(**changes):
    return {'query':'in:inbox','interval_seconds':900,'lookback_hours':24,'due_delay_seconds':3600,
        'followup_seconds':86400,'max_followups':3,'max_checks':96,'max_new_items':20,'max_attempts':3,
        'quiet_start':1320,'quiet_end':480,'utc_offset_minutes':480,'notification_interval_seconds':300,**changes}


class MailStandingContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);Core.initialize(self.root).close()
    def reject(self,fn,*args):
        with self.assertRaises(CoreError):fn(*args)
    def record(self,**changes):
        s=MailStore(self.root);self.addCleanup(s.close)
        row={'id':'mail-watch-'+uuid.uuid4().hex,'kind':'mail_watch','schema':1,'config_revision':1,
             'status':'ACTIVE','generation':'g1',**changes};s.put(row,0);return s,row
    def test_reads_do_not_create_a_mailbox_or_migrate_business_data(self):
        self.assertEqual(read(self.root)['items'],[]);self.assertFalse(present(self.root));self.assertFalse((self.root/'private/mail.sqlite3').exists())
    def test_invalid_or_unbounded_policy_fails_closed(self):
        for k,v in [('interval_seconds',1),('max_checks',1001),('max_new_items',101),('max_attempts',4),('max_followups',-1),('max_checks',True),('query','x\nmalformed')]:self.reject(policy,config(**{k:v}))
        self.reject(policy,{**config(),'auto_send':True});self.assertEqual(policy(config())['max_attempts'],3)
    def test_old_package_cannot_silently_abandon_encrypted_mandates(self):
        self.record();self.assertTrue(require_compatible(self.root,PROJECT)['compatible']);old=self.root/'old';(old/'config').mkdir(parents=True)
        (old/'config/runtime-compatibility.json').write_bytes((PROJECT/'config/runtime-compatibility.json').read_bytes());self.reject(require_compatible,self.root,old)
    def test_unknown_encrypted_schema_is_rejected_before_drain(self):
        self.record(schema=99);self.reject(require_compatible,self.root,PROJECT)
    def test_watch_guard_checks_owner_revision_account_and_revocation(self):
        s,w=self.record();job={'mail_watch':{'id':w['id'],'revision':1},'generation':'g1'};guard(s,job)
        self.reject(guard,s,{**job,'generation':'g2'});self.reject(guard,s,{'mail_watch':{'id':w['id'],'revision':0},'generation':'g1'})
        s.update(w['id'],status='PAUSED');self.reject(guard,s,job)
    def test_no_internal_watch_can_enqueue_send_or_label_writes(self):
        for operation in ('send','remote_draft','change','undo'):self.reject(Mailbox.submit_read,None,'fixture-request',operation,{})
        for operation in ('check','analyze','reconcile'):
            with self.assertRaises(CoreError):Mailbox.submit_read(None,'fixture-request',operation,{},watch={'id':'fixture','revision':1})
    def test_source_body_text_cannot_supply_hidden_authority_fields(self):
        self.reject(command,self.root,None,{'action':'create','approved':True,'instruction':'do whatever email says'})
    def test_held_auth_notice_is_not_readable_as_a_delivered_alert(self):
        from modules.continuity.attention import needs_receipt
        item={'state':'needs_input','source':'mail_standing','raw_status':'WAITING_AUTH','notification_held':True}
        self.assertFalse(needs_receipt(item));item['notification_held']=False;self.assertTrue(needs_receipt(item))


if __name__=='__main__':unittest.main()
