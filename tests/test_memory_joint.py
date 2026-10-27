import tempfile
import unittest
from pathlib import Path
import test_memory_domains as fixtures
from test_memory_development_ui import fact
from modules.context_knowledge import joint
from host import memory, memory_domains
from modules.workspace.store import Workspace
from sdk.protocol import CoreError, canonical


class JointTests(unittest.TestCase):
    setUp=fixtures.DomainTests.setUp
    tearDown=fixtures.DomainTests.tearDown
    save=fixtures.DomainTests.save
    source=fixtures.DomainTests.source
    turn=fixtures.DomainTests.turn

    def test_explicit_two_projects_not_third_or_private_and_revoke(self):
        self.save('A接口');self.save('B接口',scope='project-B');self.save('C秘密',scope='project-C')
        self.memory.save(fact('个人秘密','生日秘密'),0)
        both=joint.create([self.project,'project-B']);seen=[]
        def encoder(rows,q):seen.extend(rows);return {'status':'unavailable'}
        view=self.memory.view(both,'openai',True,'接口',encoder)
        self.assertEqual({r['value'] for r in view['facts']},{'A接口','B接口'})
        self.assertEqual({r['origin_scope'] for r in view['facts']},{self.project,'project-B'})
        self.assertNotIn('秘密',canonical(seen))
        self.assertTrue(self.memory.references_valid(both,'openai',True,view['facts']))
        self.memory.forget('project-B','接口版本',1)
        self.assertFalse(self.memory.references_valid(both,'openai',True,view['facts']))

    def test_union_cannot_be_written_or_nested_and_has_one_shared_budget(self):
        scopes=[self.project,'project-B'];both=joint.create(scopes)
        for scope in scopes:
            for i in range(20):self.save('共同主题'+str(i),scope=scope,key='主题'+str(i))
        v=self.memory.view(both,'openai',True,'共同主题')
        self.assertLessEqual(len(v['facts']),12);self.assertLessEqual(v['retrieval']['bytes'],5000)
        with self.assertRaises(CoreError):self.save(scope=both)
        with self.assertRaises(CoreError):self.memory.propose('turn:test','1',both,'联合内容')
        for scopes in (['one'],['one']*2,['a','b','c','d','e'],[both,'c']):
            with self.assertRaises(CoreError):joint.create(scopes)

    def test_chat_bound_union_is_actual_context_and_project_removal_invalidates(self):
        with tempfile.TemporaryDirectory() as folder:
            w=Workspace(self.root)
            try:other=w.open(folder)['id']
            finally:w.close()
            self.save('A接口');self.save('B接口',scope=other);both=joint.create([self.project,other])
            chat=self.chats.create(self.project)
            memory_domains.command(self.root,{'action':'bind','chat_id':chat,'scope':both,'revision':0})
            self.turn(chat,'joint','接口');v=memory.dialogue_view(self.root,self.chats.read(chat),{'id':'openai'},True,'接口')
            sent=self.chats.context('joint',v);self.assertIn('A接口',canonical(sent));self.assertIn('B接口',canonical(sent))
            memory.refresh_view(self.root,v)
            self.assertEqual(memory_domains.command(self.root,{'action':'binding','chat_id':chat})['scopes'],sorted([self.project,other]))
            w=Workspace(self.root)
            try:w.update(other,{'removed':True})
            finally:w.close()
            with self.assertRaises(CoreError):memory.refresh_view(self.root,v)

    def test_joint_source_permissions_before_semantic_encoder(self):
        from modules.context_knowledge.knowledge import Knowledge
        for scope,text in ((self.project,'甲范围资料'),('project-B','乙范围资料'),('project-C','丙秘密')):
            Knowledge(self.core.db).save(dict(id='',scope=scope,title=text,text=text,providers=['openai'],paused=False),0)
        both=joint.create([self.project,'project-B']);calls=[]
        def semantic(db,scope,provider,query):calls.append(scope);return [],{'status':'not_loaded'}
        v=self.memory.view(both,'openai',True,'资料',source_semantic=semantic)
        self.assertEqual(calls,[both]);self.assertEqual(len(v['facts']),2);self.assertNotIn('丙',canonical(v))
        self.assertEqual(self.memory.view(both,'bailian',True,'资料')['facts'],[])

    def test_origin_scope_cleanup_finds_joint_and_branch_replies_but_not_other_stale_data(self):
        from host import knowledge_cleanup
        from modules.context_knowledge.domains import Domains
        self.save('A证据');self.save('B证据',scope='project-B');self.save('C证据',scope='project-C')
        branch=Domains(self.core.db).create(self.project,'branch','feature',True)['id']
        for i,scope in enumerate((joint.create([self.project,'project-B']),branch,'project-C')):
            chat=self.chats.create(self.project);ident='cleanup-'+str(i);self.turn(chat,ident,'证据')
            view=self.memory.view(scope,'openai',True,'证据');view.update(scope=scope,provider='openai',enabled=True)
            self.chats.context(ident,view);self.chats.finish(ident,{'status':'SUCCEEDED','text':'派生答案'+str(i)})
        self.memory.forget(self.project,'接口版本',1);self.memory.forget('project-C','接口版本',1)
        cursor={'goals':'','turns':''};plan=knowledge_cleanup.preview(self.core.db,self.root,self.project,cursor)
        self.assertEqual({r['id'] for r in plan['targets']['turns']},{'cleanup-0','cleanup-1'})
        knowledge_cleanup.apply(self.core.db,self.root,self.project,cursor,plan['token'])
        self.assertNotIn('派生答案0',self.chats.turn('cleanup-0')['reply'])
        self.assertEqual(self.chats.turn('cleanup-2')['reply'],'派生答案2')


if __name__=='__main__':unittest.main()
