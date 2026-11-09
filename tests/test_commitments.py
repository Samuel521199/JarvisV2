"""Durable personal commitments: generations, replay, schema and local receipts."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from control.application_runtime import publish
from control.recovery.gate import StopGate
from host.core import Core
from host import commitments as service
from host.work_status import snapshot, acknowledge
from modules.task_resource.commitments import Commitments, due, check_compatible
from sdk.protocol import CoreError


def ident(): return uuid.uuid4().hex


def create(when='2030-01-01T12:00:00+08:00'):
    return {'action':'create','id':ident(),'request_id':ident(),
            'title':'回复邮件','source':'本人要求：明确时间提醒，勿代发邮件','due_at':when}


class CommitmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);Core.initialize(self.root).close()

    def test_offsets_ambiguity_and_invalid_dates(self):
        self.assertEqual(due('2030-01-01T12:00:00+08:00'),due('2030-01-01T04:00:00Z'))
        for value in ['明天下午','2030-01-01T12:00:00','2030-02-30T12:00:00Z',True,1,
                      '2030-01-01T12:00:00+14:01','2030-01-01T12:00:00+01:99']:
            with self.subTest(value=value),self.assertRaises(CoreError):due(value)

    def test_no_early_delivery_restart_late_delivery_and_clock_reversal(self):
        body=create();when=due(body['due_at'])
        with Commitments(self.root) as store:
            store.command(body,now=when-100);self.assertEqual(store.advance(now=when-1),0)
        with Commitments(self.root) as store:
            self.assertEqual(store.advance(now=when+3600),1)
            self.assertEqual(store.read(body['id'])['posted_at'],when+3600)
            self.assertEqual(store.advance(now=when-100),0)
            self.assertEqual(store.advance(now=when+7200),0)
            self.assertEqual([e['event'] for e in store.history(body['id'])].count('due'),1)

    def test_replay_never_resurrects_cancelled_commitment(self):
        body=create()
        with Commitments(self.root) as store:
            store.command(body)
            cancelled={'action':'cancel','id':body['id'],'request_id':ident(),'revision':1}
            store.command(cancelled)
            repeat=store.command(body)
            self.assertTrue(repeat['existing']);self.assertEqual(repeat['current']['status'],'CANCELLED')
            self.assertEqual(store.advance(now=due(body['due_at'])+1),0)
            with self.assertRaises(CoreError):store.command({**body,'title':'changed'})

    def test_stale_reschedule_and_late_cancel_cannot_write(self):
        body=create()
        with Commitments(self.root) as store:
            store.command(body)
            change={'action':'reschedule','id':body['id'],'request_id':ident(),'revision':1,'due_at':'2031-01-01T12:00:00+08:00'}
            store.command(change)
            with self.assertRaises(CoreError):store.command({'action':'cancel','id':body['id'],'request_id':ident(),'revision':1})
            self.assertEqual(store.advance(now=due(body['due_at'])+1),0)
            self.assertEqual(store.read(body['id'])['revision'],2)
            self.assertEqual(store.read(body['id'])['source'],body['source'])

    def test_concurrent_schedulers_only_post_once(self):
        body=create('2001-01-01T00:00:00Z')
        with Commitments(self.root) as store:store.command(body)
        def tick(_):
            with Commitments(self.root) as store:return store.advance()
        with ThreadPoolExecutor(max_workers=4) as pool:counts=list(pool.map(tick,range(8)))
        self.assertEqual(sum(counts),1)
        with Commitments(self.root) as store:self.assertEqual(len(store.history(body['id'])),2)

    def test_due_is_unread_until_explicit_current_version_receipt(self):
        body=create('2001-01-01T00:00:00Z');service.command(self.root,body);service.advance(self.root)
        item=next(i for i in snapshot(self.root,SimpleNamespace())['items'] if i['source']=='commitments')
        self.assertEqual(item['raw_status'],'DUE');self.assertTrue(item['attention']['unread'])
        self.assertTrue(service.read(self.root)['items'][0]['attention']['unread'])
        acknowledge(self.root,SimpleNamespace(),{'action':'viewed','key':item['attention']['key'],'version':item['attention']['version']})
        self.assertFalse(service.read(self.root)['items'][0]['attention']['unread'])
        service.command(self.root,{'action':'reschedule','id':body['id'],'request_id':ident(),'revision':1,'due_at':'2002-01-01T00:00:00Z'})
        service.advance(self.root)
        with self.assertRaises(CoreError):acknowledge(self.root,SimpleNamespace(),{'action':'viewed','key':item['attention']['key'],'version':item['attention']['version']})
        current=service.read(self.root)['items'][0]
        self.assertTrue(current['attention']['unread']);self.assertEqual(current['raw_status'],'DUE')

    def test_reading_does_not_post_and_pause_drain_suppress_pump(self):
        body=create('2001-01-01T00:00:00Z');service.command(self.root,body)
        self.assertEqual(service.read(self.root)['items'][0]['raw_status'],'OPEN')
        publish(self.root,'a'*64,1,'draining');self.assertEqual(service.advance(self.root),0)
        with self.assertRaises(CoreError):service.command(self.root,create())
        publish(self.root,'a'*64,1,'active');StopGate(self.root).stop()
        self.assertEqual(service.advance(self.root),0)
        service.command(self.root,{'action':'cancel','id':body['id'],'request_id':ident(),'revision':1})
        self.assertEqual(service.read(self.root)['items'][0]['raw_status'],'CANCELLED')

    def test_future_schema_rejected_and_core_schema_unchanged(self):
        with Commitments(self.root):pass
        target=self.root/'state/commitments.sqlite3'
        with closing(sqlite3.connect(target)) as db:db.execute('PRAGMA user_version=2');db.commit()
        with self.assertRaises(CoreError):Commitments(self.root)
        with self.assertRaises(CoreError):check_compatible(self.root)
        from apps.workbench import runtime_http
        publish(self.root,'a'*64,1,'starting')
        handler=SimpleNamespace(server=SimpleNamespace(data_root=self.root,application_build='a'*64,application_epoch=1))
        with self.assertRaises(CoreError):
            runtime_http.post(handler,'/api/runtime/health',{'build':'a'*64,'epoch':1})
        with closing(sqlite3.connect(target)) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)
        with closing(sqlite3.connect(self.root/'state/core.sqlite3')) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],7)

    def test_failed_change_rolls_back_record_history_and_idempotency(self):
        body=create()
        with Commitments(self.root) as store:
            store.command(body)
            change={'action':'reschedule','id':body['id'],'request_id':ident(),'revision':1,'due_at':None}
            with patch.object(store,'event',side_effect=OSError('injected write failure')),self.assertRaises(OSError):
                store.command(change)
            self.assertEqual(store.read(body['id'])['revision'],1)
            self.assertEqual(len(store.history(body['id'])),1)
            self.assertFalse(store.command(change)['existing'])
            self.assertEqual(store.read(body['id'])['revision'],2)

    def test_undated_todo_and_completion_are_user_claims_not_notification(self):
        body=create(None)
        with Commitments(self.root) as store:
            store.command(body);self.assertEqual(store.advance(),0)
            result=store.command({'action':'complete','id':body['id'],'request_id':ident(),'revision':1})
            self.assertEqual(result['current']['status'],'DONE');self.assertIsNone(result['current']['posted_at'])
            with self.assertRaises(CoreError):store.command({'action':'reschedule','id':body['id'],'request_id':ident(),'revision':2,'due_at':body['due_at']})


if __name__=='__main__':unittest.main()
