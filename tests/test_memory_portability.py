import copy
import tempfile
import threading
import subprocess
import sys
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import test_knowledge_cycle as cycle_fixtures
from test_memory_development_ui import fact
from host.core import Core
from host import memory, memory_portability
from modules.context_knowledge.bundle import Bundle, validate
from modules.context_knowledge.history import versions
from modules.context_knowledge.memory import Memory
from modules.context_knowledge.claims import Claims
from sdk.protocol import CoreError, canonical, digest


class Portability(unittest.TestCase):
    setUp=cycle_fixtures.Cycle.setUp
    tearDown=cycle_fixtures.Cycle.tearDown
    source=cycle_fixtures.Cycle.source
    update=cycle_fixtures.Cycle.update
    compile=cycle_fixtures.Cycle.compile
    accept=cycle_fixtures.Cycle.accept
    turn=cycle_fixtures.Cycle.turn

    def export(self):return memory_portability.command(self.root,{'action':'export','scope':'personal'})

    def restore(self,bundle,db=None,scope='personal'):
        manager=Bundle(db or self.core.db);plan=manager.preview(scope,bundle)
        return manager.restore(scope,bundle,plan['token'])

    def test_history_is_revisions_not_current_facts_and_forget_purges(self):
        saved=self.memory.save(fact(value='以前称呼'),0)
        self.memory.save(fact(value='现在称呼'),1)
        rows=versions(self.core.db,'personal','fact',saved['id'])['versions']
        self.assertEqual([r['body']['value'] for r in rows],['现在称呼','以前称呼'])
        self.assertNotIn('以前称呼',canonical(self.memory.view('personal','openai')))
        self.memory.forget('personal','称呼',2)
        self.assertEqual(self.core.db.all('SELECT * FROM memory_history'),[])
        with self.assertRaises(CoreError):versions(self.core.db,'personal','fact',saved['id'])

    def test_source_history_retained_on_correction_purged_on_delete(self):
        source=self.source();self.update(source['id'],text='新地点')
        rows=versions(self.core.db,'personal','source',source['id'])['versions']
        self.assertEqual(len(rows),2)
        from modules.context_knowledge.knowledge import Knowledge
        Knowledge(self.core.db).delete('personal',source['id'],2)
        self.assertEqual(self.core.db.all('SELECT * FROM memory_history'),[])

    def test_conditions_filter_before_encoder_and_reference_check(self):
        saved=self.memory.save(fact(applicability={'valid_from':None,'conditions':{'channel':'chat','activity':'leisure'}}),0)
        calls=[]
        def encoder(rows,q):calls.extend(rows);return {'status':'unavailable','scores':{}}
        self.memory.view('personal','openai',True,'称呼',encoder,selectors={'channel':'task'})
        self.assertEqual(calls,[])
        self.assertFalse(self.memory.references_valid('personal','openai',True,[saved],{'channel':'chat'}))
        self.assertTrue(self.memory.references_valid('personal','openai',True,[saved],{'channel':'chat','activity':'leisure'}))

    def test_effective_start_and_end_are_enforced_and_invalid_interval_rejected(self):
        now=time.time();item=fact(applicability={'valid_from':now+30,'conditions':{}});item['expires']=now+60
        saved=self.memory.save(item,0)
        self.assertEqual(self.memory.list('personal')[0]['state'],'scheduled')
        self.assertEqual(self.memory.references('personal','openai'),[])
        with patch('modules.context_knowledge.conditions.time.time',return_value=now+40):
            self.assertTrue(self.memory.references_valid('personal','openai',True,[saved]))
        with patch('modules.context_knowledge.conditions.time.time',return_value=now+61):
            self.assertEqual(self.memory.references('personal','openai'),[])
        item['expires']=now+20
        with self.assertRaises(CoreError):self.memory.save(item,1)

    def test_fresh_restore_facts_sources_candidates_history_origins_and_permissions(self):
        s=self.source();self.accept(self.compile(s));f=self.memory.save(fact(),0);self.memory.save(fact(value='另一称呼'),1)
        chat=self.chats.create();self.turn(chat,'origin','周六散步')
        memory.command(self.root,{'action':'propose','turn_id':'origin'})
        bundle=self.export();self.assertEqual(len(bundle['origins']),3)
        with tempfile.TemporaryDirectory() as folder:
            core=Core.initialize(Path(folder))
            try:
                self.restore(bundle,core.db);mem=Memory(core.db)
                self.assertEqual(len(mem.list('personal')),2)
                self.assertEqual(mem.view('personal','openai')['facts'],[])
                self.assertEqual(len(mem.candidates('personal')),1)
                self.assertEqual(len(versions(core.db,'personal','fact',f['id'])['versions']),2)
                before=core.db.all('SELECT * FROM facts');self.restore(bundle,core.db)
                self.assertEqual(before,core.db.all('SELECT * FROM facts'))
                self.assertEqual(core.db.integrity(),'ok')
            finally:core.close()

    def test_deleted_fact_is_never_restored_even_with_higher_incoming_revision(self):
        self.memory.save(fact(),0);old=self.export();self.memory.forget('personal','称呼',1)
        old['facts'][0]['revision']=800;old['checksum']=digest({k:v for k,v in old.items() if k!='checksum'})
        self.restore(old);self.assertEqual(self.memory.list('personal'),[])
        self.assertEqual(self.core.db.all('SELECT * FROM memory_history'),[])
        self.assertEqual(self.core.db.all('SELECT * FROM memory_origins'),[])

    def test_fact_tombstone_applies_to_other_node_and_dismissal_cannot_reappear(self):
        self.memory.save(fact(),0);old=self.export();self.memory.forget('personal','称呼',1);deleted=self.export()
        with tempfile.TemporaryDirectory() as folder:
            core=Core.initialize(Path(folder))
            try:
                self.restore(old,core.db);self.restore(deleted,core.db);self.restore(old,core.db)
                self.assertEqual(Memory(core.db).list('personal'),[])
                self.assertEqual(core.db.all('SELECT * FROM memory_origins'),[])
            finally:core.close()

    def test_source_tombstone_prevents_derived_fact_resurrection(self):
        s=self.source();self.accept(self.compile(s));old=self.export()
        from modules.context_knowledge.knowledge import Knowledge
        Knowledge(self.core.db).delete('personal',s['id'],1)
        self.restore(old);self.assertEqual(self.memory.list('personal'),[])
        self.assertEqual(self.core.db.all('SELECT * FROM memory_history'),[])

    def test_imported_claim_remains_bound_and_source_change_revokes_it(self):
        s=self.source();self.accept(self.compile(s));bundle=self.export()
        with tempfile.TemporaryDirectory() as folder:
            core=Core.initialize(Path(folder))
            try:
                self.restore(bundle,core.db)
                from modules.context_knowledge.knowledge import Knowledge
                source=Knowledge(core.db).detail('personal',s['id'])
                Knowledge(core.db).save({k:source[k] for k in ('id','scope','title','text','providers')}|{'paused':False},source['revision'])
                self.assertEqual(Memory(core.db).list('personal'),[])
            finally:core.close()

    def test_conflicting_fact_blocks_entire_source_bundle(self):
        self.memory.save(fact(),0);self.source();bundle=self.export();self.memory.save(fact(value='本地纠正'),1)
        bundle['facts'][0]['value']='远端分叉';bundle['checksum']=digest({k:v for k,v in bundle.items() if k!='checksum'})
        plan=Bundle(self.core.db).preview('personal',bundle);self.assertFalse(plan['can_apply'])
        before=canonical(self.core.db.all('SELECT * FROM knowledge_sources'))
        with self.assertRaises(CoreError):Bundle(self.core.db).restore('personal',bundle,plan['token'])
        self.assertEqual(before,canonical(self.core.db.all('SELECT * FROM knowledge_sources')))

    def test_preview_rejects_concurrent_candidate_review(self):
        self.memory.propose('turn:test','hash','personal','待核对');bundle=self.export();manager=Bundle(self.core.db)
        plan=manager.preview('personal',bundle);r=self.memory.candidates('personal')[0];self.memory.dismiss(r['id'],r['revision'])
        with self.assertRaises(CoreError):manager.restore('personal',bundle,plan['token'])

    def test_restore_failure_rolls_back_sources_and_facts(self):
        self.memory.save(fact(),0);self.source();bundle=self.export()
        with tempfile.TemporaryDirectory() as folder:
            core=Core.initialize(Path(folder))
            try:
                with patch('modules.context_knowledge.bundle.changed',side_effect=RuntimeError('injected')):
                    with self.assertRaises(RuntimeError):self.restore(bundle,core.db)
                self.assertEqual(core.db.all('SELECT * FROM facts'),[])
                self.assertEqual(core.db.all('SELECT * FROM knowledge_sources'),[])
                self.assertEqual(core.db.all('SELECT * FROM memory_imports'),[])
            finally:core.close()

    def test_invalid_bundle_is_rejected_without_partial_write(self):
        self.memory.save(fact(),0);bundle=self.export()
        for name,value in [('facts',[{}]),('history',[{}]),('candidates',[{}]),('origins',[{}]),('checksum','bad')]:
            bad=copy.deepcopy(bundle);bad[name]=value
            with self.assertRaises(CoreError):validate(bad)
        self.assertEqual(len(self.memory.list('personal')),1)

    def test_cross_scope_id_conflict_and_explicit_mapping_on_fresh_target(self):
        self.memory.save(fact(),0);bundle=self.export()
        self.assertFalse(Bundle(self.core.db).preview('project-new',bundle)['can_apply'])
        with tempfile.TemporaryDirectory() as folder:
            core=Core.initialize(Path(folder))
            try:
                self.restore(bundle,core.db,'project-new')
                row=Memory(core.db).list('project-new')[0]
                self.assertEqual(row['purpose'],'project');self.assertEqual(row['providers'],[])
                self.assertEqual(Memory(core.db).list('personal'),[])
            finally:core.close()

    def test_bulk_restore_does_not_hold_chat_lock_or_expose_partial_state(self):
        self.memory.save(fact(),0);bundle=self.export();bundle['facts'][0].update(value='远端更新',revision=2)
        bundle['checksum']=digest({k:v for k,v in bundle.items() if k!='checksum'})
        plan=Bundle(self.core.db).preview('personal',bundle);entered=threading.Event();release=threading.Event();errors=[]
        original=Bundle.apply
        def slow(manager,*args):
            result=original(manager,*args);entered.set()
            if not release.wait(5):raise RuntimeError('test release timeout')
            return result
        def worker():
            try:memory_portability.command(self.root,{'action':'restore','scope':'personal','bundle':bundle,'token':plan['token']})
            except Exception as e:errors.append(e)
        with patch.object(Bundle,'apply',slow):
            thread=threading.Thread(target=worker);thread.start()
            try:
                self.assertTrue(entered.wait(5));started=time.monotonic()
                view=memory.retrieve(self.root,'personal','openai',True,'称呼')
                self.assertLess(time.monotonic()-started,.5)
                self.assertEqual(view['facts'][0]['value'],'青鸟')
            finally:release.set();thread.join(8)
        self.assertEqual(errors,[]);self.assertFalse(thread.is_alive())
        self.assertEqual(self.memory.list('personal')[0]['value'],'远端更新')
        self.assertEqual(self.memory.view('personal','openai')['facts'],[])

    def test_process_crash_before_commit_rolls_back_and_after_commit_retry_is_idempotent(self):
        self.memory.save(fact(),0);self.source();bundle=self.export()
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'data';root.mkdir();Core.initialize(root).close()
            path=base/'bundle.json';path.write_text(canonical(bundle),encoding='utf-8')
            import hashlib
            (root/'.synthetic-crash-fixture').write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='ascii')
            cmd=[sys.executable,'-m','tools.probe_memory_fault','--root',str(root),'--bundle',str(path)]
            before=subprocess.run(cmd+['--phase','before_commit'],capture_output=True,timeout=20)
            self.assertEqual(before.returncode,77,before.stderr.decode(errors='replace'))
            core=Core(root)
            try:
                self.assertEqual(core.db.integrity(),'ok');self.assertEqual(core.db.all('SELECT * FROM facts'),[])
                self.assertEqual(core.db.all('SELECT * FROM knowledge_sources'),[])
            finally:core.close()
            after=subprocess.run(cmd+['--phase','after_commit'],capture_output=True,timeout=20)
            self.assertEqual(after.returncode,78,after.stderr.decode(errors='replace'))
            core=Core(root)
            try:
                self.assertEqual(core.db.integrity(),'ok');saved=core.db.all('SELECT * FROM facts')
                self.restore(bundle,core.db);self.assertEqual(saved,core.db.all('SELECT * FROM facts'))
                self.assertEqual(len(core.db.all('SELECT * FROM memory_imports')),1)
            finally:core.close()


if __name__=='__main__':unittest.main()
