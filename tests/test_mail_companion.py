"""Companion account isolation, real counts, read-only sync and boundary tests."""
import copy
import tempfile
import time
import unittest
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
from pathlib import Path
from unittest.mock import patch

from host.core import Core
from host.mailbox import Mailbox
from modules.mail.store import MailStore
from modules.mail.companion import project
from sdk.mail import READ,MODIFY,classify
from sdk.protocol import CoreError
from adapters.mail.google import Gmail

CREDS={'client_id':'test.apps.googleusercontent.com','client_secret':'fixture-secret','access_token':'fixture-access',
       'refresh_token':'fixture-refresh','scope':READ+' '+MODIFY,'expires_at':time.time()+3600}
MAIL={'id':'m1','from':'friend@example.com','subject':'会议安排','date':'today','snippet':'hello',
      'labels':['INBOX','UNREAD'],'body':'private-body-not-in-projection','thread_id':'t1'}


def account(generation='g1'):
    return {'generation':generation,'email':'owner@example.com','credentials':CREDS,'health':'connected','checked_at':100}


def job(generation='g1',operation='sync'):
    return {'id':'job-fixture','generation':generation,'status':'SUCCEEDED','operation':operation,'updated':101,
            'payload':{'query':'in:inbox','page':''},'result':{'messages':[MAIL],'next_page':'more',
            'counts':{'messagesUnread':317}}}


class FakeGmail:
    writes=0
    def __init__(self,credentials,guard):self.credentials=copy.deepcopy(credentials);self.guard=guard
    def refresh(self):self.guard();return self.credentials
    def listing(self,query,page):self.guard();return {'messages':[copy.deepcopy(MAIL)],'next_page':'more'}
    def inbox_counts(self):return {'messagesTotal':500,'messagesUnread':317,'threadsTotal':400,'threadsUnread':200}


class CompanionProjectionTests(unittest.TestCase):
    def project(self,**kwargs):
        defaults=dict(account=account(),configured=True,jobs=[job()],rules=[],messages=[],authorization={},network_blocked=False,now=110)
        return project(**(defaults|kwargs))
    def test_exact_count_does_not_count_only_the_ten_message_sample(self):
        result=self.project();self.assertEqual(result['unread_count'],317);self.assertEqual(result['sample_unread_count'],1)
        self.assertEqual(result['count_scope'],'inbox_messages');self.assertTrue(result['has_more'])
    def test_never_returns_credentials_body_drafts_or_oauth_url(self):
        result=self.project(authorization={'status':'WAITING_BROWSER','url':'secret-auth-url','future':object()})
        self.assertNotIn('url',result['authorization']);self.assertNotIn('body',result['items'][0])
        self.assertNotIn('credentials',result);self.assertNotIn('fixture-secret',str(result))
    def test_changed_account_hides_old_cached_mail(self):
        self.assertEqual(self.project(account=account('g2'))['items'],[])
        self.assertIsNone(self.project(account=account('g2'))['unread_count'])
    def test_unknown_count_is_not_faked_as_zero(self):
        result=self.project(jobs=[job(operation='list')]);self.assertIsNone(result['unread_count'])
        self.assertEqual(result['count_scope'],'cached_sample')
    def test_authorization_expiry_and_old_checks_never_show_connected(self):
        self.assertEqual(self.project(account=account()|{'health':'auth_required'})['status'],'auth_required')
        self.assertEqual(self.project(now=500)['status'],'unchecked')
        self.assertEqual(self.project(network_blocked=True)['status'],'offline')
    def test_uses_corrected_cache_labels_and_owner_rule(self):
        cached={'account_generation':'g1','message':MAIL|{'labels':['INBOX']}}
        result=self.project(messages=[cached],rules=[{'id':'r1','sender':'friend@example.com','category':'promotion'}])
        self.assertFalse(result['items'][0]['unread']);self.assertEqual(result['items'][0]['classification']['category'],'promotion')
        archived={'account_generation':'g1','message':MAIL|{'labels':[]}}
        self.assertEqual(self.project(messages=[archived])['items'],[])
    def test_sent_or_paginated_queries_do_not_become_inbox(self):
        for payload in ({'query':'in:sent','page':''},{'query':'in:inbox','page':'page2'}):
            self.assertEqual(self.project(jobs=[job()|{'payload':payload}])['items'],[])
    def test_receipts_are_attention_candidates_and_promotion_labels_are_used(self):
        self.assertEqual(classify(MAIL|{'subject':'Your receipt from Example','snippet':''})['category'],'important')
        self.assertEqual(classify(MAIL|{'subject':'消费成功','snippet':''})['category'],'important')
        self.assertEqual(classify(MAIL|{'subject':'Newsletter','labels':['CATEGORY_PROMOTIONS']})['category'],'promotion')


class CompanionMailboxTests(unittest.TestCase):
    def test_sync_and_cached_projection_use_no_model_and_do_not_write_to_google(self):
        with tempfile.TemporaryDirectory(prefix='jarvis-mail-companion-') as temp:
            root=Path(temp);Core.initialize(root).close();store=MailStore(root)
            try:
                with store.transaction():store.put(account()|{'id':'account','kind':'account'},0)
            finally:store.close()
            box=Mailbox(root,gmail_factory=FakeGmail)
            try:
                row=box.command({'action':'job','request_id':'companion-sync-fixture','operation':'sync','payload':{'query':'in:inbox','page':''}})
                end=time.monotonic()+5
                while time.monotonic()<end:
                    result=box.command({'action':'detail','id':row['id']})
                    if result['status'] not in {'READY','RUNNING'}:break
                    time.sleep(.01)
                self.assertEqual(result['status'],'SUCCEEDED',result)
                with patch.object(box,'gmail_factory',side_effect=AssertionError('Projection contacted Google')):
                    overview=box.companion()
                self.assertEqual(overview['unread_count'],317);self.assertEqual(FakeGmail.writes,0)
                self.assertNotIn('private-body-not-in-projection',str(overview))
                with self.assertRaises(CoreError):
                    box.command({'action':'job','request_id':'wrong-sync-scope','operation':'sync','payload':{'query':'in:sent','page':''}})
            finally:box.close()
    def test_google_inbox_counts_are_bounded_read_request(self):
        api=Gmail(CREDS,lambda:None)
        with patch.object(api,'api',return_value={'messagesTotal':20,'messagesUnread':12,'threadsTotal':15,'threadsUnread':10}) as call:
            self.assertEqual(api.inbox_counts()['messagesUnread'],12);call.assert_called_once_with('/labels/INBOX')
        with patch.object(api,'api',return_value={'messagesTotal':True}):
            with self.assertRaises(CoreError):api.inbox_counts()
    def test_companion_http_requires_existing_owner_access_and_serves_external_assets(self):
        from apps.workbench.server import Handler
        from control.local_access import LocalAccess,cookie_name
        with tempfile.TemporaryDirectory(prefix='jarvis-mail-http-') as temp:
            root=Path(temp);Core.initialize(root).close()
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=root;server.nonce='fixture-page-nonce'
            server.access=LocalAccess(root,key='fixture-key-'+('a'*32))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def get(path,cookie=''):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                connection.request('GET',path,headers={'Cookie':cookie});response=connection.getresponse();data=response.read();status=response.status;connection.close();return status,data
            try:
                status,_=get('/api/mail/companion');self.assertEqual(status,401)
                token=server.access.unlock('fixture-key-'+('a'*32));cookie=cookie_name(server.server_port)+'='+token
                status,data=get('/api/mail/companion',cookie);self.assertEqual(status,200)
                self.assertEqual(json.loads(data)['items'],[])
                status,data=get('/companion',cookie);self.assertEqual(status,200)
                self.assertIn(b'type="module" src="/companion-shell.js"',data)
                self.assertNotIn(b'<script>',data)
            finally:
                server.shutdown();server.server_close();thread.join()
                if hasattr(server,'mailbox'):server.mailbox.close()


if __name__=='__main__':unittest.main()
