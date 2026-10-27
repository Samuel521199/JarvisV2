import copy
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_memory_domains as fixtures
from host import memory_domains, memory, knowledge_cleanup, memory_portability
from host.core import Core
from modules.context_knowledge.collection import Collection, checked
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.memory import Memory
from modules.context_knowledge.source_merge import SourceMerge, combine
from modules.context_knowledge.transfer import Transfer
from modules.context_knowledge.claims import Claims
from sdk.protocol import CoreError, canonical, digest


class SourceMergeTests(unittest.TestCase):
    setUp=fixtures.DomainTests.setUp
    tearDown=fixtures.DomainTests.tearDown
    source=fixtures.DomainTests.source
    branch=fixtures.DomainTests.branch
    turn=fixtures.DomainTests.turn

    def setup_source(self,text='# 开发\n接口 Alpha。\n# 发布\n状态待定。\n'):
        parent=self.source(text,'接口说明',self.project);branch=self.branch()
        manager=SourceMerge(self.core.db);local=manager.fork(branch,parent['id'],1)
        return manager,branch,parent['id'],local['id']

    def edit(self,ident,scope,text,providers=('openai',),paused=False):
        lib=Knowledge(self.core.db);row=lib.detail(scope,ident)
        return lib.save({'id':ident,'scope':scope,'title':row['title'],'text':text,'providers':list(providers),'paused':paused},row['revision'])

    def apply(self,m,branch,choice='branch'):
        p=m.preview(branch);choices={r['id']:choice for r in p['items'] if r['state'] not in {'forgotten','unchanged','missing_base'}}
        return m.apply(branch,p['token'],choices)

    def test_disjoint_chapters_combine_and_parent_stays_inert_until_enabled(self):
        m,b,p,c=self.setup_source()
        self.edit(p,self.project,'# 开发\n接口 Alpha。\n# 发布\n状态已批准。\n')
        self.edit(c,b,'# 开发\n接口 Beta。\n# 发布\n状态待定。\n')
        plan=m.preview(b);self.assertEqual(plan['items'][0]['state'],'combined')
        result=self.apply(m,b,'combined');self.assertEqual(result['changed'],1)
        row=Knowledge(self.core.db).detail(self.project,p)
        self.assertIn('Beta',row['text']);self.assertIn('已批准',row['text'])
        self.assertEqual(row['providers'],[]);self.assertEqual(row['status'],'paused')
        self.assertEqual(self.memory.view(b,'openai',True,'接口')['facts'],[])

    def test_overlapping_edits_conflict_no_guess_and_stale_preview_rejected(self):
        m,b,p,c=self.setup_source('版本 Alpha\n')
        self.edit(p,self.project,'版本 Parent\n');self.edit(c,b,'版本 Branch\n')
        plan=m.preview(b);self.assertEqual(plan['items'][0]['state'],'conflict')
        with self.assertRaises(CoreError):self.apply(m,b,'combined')
        with self.assertRaises(CoreError):m.apply(b,plan['token'],{})
        self.edit(p,self.project,'版本 Parent2\n')
        with self.assertRaises(CoreError):m.apply(b,plan['token'],{c:'branch'})
        self.assertEqual(Knowledge(self.core.db).detail(self.project,p)['text'],'版本 Parent2\n')

    def test_source_shadow_and_parent_permission_filters_before_encoding_and_claims(self):
        m,b,p,c=self.setup_source('接口版本 Alpha，必须先验证。')
        self.edit(c,b,'接口版本 Branch，必须先验证。',providers=('openai','bailian'))
        self.assertEqual(Knowledge(self.core.db).detail(b,c)['providers'],['openai'])
        self.assertNotIn('Alpha',canonical(self.memory.view(b,'openai',True,'接口版本')))
        claims=Claims(self.core.db);claims.compile(b,c,2);claim=claims.list(b)[0]
        from test_memory_development_ui import fact
        claims.accept(b,claim['id'],claim['revision'],{**fact('知识','接口版本 Branch，必须先验证。'),'scope':b,'kind':'knowledge','purpose':'project'},0)
        self.edit(p,self.project,'接口版本 Alpha，必须先验证。',providers=())
        seen=[]
        self.assertEqual(self.memory.view(b,'openai',True,'接口版本',lambda rows,q:seen.extend(rows))['facts'],[])
        self.assertEqual(seen,[]);self.assertEqual(self.memory.references(b,'openai'),[])
        with self.assertRaises(CoreError):claims.model_candidates(b,c,2,'openai',{'claims':[{'key':'引用','quote':'接口版本 Branch，必须先验证。'}]})

    def test_parent_forgetting_cascades_and_stale_merge_receipt_does_not_replay(self):
        m,b,p,c=self.setup_source('需遗忘的独有原文。');self.edit(c,b,'分支同样需遗忘。')
        plan=m.preview(b);choices={c:'branch'};m.apply(b,plan['token'],choices)
        Knowledge(self.core.db).delete(self.project,p,2)
        self.assertTrue(m.apply(b,plan['token'],choices)['replayed'])
        self.assertEqual(m.preview(b)['items'][0]['state'],'forgotten')
        for table in ('knowledge_sources','knowledge_chunks','memory_history'):
            self.assertNotIn('需遗忘',canonical(self.core.db.all('SELECT * FROM '+table)))
        with self.assertRaises(CoreError):m.fork(b,p,1)
        self.assertEqual(self.core.db.integrity(),'ok')

    def test_archived_branch_forgetting_and_parent_scoped_chat_cleanup(self):
        m,b,p,c=self.setup_source();self.edit(c,b,'接口版本是 Branch')
        chat=self.chats.create(self.project)
        memory_domains.command(self.root,{'action':'bind','chat_id':chat,'scope':b,'revision':0})
        self.turn(chat,'fork-response','接口版本')
        view=memory.dialogue_view(self.root,self.chats.read(chat),{'id':'openai'},True,'接口版本')
        self.assertEqual(view['facts'][0]['id'],c)
        self.chats.context('fork-response',view);self.chats.finish('fork-response',{'status':'SUCCEEDED','text':'分支回答旧正文'})
        self.domains.archive(b,1,True);Knowledge(self.core.db).delete(self.project,p,1)
        first={'goals':'','turns':''};preview=knowledge_cleanup.preview(self.core.db,self.root,self.project,first)
        self.assertEqual(preview['counts']['turns'],1)
        knowledge_cleanup.apply(self.core.db,self.root,self.project,first,preview['token'])
        self.assertNotIn('旧正文',self.chats.turn('fork-response')['reply'])
        self.assertEqual(self.core.db.one('SELECT status FROM knowledge_sources WHERE id=?',(c,))['status'],'deleted')

    def test_persistent_vectors_cannot_bypass_parent_permission(self):
        from modules.context_knowledge.vectors import Vectors
        m,b,p,c=self.setup_source();self.edit(c,b,'接口版本是 Branch')
        vectors=Vectors(self.core.db);vectors.build('synthetic-384',384,lambda texts:[[1.0]+[0.0]*383 for _ in texts])
        self.assertTrue(vectors.search(b,'openai','synthetic-384',[1.0]+[0.0]*383)[0])
        self.edit(p,self.project,'主项目撤销访问',providers=())
        self.assertEqual(vectors.search(b,'openai','synthetic-384',[1.0]+[0.0]*383)[0],[])

    def test_delete_in_branch_is_only_merged_after_owner_choice(self):
        m,b,p,c=self.setup_source();Knowledge(self.core.db).delete(b,c,1)
        self.assertEqual(m.preview(b)['items'][0]['state'],'delete')
        self.assertEqual(self.apply(m,b,'parent')['changed'],0)
        self.assertTrue(Knowledge(self.core.db).detail(self.project,p)['text'])
        self.assertEqual(self.apply(m,b)['changed'],1)
        with self.assertRaises(CoreError):Knowledge(self.core.db).detail(self.project,p)

    def test_new_source_merge_idempotence_and_later_edits_keep_identity(self):
        b=self.branch();c=self.source('新资料正文','新资料',b)['id'];m=SourceMerge(self.core.db)
        plan=m.preview(b);choices={c:'branch'};r=m.apply(b,plan['token'],choices)
        self.assertTrue(m.apply(b,plan['token'],choices)['replayed'])
        target=Knowledge(self.core.db).list(self.project)[0]['id']
        self.edit(c,b,'新资料正文第二版');self.assertEqual(self.apply(m,b)['changed'],1)
        self.assertEqual(len(Knowledge(self.core.db).list(self.project)),1)
        self.assertEqual(Knowledge(self.core.db).detail(self.project,target)['text'],'新资料正文第二版')

    def test_second_source_failure_rolls_back_documents_chunks_policy_and_receipt(self):
        b=self.branch();self.source('第一个正文','一',b);self.source('第二个正文','二',b);m=SourceMerge(self.core.db)
        original=Knowledge.save_in;calls=[]
        def fail(*args,**kwargs):
            calls.append(1)
            if len(calls)==2:raise RuntimeError('injected')
            return original(*args,**kwargs)
        with patch.object(Knowledge,'save_in',fail):
            with self.assertRaises(RuntimeError):self.apply(m,b)
        self.assertEqual(Knowledge(self.core.db).list(self.project),[])
        self.assertEqual(self.core.db.all('SELECT * FROM memory_source_branches'),[])
        self.assertEqual(self.core.db.all("SELECT * FROM memory_imports WHERE id LIKE 'source-merge-%'"),[])

    def test_collection_preserves_lineage_and_local_tombstone_beats_old_archive(self):
        m,b,p,c=self.setup_source();self.edit(c,b,'分支资料')
        pack=Collection(self.core.db).export(self.project)
        self.assertEqual(pack['format'],'jarvis.memory-collection.v2')
        with self.assertRaises(CoreError):Transfer(self.core.db).export(b)
        with tempfile.TemporaryDirectory() as folder:
            target=Core.initialize(Path(folder))
            try:
                coll=Collection(target.db);plan=coll.preview('project-target',pack)
                coll.restore('project-target',pack,plan['token'])
                self.assertEqual(target.db.all('SELECT * FROM memory_source_branches'),pack['source_branches'])
                row=Knowledge(target.db).detail('project-target',p);Knowledge(target.db).delete('project-target',p,row['revision'])
                plan=coll.preview('project-target',pack);coll.restore('project-target',pack,plan['token'])
                self.assertEqual(target.db.one('SELECT status FROM knowledge_sources WHERE id=?',(c,))['status'],'deleted')
                self.assertNotIn('分支资料',canonical(target.db.all('SELECT * FROM memory_history')))
            finally:target.close()

    def test_v1_compatible_and_malicious_cross_domain_lineage_is_rejected(self):
        m,b,p,c=self.setup_source();pack=Collection(self.core.db).export(self.project)
        bad=copy.deepcopy(pack);bad['source_branches'][0]['source_id']=p;bad['checksum']=digest({k:v for k,v in bad.items() if k!='checksum'})
        with self.assertRaises(CoreError):checked(bad)
        legacy=copy.deepcopy(pack);legacy.pop('source_branches');legacy['format']='jarvis.memory-collection.v1';legacy['checksum']=digest({k:v for k,v in legacy.items() if k!='checksum'})
        self.assertEqual(checked(legacy)['format'],'jarvis.memory-collection.v1')
        result=memory_portability.command(self.root,{'action':'preview','scope':self.project,'bundle':legacy})
        self.assertTrue(result['can_apply'])

    def test_schema_three_upgrade_preserves_source_history_and_adds_empty_lineage(self):
        from adapters.storage.memory_schema import ensure
        self.source('升级保留原文','原资料',self.project)
        before=self.core.db.all('SELECT * FROM knowledge_sources')
        with self.core.db.transaction() as tx:
            tx.execute('DROP TABLE memory_source_branches')
            tx.execute("UPDATE meta SET value='3' WHERE key='memory_schema'")
        ensure(self.core.db.connection)
        self.assertEqual(self.core.db.one("SELECT value FROM meta WHERE key='memory_schema'")['value'],'4')
        self.assertEqual(before,self.core.db.all('SELECT * FROM knowledge_sources'))
        self.assertEqual(self.core.db.all('SELECT * FROM memory_source_branches'),[])

    def test_host_actions_reject_other_scope_and_wrong_revision(self):
        m,b,p,c=self.setup_source()
        r=memory_domains.command(self.root,{'action':'source_inherited','scope':b})
        self.assertEqual(r['sources'][0]['branch_id'],c)
        with self.assertRaises(CoreError):memory_domains.command(self.root,{'action':'source_fork','scope':b,'id':p,'revision':999})
        with self.assertRaises(CoreError):memory_domains.command(self.root,{'action':'source_merge_preview','scope':self.project})

    def test_line_merger_preserves_unicode_newlines_and_refuses_ambiguous_boundaries(self):
        self.assertEqual(combine('甲\r\n乙\r\n丙','改甲\r\n乙\r\n丙','甲\r\n乙\r\n改丙'),'改甲\r\n乙\r\n改丙')
        self.assertIsNone(combine('a\nb','a\nx\nb','a\ny\nb'))
        self.assertIsNone(combine('a\nb','b','z\na\nb'))

    def test_process_exit_before_commit_rolls_back_then_committed_receipt_deduplicates(self):
        m,b,p,c=self.setup_source();self.edit(c,b,'崩溃恢复后的分支原文')
        plan=m.preview(b);value={'scope':b,'token':plan['token'],'choices':{c:'branch'}}
        request=self.root/'merge-fixture.json';request.write_text(canonical(value),encoding='utf-8')
        (self.root/'.synthetic-crash-fixture').write_text(hashlib.sha256(request.read_bytes()).hexdigest(),encoding='ascii')
        command=[sys.executable,'-m','tools.probe_memory_fault','--root',str(self.root),'--bundle',str(request),'--operation','source-merge']
        before=subprocess.run(command+['--phase','before_commit'],capture_output=True,timeout=20)
        self.assertEqual(before.returncode,77,before.stderr.decode(errors='replace'))
        self.assertNotIn('崩溃恢复',Knowledge(self.core.db).detail(self.project,p)['text'])
        self.assertEqual(self.core.db.integrity(),'ok')
        after=subprocess.run(command+['--phase','after_commit'],capture_output=True,timeout=20)
        self.assertEqual(after.returncode,78,after.stderr.decode(errors='replace'))
        self.assertEqual(Knowledge(self.core.db).detail(self.project,p)['text'],'崩溃恢复后的分支原文')
        self.assertTrue(m.apply(b,plan['token'],{c:'branch'})['replayed'])
        self.assertEqual(Knowledge(self.core.db).detail(self.project,p)['revision'],2)


if __name__=='__main__':unittest.main()
