import copy
import http.client
from http.server import ThreadingHTTPServer
import threading
import time
import unittest
from unittest.mock import patch

import test_knowledge as fixtures
from host import memory
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.methods import parse,select,text_digest
from sdk.protocol import CoreError,canonical,decode


class ConditionalAdvice(unittest.TestCase):
    setUp=fixtures.Library.setUp
    tearDown=fixtures.Library.tearDown
    source=fixtures.Library.source

    def prepare(self,**changes):
        evidence=self.source('Prior task filtered delivery and budget before comparing full prices.','Original observation')
        text=Knowledge(self.core.db).detail('personal',evidence['id'])['text']
        card={'schema':'jarvis.method-card.v1','id':'quote-filter-first','revision':1,'status':'CANDIDATE',
            'recipe':'quote-source-v1','requires':{'currency':'CNY','price_includes_fees':True},
            'summary':'Filter current budget and deadline, then compare current total prices; do not cache the old winning offer.',
            'counterexamples':['A net price without fees is outside this method.'],
            'evidence':[{'source_id':evidence['id'],'revision':1,'sha256':text_digest(text)}],'expires':time.time()+3600}
        card.update(changes)
        saved=self.source(canonical(card),'Quote reuse method')
        return evidence,card,saved

    def recall(self,context=None,**changes):
        value={'action':'method_recall','scope':'personal','provider':'openai','enabled':True,
            'query':'Quote reuse method','context':{'currency':'CNY','price_includes_fees':True} if context is None else context}
        value.update(changes);return memory.command(self.root,value)

    def test_current_conditions_keep_source_and_counterexamples_without_writes(self):
        _,card,source=self.prepare();before=self.core.db.all('SELECT * FROM facts')
        result=self.recall();method=result['methods'][0]
        self.assertEqual(method['source_id'],source['id']);self.assertEqual(method['requires'],card['requires'])
        self.assertEqual(method['counterexamples'],card['counterexamples']);self.assertEqual(method['evidence'],card['evidence'])
        self.assertFalse(method['verified']);self.assertFalse(method['execution_authorized']);self.assertFalse(result['automatic_promotion'])
        self.assertEqual(before,self.core.db.all('SELECT * FROM facts'))

    def test_missing_unknown_reversed_and_wrong_scalar_types_never_match(self):
        self.prepare()
        for selectors in [{},{'currency':'CNY','price_includes_fees':None},{'currency':'CNY','price_includes_fees':False},
                          {'currency':'CNY','price_includes_fees':1}]:
            result=self.recall(selectors);self.assertEqual(result['methods'],[])
            self.assertTrue(any(r['reason'] in ('unknown_precondition','precondition_mismatch') for r in result['rejected']))

    def test_corrected_or_deleted_evidence_invalidates_without_changing_card(self):
        evidence,_,_=self.prepare();self.assertEqual(len(self.recall()['methods']),1)
        library=Knowledge(self.core.db);old=library.detail('personal',evidence['id'])
        library.save({k:old[k] for k in ('id','scope','title','text','providers')}|{'paused':False,'text':'The previous observation was wrong.'},1)
        self.assertEqual(self.recall()['methods'],[])
        library.delete('personal',evidence['id'],2)
        self.assertEqual(self.recall()['methods'],[])

    def test_permission_change_and_disabled_memory_cannot_follow_embedded_ids(self):
        evidence,_,_=self.prepare();library=Knowledge(self.core.db);old=library.detail('personal',evidence['id'])
        library.save({k:old[k] for k in ('id','scope','title','text')}|{'providers':['bailian'],'paused':False},1)
        self.assertEqual(self.recall()['methods'],[])
        self.assertEqual(self.recall(enabled=False)['methods'],[])
        self.assertEqual(self.recall(provider='bailian')['methods'],[])

    def test_project_and_provider_boundaries_apply_to_supporting_evidence(self):
        secret=Knowledge(self.core.db).save({'id':'','scope':'project-private','title':'Secret','text':'private observation',
            'providers':['openai'],'paused':False},0)
        self.prepare(evidence=[{'source_id':secret['id'],'revision':1,'sha256':text_digest('private observation')}])
        result=self.recall();self.assertEqual(result['methods'],[])
        self.assertNotIn('private observation',canonical(result))

    def test_expired_and_quarantined_candidates_are_not_reused(self):
        self.prepare(status='QUARANTINED');self.assertEqual(self.recall()['methods'],[])
        # Separate sources exercise expiry independently of quarantine.
        self.prepare(expires=time.time()-1)
        self.assertEqual(self.recall()['methods'],[])

    def test_same_evidence_copies_do_not_fill_context_or_count_as_successes(self):
        _,card,_=self.prepare();duplicate=copy.deepcopy(card);duplicate['id']='echo-from-another-bot'
        self.source(canonical(duplicate),'Quote reuse method echo')
        result=self.recall();self.assertEqual(len(result['methods']),1)
        self.assertEqual(result['lineage_groups'],1);self.assertIsNone(result['independent_successes'])
        self.assertIn('duplicate_method_same_evidence',[r['reason'] for r in result['rejected']])

    def test_competing_summaries_are_retained_without_claiming_independent_support(self):
        _,card,_=self.prepare();card['id']='challenger';card['summary']='A competing hypothesis which must be tested separately.'
        self.source(canonical(card),'Quote reuse method challenger')
        result=self.recall();self.assertEqual(len(result['methods']),2)
        self.assertEqual(result['lineage_groups'],1);self.assertIsNone(result['independent_successes'])

    def test_methods_cannot_self_corroborate_or_cite_another_method(self):
        _,card,saved=self.prepare();card['id']='circular';card['evidence']=[{'source_id':saved['id'],'revision':1,'sha256':text_digest(canonical(card))}]
        # Bind exact bytes of the other valid card; even that isn't an observation.
        card['evidence'][0]['sha256']=text_digest(Knowledge(self.core.db).detail('personal',saved['id'])['text'])
        self.source(canonical(card),'Quote reuse method circular')
        result=self.recall();self.assertEqual(len(result['methods']),1)
        self.assertIn('method_as_evidence',[r['reason'] for r in result['rejected']])

    def test_invalid_json_duplicate_keys_and_rules_are_rejected(self):
        _,card,_=self.prepare()
        for bad in [canonical(card)[:-1]+',"revision":2}',canonical(card|{'requires':{'price_includes_fees':None}}),
                    canonical(card|{'evidence':card['evidence']*2}),canonical(card|{'counterexamples':[]})]:
            with self.assertRaises(CoreError):parse(bad)
        with self.assertRaises(CoreError):self.recall({'price_includes_fees':[]})

    def test_budget_rejects_whole_card_without_truncating_conditions(self):
        _,card,saved=self.prepare();source=Knowledge(self.core.db).detail('personal',saved['id'])
        evidence=Knowledge(self.core.db).detail('personal',card['evidence'][0]['source_id'])
        result=select([source],{'currency':'CNY','price_includes_fees':True},lambda _:evidence,max_bytes=512)
        self.assertEqual(result['methods'],[]);self.assertEqual(result['rejected'][0]['reason'],'context_budget')

    def test_before_use_revalidation_checks_original_sources_not_current_top_n(self):
        evidence,card,_=self.prepare();receipt=self.recall()['receipt']
        for i in range(15):self.source('Other observation '+str(i),'Quote reuse method '+str(i))
        command={'action':'method_revalidate','scope':'personal','provider':'openai','enabled':True,
            'context':{'currency':'CNY','price_includes_fees':True},'receipt':receipt}
        self.assertTrue(memory.command(self.root,command)['current'])
        library=Knowledge(self.core.db);old=library.detail('personal',evidence['id'])
        library.save({k:old[k] for k in ('id','scope','title','text','providers')}|{'paused':True},1)
        with self.assertRaises(CoreError):memory.command(self.root,command)

    def test_changed_context_or_forged_receipt_cannot_claim_current_advice(self):
        self.prepare();receipt=self.recall()['receipt']
        command={'action':'method_revalidate','scope':'personal','provider':'openai','enabled':True,
            'context':{'currency':'CNY','price_includes_fees':True},'receipt':receipt}
        for changed in [command|{'enabled':False},command|{'context':{'currency':'CNY','price_includes_fees':False}},
            command|{'receipt':receipt|{'version':'future-policy'}},
            command|{'receipt':receipt|{'methods':[receipt['methods'][0]|{'method_digest':'0'*64}]}}]:
            with self.assertRaises(CoreError):memory.command(self.root,changed)

    def test_http_uses_original_nonce_and_origin_gate_and_returns_only_advice(self):
        self.prepare();server=ThreadingHTTPServer(('127.0.0.1',0),fixtures.Handler)
        server.data_root=self.root;server.nonce='test'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            body={'action':'method_recall','scope':'personal','provider':'openai','enabled':True,
                'query':'Quote reuse method','context':{'currency':'CNY','price_includes_fees':True}}
            def post(auth):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
                headers={'Content-Type':'application/json'}
                if auth:headers.update(Origin='http://127.0.0.1:'+str(server.server_port),**{'X-Jarvis-Token':'test'})
                connection.request('POST','/api/memory',canonical(body).encode(),headers)
                response=connection.getresponse();value=decode(response.read());connection.close()
                return response.status,value
            self.assertEqual(post(False)[0],403)
            status,value=post(True);self.assertEqual(status,200)
            self.assertEqual(len(value['methods']),1);self.assertFalse(value['execution_authorized'])
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_method_cards_and_their_claims_never_become_ordinary_factual_context(self):
        _,card,saved=self.prepare()
        for indexed in [False,True]:
            if indexed:Knowledge(self.core.db).rebuild()
            view=memory.retrieve(self.root,'personal','openai',True,'Quote reuse method')
            self.assertNotIn(saved['id'],[r['id'] for r in view['facts']])
            self.assertNotIn(card['summary'],canonical(view))
        from modules.context_knowledge.claims import Claims
        claims=Claims(self.core.db);claims.compile('personal',saved['id'],1)
        claim=next(r for r in claims.list('personal') if r['source_id']==saved['id'])
        with self.assertRaises(CoreError):claims.accept('personal',claim['id'],claim['revision'],
            {'scope':'personal','key':'Not a verified method','value':card['summary'],'kind':'knowledge','purpose':'personal',
             'providers':['openai'],'paused':False,'expires':None},0)
        self.assertEqual(len(self.recall()['methods']),1)

    def test_branch_snapshot_and_future_method_schema_do_not_leak_as_plain_reference(self):
        _,card,_=self.prepare();library=Knowledge(self.core.db)
        saved=library.save({'id':'','scope':'project-A','title':'Historical method','text':canonical(card),
            'providers':['openai'],'paused':False},0)
        from modules.context_knowledge.domains import Domains
        branch=Domains(self.core.db).create('project-A','branch','Snapshot',True)['id']
        library.save({'id':saved['id'],'scope':'project-A','title':'Now ordinary','text':'An ordinary current observation',
            'providers':['openai'],'paused':False},1)
        self.assertNotIn(card['summary'],canonical(self.memory.view(branch,'openai',True,'Historical method')))
        future=self.source('{"schema":"jarvis.method-card.v2","summary":"future-method-canary"}','Future advice')
        self.assertNotIn(future['id'],[r['id'] for r in memory.retrieve(self.root,'personal','openai',True,'Future advice')['facts']])
        ordinary=self.source('{"schema":"other.v1","text":"ordinary-json-canary"}','Ordinary JSON')
        self.assertIn(ordinary['id'],[r['id'] for r in memory.retrieve(self.root,'personal','openai',True,'Ordinary JSON')['facts']])

    def test_vector_recall_also_excludes_method_cards_from_normal_background(self):
        _,card,saved=self.prepare()
        from modules.context_knowledge.vectors import Vectors
        vectors=Vectors(self.core.db);vectors.build('test-encoder',2,lambda texts:[[1.,0.] for _ in texts])
        rows,_=vectors.search('personal','openai','test-encoder',[1.,0.])
        self.assertNotIn(saved['id'],[r['evidence']['source_id'] for r in rows])
        self.assertNotIn(card['summary'],canonical(rows))

    def test_method_edit_or_expiry_invalidates_pre_use_receipt(self):
        _,card,saved=self.prepare();receipt=self.recall()['receipt']
        command={'action':'method_revalidate','scope':'personal','provider':'openai','enabled':True,
            'context':card['requires'],'receipt':receipt}
        with patch('modules.context_knowledge.methods.time.time',return_value=card['expires']+1):
            with self.assertRaises(CoreError):memory.command(self.root,command)
        card['summary']='A corrected hypothesis; new use must be reviewed again.';card['revision']=2
        Knowledge(self.core.db).save({'id':saved['id'],'scope':'personal','title':'Quote reuse method','text':canonical(card),
            'providers':['openai'],'paused':False},1)
        with self.assertRaises(CoreError):memory.command(self.root,command)

    def test_reserved_method_payload_cannot_bypass_role_by_becoming_a_fact(self):
        _,card,_=self.prepare()
        item={'scope':'personal','key':'Unsafe fact route','value':canonical(card),'kind':'knowledge','purpose':'personal',
              'providers':['openai'],'paused':False,'expires':None}
        with self.assertRaises(CoreError):self.memory.save(item,0)
        normal={**item,'value':'A previously ordinary fact'};saved=self.memory.save(normal,0)
        # Simulate an old writer/restored fact which didn't understand the role.
        with self.core.db.transaction() as tx:tx.execute('UPDATE facts SET value=? WHERE id=?',(canonical(card),saved['id']))
        self.assertEqual(self.memory.list('personal')[0]['state'],'advisory_only')
        self.assertNotIn(card['summary'],canonical(memory.retrieve(self.root,'personal','openai',True,'Unsafe fact route')))





    def test_unknown_future_method_cannot_be_used_as_original_observation(self):
        _,card,_=self.prepare()
        future=self.source('{"schema":"jarvis.method-card.v2","summary":"not original evidence"}','Future method')
        card['id']='future-evidence';card['evidence']=[{'source_id':future['id'],'revision':1,'sha256':text_digest('{"schema":"jarvis.method-card.v2","summary":"not original evidence"}')}]
        saved=self.source(canonical(card),'Quote reuse method future evidence')
        result=self.recall()
        self.assertFalse(any(m['source_id']==saved['id'] for m in result['methods']))
        self.assertIn('method_as_evidence',[r['reason'] for r in result['rejected']])


if __name__=='__main__':unittest.main()
