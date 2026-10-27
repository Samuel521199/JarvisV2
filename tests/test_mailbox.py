"""Gmail review, reauthorization, isolation and unknown-effect tests; no real mail writes."""
import base64
import copy
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from host.core import Core
from host.mailbox import Mailbox
from modules.mail.store import MailStore
from sdk.mail import READ,MODIFY,COMPOSE,capabilities,message,encoded_message,classify
from sdk.protocol import CoreError
from adapters.mail.oauth import authorize
from adapters.mail.google import token_result,Gmail
from apps.workbench.server import Handler

CREDS={'client_id':'test-client.apps.googleusercontent.com','client_secret':'fixture-secret','access_token':'fixture-access','refresh_token':'fixture-refresh','expires_at':time.time()+3600,'scope':READ+' '+MODIFY}


class FakeGmail:
    sent=[];labels={'m1':['INBOX','UNREAD']};fail=None;delay=None
    def __init__(self,c,guard):self.credentials=copy.deepcopy(c);self.guard=guard
    def refresh(self,force=False):
        self.guard()
        if self.fail=='auth':raise CoreError('mail_auth_required','fixture')
        return self.credentials
    def profile(self):self.guard();return {'email':'owner@example.com','messages_total':1}
    def read(self,ident,full=True):
        self.guard();return {'id':ident,'subject':'Fixture message','from':'friend@example.com','to':'owner@example.com','date':'today','labels':list(self.labels[ident]),'snippet':'hello','body':'Private fixture content'}
    def listing(self,query='',page=''):return {'messages':[self.read('m1',False)],'next_page':''}
    def modify(self,ident,remove,add):
        self.guard();self.labels[ident]=list((set(self.labels[ident])-set(remove))|set(add))
        return self.read(ident,False)
    def trash(self,ident,undo=False):return self.modify(ident,['TRASH'] if undo else [],[] if undo else ['TRASH'])
    def send(self,raw,as_draft=False):
        self.guard();self.sent.append(raw)
        if self.delay:self.delay()
        if self.fail=='unknown':raise CoreError('mail_network','fixture timeout after sending')
        return {'remote_id':'remote1','message_id':'m1'}


class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='jarvis-mail-');self.root=Path(self.tmp.name)
        Core.initialize(self.root).close();FakeGmail.sent=[];FakeGmail.labels={'m1':['INBOX','UNREAD']};FakeGmail.fail=None;FakeGmail.delay=None
        self.box=Mailbox(self.root,gmail_factory=FakeGmail,oauth=lambda *a,**k:copy.deepcopy(CREDS))
        s=MailStore(self.root)
        try:
            with s.transaction():
                s.put({'id':'client','kind':'client','configuration':{k:CREDS[k] for k in ['client_id','client_secret']}},0)
                s.put({'id':'account','kind':'account','email':'owner@example.com','credentials':copy.deepcopy(CREDS),'generation':'fixture-generation','health':'unchecked'},0)
        finally:s.close()
    def tearDown(self):self.box.close();self.tmp.cleanup()
    def code(self,code,fn,*args,**kwargs):
        with self.assertRaises(CoreError) as e:fn(*args,**kwargs)
        self.assertEqual(e.exception.code,code)
    def job(self,op,payload,request_id=None):return self.box.command({'action':'job','operation':op,'payload':payload,'request_id':request_id or 'request-'+str(time.time_ns())})
    def wait(self,ident,status=None):
        end=time.monotonic()+5
        while time.monotonic()<end:
            result=self.box.command({'action':'detail','id':ident})
            if result['status'] not in {'READY','RUNNING'}:
                if status:self.assertEqual(result['status'],status,result)
                return result
            time.sleep(.01)
        self.fail('Mailbox job did not settle')
    def local_draft(self):return self.box.command({'action':'draft','id':'','revision':0,'value':{'to':'self@example.com','subject':'Review fixture','body':'Private fixture content'}})
    def approve(self,op,payload):
        review=self.box.command({'action':'review','operation':op,'payload':payload})
        return self.box.command({'action':'approve','review_id':review['id'],'request_id':'write-'+str(time.time_ns())}),review
    def test_read_and_encrypted_cache_never_calls_models_or_changes_mail(self):
        result=self.wait(self.job('read',{'message_id':'m1'})['id'],'SUCCEEDED');self.assertEqual(result['result']['body'],'Private fixture content')
        self.assertEqual(FakeGmail.sent,[])
        for file in (self.root/'private').glob('mail.sqlite3*'):self.assertNotIn(b'Private fixture content',file.read_bytes())
        self.assertNotIn('credentials',json.dumps(self.box.state()))
    def test_send_requires_review_and_one_review_never_sends_twice(self):
        d=self.local_draft();payload={'draft_id':d['id'],'revision':d['revision']}
        self.code('mail_review_required',self.job,'send',payload)
        row,review=self.approve('send',payload);self.wait(row['id'],'SUCCEEDED')
        repeat=self.box.command({'action':'approve','review_id':review['id'],'request_id':'another-click'})
        self.assertEqual(repeat['id'],row['id']);self.assertEqual(len(FakeGmail.sent),1)
        self.assertIn(b'Message-ID: <jarvis-',base64.urlsafe_b64decode(FakeGmail.sent[0]+'='*(-len(FakeGmail.sent[0])%4)))
    def test_draft_changed_after_review_does_not_send(self):
        d=self.local_draft();review=self.box.review('send',{'draft_id':d['id'],'revision':d['revision']})
        self.box.command({'action':'draft','id':d['id'],'revision':d['revision'],'value':{**d['value'],'body':'Changed'}})
        row=self.box.command({'action':'approve','review_id':review['id'],'request_id':'changed-draft-request'})
        self.wait(row['id'],'FAILED');self.assertEqual(FakeGmail.sent,[])
    def test_unknown_send_cannot_resume_and_reconcile_does_not_send_again(self):
        FakeGmail.fail='unknown';d=self.local_draft();row,_=self.approve('send',{'draft_id':d['id'],'revision':d['revision']})
        self.wait(row['id'],'UNKNOWN');self.code('mail_uncertain',self.box.command,{'action':'resume','id':row['id']})
        FakeGmail.fail=None;reconcile=self.job('reconcile',{'job_id':row['id']});self.wait(reconcile['id'],'SUCCEEDED')
        self.assertEqual(len(FakeGmail.sent),1);self.wait(row['id'],'SUCCEEDED')
    def test_auth_wait_and_reconnect_automatically_resume_read_only_original_task(self):
        FakeGmail.fail='auth';row=self.job('list',{'query':'in:inbox','page':''});self.wait(row['id'],'WAITING_AUTH')
        FakeGmail.fail=None;self.box.command({'action':'authorize','level':'manage'})
        end=time.monotonic()+5
        while time.monotonic()<end and self.box.auth['status'] not in {'SUCCEEDED','FAILED'}:time.sleep(.01)
        self.assertEqual(self.box.auth['status'],'SUCCEEDED');self.wait(row['id'],'SUCCEEDED')
    def test_disconnect_prevents_stale_credential_resurrection(self):
        self.box.command({'action':'disconnect'})
        s=MailStore(self.root)
        try:self.code('mail_account_changed',self.box.save_account,s,'fixture-generation',credentials=CREDS,health='connected')
        finally:s.close()
        self.assertFalse(self.box.state()['connected'])
    def test_mail_network_gate_and_scope_checks(self):
        from control.network import NetworkGate
        gate=NetworkGate(self.root);gate.update({'revision':gate.read()['revision'],'blocked':True})
        row=self.job('check',{});self.wait(row['id'],'WAITING_NETWORK')
        self.assertEqual(FakeGmail.sent,[])
        gate.update({'revision':gate.read()['revision'],'blocked':False})
        self.box.command({'action':'resume','id':row['id']});self.wait(row['id'],'SUCCEEDED')
        s=MailStore(self.root)
        try:s.update('account',credentials={**CREDS,'scope':READ})
        finally:s.close()
        d=self.local_draft();self.code('mail_scope',self.box.review,'send',{'draft_id':d['id'],'revision':d['revision']})
    def test_label_change_and_reviewed_undo(self):
        self.wait(self.job('read',{'message_id':'m1'})['id'],'SUCCEEDED')
        row,_=self.approve('change',{'message_id':'m1','change':'archive'});self.wait(row['id'],'SUCCEEDED')
        self.assertNotIn('INBOX',FakeGmail.labels['m1'])
        undo,_=self.approve('undo',{'job_id':row['id']});self.wait(undo['id'],'SUCCEEDED');self.assertIn('INBOX',FakeGmail.labels['m1'])
    def test_local_feedback_changes_classification_and_is_removable(self):
        r=self.box.command({'action':'rule','sender':'friend@example.com','category':'important'})
        row=self.wait(self.job('list',{'query':'','page':''})['id'],'SUCCEEDED')
        self.assertEqual(row['result']['messages'][0]['classification']['category'],'important')
        self.box.command({'action':'remove_rule','id':r['id'],'revision':r['revision']})
        self.assertEqual(self.box.state()['rules'],[])
    def test_trash_undo_uses_dedicated_trash_endpoint(self):
        self.wait(self.job('read',{'message_id':'m1'})['id'],'SUCCEEDED')
        row,_=self.approve('change',{'message_id':'m1','change':'trash'});self.wait(row['id'],'SUCCEEDED');self.assertIn('TRASH',FakeGmail.labels['m1'])
        undo,review=self.approve('undo',{'job_id':row['id']});self.wait(undo['id'],'SUCCEEDED');self.assertNotIn('TRASH',FakeGmail.labels['m1'])
    def test_restart_does_not_replay_ready_or_uncertain_write(self):
        s=MailStore(self.root)
        try:
            one,_=s.job('interrupted-ready','check',{})
            two,_=s.job('interrupted-write','send',{},approved=True);s.update(two['id'],status='RUNNING',effect_started=True)
            s.recover();self.assertEqual(s.get(one['id'])['status'],'WAITING');self.assertEqual(s.get(two['id'])['status'],'UNKNOWN')
        finally:s.close()
    def test_payload_and_unsafe_headers_are_rejected(self):
        self.code('mail_address',encoded_message,{'to':'a@example.com\nBcc: x@example.com','subject':'x','body':'x'},'owner@example.com','<id@local>')
        self.code('mail_invalid',self.job,'read',{'message_id':'../../settings'})
        self.code('mail_client_invalid',self.box.command,{'action':'configure','client':{'type':'service_account'}})
        self.assertTrue(capabilities(MODIFY)['send']);self.assertFalse(capabilities(READ)['send'])
    def test_request_id_reuse_with_different_content_conflicts(self):
        a=self.job('check',{},'same-request-id');self.wait(a['id'],'SUCCEEDED')
        b=self.job('check',{},'same-request-id');self.assertEqual(a['id'],b['id'])
        self.code('conflict',self.job,'read',{'message_id':'m1'},'same-request-id')
    def test_http_origin_nonce_and_no_secret_projection(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='fixture-nonce';server.mailbox=self.box
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        def send(method,value=None,nonce=True,foreign=False):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers={'Origin':'https://attacker.invalid' if foreign else origin,'Content-Type':'application/json'}
            if nonce:headers['X-Jarvis-Token']=server.nonce
            c.request(method,'/api/mail',json.dumps(value) if value is not None else None,headers);r=c.getresponse();raw=r.read();c.close();return r.status,raw
        try:
            self.assertEqual(send('GET',foreign=True)[0],403)
            status,raw=send('GET');self.assertEqual(status,200);self.assertNotIn(CREDS['refresh_token'].encode(),raw);self.assertNotIn(CREDS['client_secret'].encode(),raw)
            value={'action':'job','operation':'check','payload':{},'request_id':'http-check-fixture'}
            self.assertEqual(send('POST',value,nonce=False)[0],403)
            self.assertEqual(send('POST',{**value,'extra':'authority'})[0],400)
            status,raw=send('POST',value);self.assertEqual(status,200);self.wait(json.loads(raw)['id'],'SUCCEEDED')
        finally:
            server.shutdown();server.server_close();worker.join(2)
            if hasattr(server,'family'):server.family.close()
    def test_one_time_legacy_migration_preserves_scope_and_never_revives_disconnect(self):
        from apps.cli.migrate_gmail import migrate
        from control.credentials import crypt
        import sqlite3
        target=self.root/'target';Core.initialize(target).close();legacy=self.root/'legacy-mail.db'
        packet={'purpose':'jarvis-mail-account-v1','provider':'gmail','id':'legacy-fixture','credentials':CREDS}
        db=sqlite3.connect(legacy);db.execute('CREATE TABLE accounts(provider TEXT,id TEXT,label TEXT,encrypted TEXT,revision INTEGER)')
        db.execute('INSERT INTO accounts VALUES(?,?,?,?,?)',('gmail','legacy-fixture','owner@example.com',base64.b64encode(crypt(json.dumps(packet).encode())).decode(),3));db.commit();db.close()
        before=legacy.read_bytes();result=migrate(target,legacy);self.assertTrue(result['migrated']);self.assertTrue(result['capabilities']['modify']);self.assertEqual(legacy.read_bytes(),before)
        s=MailStore(target)
        try:
            s.update('account',credentials={},generation='disconnected')
            self.assertFalse(migrate(target,legacy)['migrated']);self.assertEqual(s.get('account')['credentials'],{})
        finally:s.close()
    def test_an_unknown_write_does_not_stop_unrelated_mail_tasks(self):
        FakeGmail.fail='unknown';d=self.local_draft();row,_=self.approve('send',{'draft_id':d['id'],'revision':d['revision']})
        self.wait(row['id'],'UNKNOWN');FakeGmail.fail=None
        self.wait(self.job('check',{})['id'],'SUCCEEDED');self.wait(row['id'],'UNKNOWN');self.assertEqual(len(FakeGmail.sent),1)


class MailCodecs(unittest.TestCase):
    def test_accepted_label_change_with_failed_verification_is_unknown(self):
        api=Gmail(copy.deepcopy(CREDS),lambda:None)
        with patch.object(api,'api',return_value={}),patch.object(api,'read',side_effect=CoreError('mail_auth_required','verification failed')):
            with self.assertRaises(CoreError) as exc:api.modify('m1',[],['STARRED'])
            self.assertEqual(exc.exception.code,'mail_confirmation_unknown')
    def test_html_is_text_and_attachments_are_not_loaded(self):
        raw=base64.urlsafe_b64encode(b'<script>bad()</script><p>Hello<img src="https://attacker.invalid/pixel"></p>').decode()
        result=message({'id':'m1','payload':{'mimeType':'text/html','body':{'data':raw}}},True)
        self.assertIn('Hello',result['body']);self.assertNotIn('bad()',result['body']);self.assertNotIn('attacker',result['body'])
        self.assertEqual(classify({'from':'friend@example.com','subject':'中奖','snippet':''})['category'],'suspicious')
    def test_refresh_never_expands_scope_and_preserves_refresh_token(self):
        v={'access_token':'new','token_type':'Bearer','expires_in':3600}
        result=token_result(v,CREDS);self.assertEqual(result['refresh_token'],CREDS['refresh_token'])
        with self.assertRaises(CoreError):token_result({**v,'scope':READ+' '+MODIFY},{**CREDS,'scope':READ})
    def test_google_401_refreshes_once_but_network_unknown_does_not_retry(self):
        calls=[]
        def send(url,guard,**kw):
            calls.append(url)
            if len(calls)==1:raise CoreError('mail_auth_required','401')
            if 'token' in url:return {'access_token':'new','token_type':'Bearer','expires_in':3600}
            return {'emailAddress':'owner@example.com'}
        api=Gmail(copy.deepcopy(CREDS),lambda:None)
        with patch('adapters.mail.google.request',side_effect=send):self.assertEqual(api.profile()['email'],'owner@example.com')
        self.assertEqual(len(calls),3)
        with patch('adapters.mail.google.request',side_effect=CoreError('mail_network','unknown')) as send:
            with self.assertRaises(CoreError):api.send('raw')
            self.assertEqual(send.call_count,1)
    def test_oauth_checks_state_and_pkce_and_returns_no_code_in_page(self):
        observed=[];workers=[]
        def browser(url):
            query=parse_qs(urlsplit(url).query);observed.append(query)
            target=urlsplit(query['redirect_uri'][0])
            def callback():
                for state in ('wrong',query['state'][0]):
                    c=http.client.HTTPConnection(target.hostname,target.port,timeout=3)
                    c.request('GET','/callback?state='+state+'&code=fixture-code');r=c.getresponse();body=r.read();observed.append((r.status,body));c.close()
            worker=threading.Thread(target=callback,daemon=True);workers.append(worker);worker.start();return True
        result={'access_token':'new','refresh_token':'new-refresh','token_type':'Bearer','expires_in':3600,'scope':READ}
        with patch('adapters.mail.oauth.request',return_value=result):credentials=authorize({k:CREDS[k] for k in ['client_id','client_secret']},'read',lambda:None,opener=browser,timeout=4)
        for worker in workers:worker.join(timeout=3)
        self.assertEqual(credentials['refresh_token'],'new-refresh');self.assertEqual(observed[0]['code_challenge_method'],['S256'])
        self.assertEqual([x[0] for x in observed[1:]],[400,200]);self.assertNotIn(b'fixture-code',observed[-1][1])


if __name__=='__main__':unittest.main()
