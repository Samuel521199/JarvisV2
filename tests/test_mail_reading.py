"""Cached reading, exact write approval and zero-token local filing; synthetic mail only."""
import copy,tempfile,time,unittest
from pathlib import Path
from control.network import NetworkGate
from host.core import Core
from host.mailbox import Mailbox
from modules.mail.store import MailStore
from sdk.mail import classify
from sdk.protocol import CoreError
from test_mailbox import FakeGmail,CREDS
import test_mailbox as mailbox_fixture


class ReadingGmail(FakeGmail):
    def read(self,ident,full=True):
        value=super().read(ident,full)
        if not full:value.pop('body',None)
        return value
    def inbox_counts(self):
        self.guard();return {'messagesUnread':sum('UNREAD' in labels and 'INBOX' in labels and not {'TRASH','SPAM'}&set(labels) for labels in self.labels.values())}


class ReadingTests(unittest.TestCase):
    job=mailbox_fixture.MailboxTests.job
    wait=mailbox_fixture.MailboxTests.wait
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        Core.initialize(self.root).close();FakeGmail.labels={'m1':['INBOX','UNREAD'],'m2':['INBOX','UNREAD']};FakeGmail.fail=None;FakeGmail.delay=None
        self.api_calls=0
        def factory(*args):self.api_calls+=1;return ReadingGmail(*args)
        self.box=Mailbox(self.root,gmail_factory=factory);self.addCleanup(self.box.close)
        s=MailStore(self.root)
        try:
            with s.transaction():s.put({'id':'account','kind':'account','email':'owner@example.com','credentials':copy.deepcopy(CREDS),'generation':'g1','health':'connected','checked_at':time.time()},0)
        finally:s.close()

    def test_full_cached_body_is_readable_offline_without_remote_call_or_read_effect(self):
        self.wait(self.job('read',{'message_id':'m1'})['id'],'SUCCEEDED');before=self.api_calls
        gate=NetworkGate(self.root);gate.update({'revision':gate.read()['revision'],'blocked':True})
        detail=self.box.command({'action':'cached_message','message_id':'m1'})
        self.assertEqual(detail['body'],'Private fixture content');self.assertTrue(detail['source_digest']);self.assertEqual(self.api_calls,before)
        self.assertIn('UNREAD',FakeGmail.labels['m1'])

    def test_reading_preference_is_display_choice_and_never_bypasses_exact_approval(self):
        self.box.command({'action':'view_preferences','revision':0,'mark_read_on_open':True,'account_generation':'g1'})
        self.assertTrue(self.box.state()['view_preferences']['mark_read_on_open']);self.assertEqual(self.api_calls,0)
        with self.assertRaises(CoreError):self.job('change',{'message_id':'m1','change':'read'})
        self.assertIn('UNREAD',FakeGmail.labels['m1'])

    def test_account_change_does_not_reactivate_reading_choice_or_old_cache(self):
        self.wait(self.job('read',{'message_id':'m1'})['id'],'SUCCEEDED')
        self.box.command({'action':'view_preferences','revision':0,'mark_read_on_open':True,'account_generation':'g1'})
        s=MailStore(self.root)
        try:s.update('account',generation='g2')
        finally:s.close()
        self.assertFalse(self.box.state()['view_preferences']['mark_read_on_open'])
        for command in ({'action':'cached_message','message_id':'m1'},{'action':'view_preferences','revision':1,'mark_read_on_open':True,'account_generation':'g1'}):
            with self.assertRaises(CoreError):self.box.command(command)

    def test_title_rules_are_correctable_local_hints_without_body_upload(self):
        result=self.box.command({'action':'folder_rule','id':'','revision':0,'field':'subject','pattern':'口语','folder':'我的英语','priority':80,'enabled':True,'account_generation':'g1'})
        rules=self.box.state()['rules'];mail={'subject':'英语口语练习提醒','from':'teacher@example.com','snippet':''}
        self.assertEqual(classify(mail,rules)['folder'],'我的英语');self.assertEqual(classify(mail,rules)['model_tokens'],0)
        self.box.command({'action':'remove_rule','id':result['id'],'revision':result['revision']})
        self.assertEqual(classify(mail,self.box.state()['rules'])['folder'],'学习成长');self.assertEqual(self.api_calls,0)

    def test_folder_assignment_does_not_assert_trust(self):
        rule={'id':'r','kind':'folder_rule','field':'subject','pattern':'验证密码','folder':'个人','priority':80,'enabled':True}
        result=classify({'subject':'验证密码','from':'noreply@example.com'},[rule])
        self.assertEqual(result['folder'],'个人');self.assertEqual(result['category'],'suspicious')

    def test_reviewed_read_updates_count_and_trash_is_undoable(self):
        self.wait(self.job('sync',{'query':'in:inbox','page':''})['id'],'SUCCEEDED')
        def change(name):
            review=self.box.command({'action':'review','operation':'change','payload':{'message_id':'m1','change':name}})
            job=self.box.command({'action':'approve','review_id':review['id'],'request_id':'review-'+str(time.time_ns())})
            return self.wait(job['id'],'SUCCEEDED')
        change('read');self.wait(self.job('counts',{})['id'],'SUCCEEDED')
        self.assertEqual(self.box.companion()['unread_count'],1)
        trash=change('trash');self.assertEqual(self.box.companion()['items'],[])
        review=self.box.command({'action':'review','operation':'undo','payload':{'job_id':trash['id']}})
        self.wait(self.box.command({'action':'approve','review_id':review['id'],'request_id':'undo-reviewed-fixture'})['id'],'SUCCEEDED')
        self.assertNotIn('TRASH',FakeGmail.labels['m1']);self.assertNotIn('UNREAD',FakeGmail.labels['m1'])


if __name__=='__main__':unittest.main()
