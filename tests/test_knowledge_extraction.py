import threading
import time
import unittest
from unittest.mock import patch
import test_knowledge as fixtures
from host import knowledge_extraction as extract,memory
from modules.context_knowledge.claims import Claims
from sdk.protocol import CoreError,canonical

QUOTE='2026年十月的项目会议改在北楼举行，尚未最终确认。'


class ExtractionTests(unittest.TestCase):
    setUp=fixtures.Library.setUp
    source=fixtures.Library.source
    update=fixtures.Library.update

    def tearDown(self):
        extract.close(self.root);fixtures.Library.tearDown(self)

    def command(self,source,ident='synthetic-extract'):
        return dict(action='start',scope='personal',id=source['id'],revision=source['revision'],provider='openai',model='test-model',reasoning='default',request_id=ident)

    def fake(self,callback=None):
        class Client:
            calls=0
            def __init__(self,*args):pass
            def available(self):return True
            def complete(self,messages,checkpoint,json_mode):
                Client.calls+=1;checkpoint()
                if callback:return callback(messages,checkpoint)
                return {'status':'SUCCEEDED','text':canonical({'claims':[{'key':'会议安排待确认','quote':QUOTE}]}),'usage':{'prompt_tokens':30,'completion_tokens':20}}
        return Client

    def finish(self):extract.ACTIVE[str(self.root)].result(timeout=5)
    def jobs(self):return extract.command(self.root,{'action':'status','scope':'personal'})['jobs']

    def test_async_candidates_not_facts_exact_offsets_and_paid_receipt_no_raw_result(self):
        source=self.source('原始记录：\n'+QUOTE+'\n不要将这条计划当成已经发生。');client=self.fake()
        with patch.object(extract,'NativeModel',client):
            extract.command(self.root,self.command(source));self.finish()
            extract.command(self.root,self.command(source));self.finish()
        self.assertEqual(client.calls,1);self.assertEqual(self.jobs()[0]['state'],'succeeded')
        candidates=Claims(self.core.db).list('personal');self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[0]['quote'],QUOTE);self.assertEqual(candidates[0]['start'],6)
        self.assertEqual(self.memory.list('personal'),[])
        call=self.core.db.one("SELECT * FROM model_calls WHERE phase='knowledge-extract'")
        self.assertIsNone(call['result']);self.assertNotIn(QUOTE,canonical(call))

    def test_fabricated_ambiguous_or_partial_batch_has_no_candidates(self):
        source=self.source(QUOTE+'\n'+QUOTE);claims=Claims(self.core.db)
        for payload in ({'claims':[{'key':'编造','quote':'原文中不存在的内容。'}]},
                        {'claims':[{'key':'歧义','quote':QUOTE}]},
                        {'claims':[{'key':'多余字段','quote':QUOTE,'command':'execute'}]}):
            with self.assertRaises(CoreError):claims.model_candidates('personal',source['id'],1,'openai',payload)
        self.assertEqual(claims.list('personal'),[])

    def test_permission_denied_before_model_and_revoked_during_call_rejects_commit(self):
        source=self.source(QUOTE,providers=['bailian']);client=self.fake()
        with patch.object(extract,'NativeModel',client):
            with self.assertRaises(CoreError):extract.command(self.root,self.command(source))
        self.assertEqual(client.calls,0)
        source=self.update(source['id'],providers=['openai'])
        def mutate(messages,checkpoint):
            self.update(source['id'],providers=[])
            return {'status':'SUCCEEDED','text':canonical({'claims':[{'key':'会议','quote':QUOTE}]})}
        with patch.object(extract,'NativeModel',self.fake(mutate)):
            extract.command(self.root,self.command(source));self.finish()
        self.assertEqual(self.jobs()[0]['state'],'failed');self.assertEqual(Claims(self.core.db).list('personal'),[])

    def test_slow_extraction_does_not_block_memory_reads_and_can_cancel(self):
        source=self.source(QUOTE);entered=threading.Event();release=threading.Event()
        def slow(messages,checkpoint):
            entered.set();release.wait(5);checkpoint()
            return {'status':'SUCCEEDED','text':canonical({'claims':[]})}
        try:
            with patch.object(extract,'NativeModel',self.fake(slow)):
                extract.command(self.root,self.command(source));self.assertTrue(entered.wait(2))
                started=time.monotonic();memory.retrieve(self.root,'personal','openai',True,'会议')
                self.assertLess(time.monotonic()-started,.5)
                extract.command(self.root,{'action':'cancel','scope':'personal','request_id':'synthetic-extract'})
                release.set();self.finish()
        finally:release.set()
        self.assertEqual(self.jobs()[0]['state'],'cancelled');self.assertEqual(Claims(self.core.db).list('personal'),[])

    def test_unknown_never_replayed_and_recovery_does_not_send_again(self):
        source=self.source(QUOTE);client=self.fake(lambda *_:{'status':'UNKNOWN','code':'transport_timeout'})
        with patch.object(extract,'NativeModel',client):
            extract.command(self.root,self.command(source));self.finish();extract.recover(self.root)
            extract.command(self.root,self.command(source));self.finish()
        self.assertEqual(client.calls,1);self.assertEqual(self.jobs()[0]['state'],'unknown')
        with self.core.db.transaction() as tx:
            tx.execute("UPDATE knowledge_extractions SET state='running'")
            tx.execute("UPDATE model_calls SET status='DISPATCHING' WHERE phase='knowledge-extract'")
        extract.recover(self.root)
        self.assertEqual(self.jobs()[0]['error'],'host_interrupted')
        self.assertEqual(self.core.db.one("SELECT status FROM model_calls WHERE phase='knowledge-extract'")['status'],'UNKNOWN')

    def test_candidate_is_withdrawn_when_source_changes(self):
        source=self.source(QUOTE)
        Claims(self.core.db).model_candidates('personal',source['id'],1,'openai',{'claims':[{'key':'会议安排','quote':QUOTE}]})
        self.update(source['id'],text='会议取消了，不再安排到北楼。')
        row=Claims(self.core.db).list('personal')[0];self.assertEqual(row['state'],'withdrawn');self.assertEqual(row['quote'],'')


if __name__=='__main__':unittest.main()
