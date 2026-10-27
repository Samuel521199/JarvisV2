import tempfile
import unittest
from pathlib import Path
import test_knowledge as fixtures
from test_memory_development_ui import fact
from host import memory, memory_domains, goal_context, knowledge_cleanup
from modules.context_knowledge.domains import Domains
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.collection import Collection
from host.core import Core
from modules.workspace.store import Workspace
from sdk.protocol import CoreError, canonical


class DomainTests(unittest.TestCase):
    def setUp(self):
        fixtures.Library.setUp(self)
        self.folder=tempfile.TemporaryDirectory();workspace=Workspace(self.root)
        try:self.project=workspace.open(self.folder.name)['id']
        finally:workspace.close()
        self.domains=Domains(self.core.db)

    def tearDown(self):fixtures.Library.tearDown(self);self.folder.cleanup()
    source=fixtures.Library.source
    turn=fixtures.Library.turn

    def save(self,value='主项目值',revision=0,scope=None,key='接口版本'):
        return self.memory.save({**fact(key,value),'scope':scope or self.project,'purpose':'project','kind':'knowledge'},revision)

    def branch(self):return self.domains.create(self.project,'branch','feature',True)['id']

    def test_snapshot_keeps_base_revision_and_local_override_does_not_change_parent(self):
        original=self.save();branch=self.branch();self.save('主项目已更新',1)
        view=self.memory.view(branch,'openai',True,'接口版本')
        self.assertEqual(view['facts'][0]['value'],'主项目值')
        self.assertTrue(self.memory.references_valid(branch,'openai',True,[original]))
        self.save('分支方案',scope=branch)
        self.assertEqual(self.memory.view(branch,'openai',True,'接口版本')['facts'][0]['value'],'分支方案')
        self.assertEqual(self.memory.list(self.project)[0]['value'],'主项目已更新')
        self.memory.forget(branch,'接口版本',1)
        self.assertEqual(self.memory.view(branch,'openai',True,'接口版本')['facts'],[])

    def test_parent_forgetting_removes_snapshot_body_and_prevents_retrieval(self):
        original=self.save();branch=self.branch();self.memory.forget(self.project,'接口版本',1)
        self.assertEqual(self.memory.view(branch,'openai',True,'接口版本')['facts'],[])
        self.assertFalse(self.memory.references_valid(branch,'openai',True,[original]))
        self.assertNotIn('主项目值',canonical(self.core.db.all('SELECT * FROM memory_history')))

    def test_permission_revocation_filters_snapshot_before_encoder(self):
        self.save();branch=self.branch()
        row=self.memory.list(self.project)[0]
        item={k:row[k] for k in ('scope','key','value','kind','purpose','providers','paused','expires')};item.update(providers=[],paused=False)
        self.memory.save(item,1);seen=[]
        def encoder(rows,q):seen.extend(rows);return {'status':'unavailable'}
        self.memory.view(branch,'openai',True,'接口版本',encoder)
        self.assertEqual(seen,[])

    def test_source_snapshot_is_traceable_after_parent_edit_and_forgetting_propagates(self):
        source=self.source('接口版本是 Alpha','接口说明',self.project);branch=self.branch()
        Knowledge(self.core.db).save({'id':source['id'],'scope':self.project,'title':'接口说明','text':'接口版本是 Beta','providers':['openai'],'paused':False},1)
        view=self.memory.view(branch,'openai',True,'接口版本');selected=view['facts'][0]
        self.assertIn('Alpha',selected['value']);self.assertEqual(selected['evidence']['snapshot_domain'],branch)
        detail=self.domains.historical_source(branch,source['id'],1);self.assertEqual(detail['text'],selected['value'])
        Knowledge(self.core.db).delete(self.project,source['id'],2)
        self.assertEqual(self.memory.view(branch,'openai',True,'接口版本')['facts'],[])
        with self.assertRaises(CoreError):self.domains.historical_source(branch,source['id'],1)

    def test_world_and_task_do_not_inherit_personal_profile_or_style(self):
        self.memory.save({**fact('喜好','现实秘密'),'purpose':'style'},0)
        for kind in ('world','task'):
            domain=self.domains.create('personal',kind,'同名人物',False)['id']
            self.assertEqual(self.memory.view(domain,'openai')['facts'],[])
            self.save('虚拟人物喜好',scope=domain,key='喜好')
            self.assertNotIn('现实秘密',canonical(self.memory.view(domain,'openai')))
            self.assertNotIn('虚拟人物',canonical(self.memory.view('personal','openai')))

    def test_archive_rejects_host_reads_and_reactivate_requires_revision(self):
        branch=self.branch();self.save(scope=branch);self.domains.archive(branch,1,True)
        with self.assertRaises(CoreError):memory.scope_for(self.root,branch)
        with self.assertRaises(CoreError):self.domains.archive(branch,1,False)
        self.domains.archive(branch,2,False);self.assertEqual(memory.scope_for(self.root,branch),branch)

    def test_conversation_switch_changes_real_context_and_discards_old_history(self):
        self.save();branch=self.branch();self.save('分支方案',scope=branch);chat=self.chats.create(self.project)
        self.turn(chat,'first','接口版本');view=memory.dialogue_view(self.root,self.chats.read(chat),{'id':'openai'},True,'接口版本')
        self.chats.context('first',view);self.chats.finish('first',{'status':'SUCCEEDED','text':'主项目答复'})
        memory_domains.command(self.root,{'action':'bind','chat_id':chat,'scope':branch,'revision':0})
        self.turn(chat,'second','接口版本');view=memory.dialogue_view(self.root,self.chats.read(chat),{'id':'openai'},True,'接口版本')
        sent=self.chats.context('second',view)
        self.assertEqual(len(sent),1);self.assertIn('分支方案',canonical(sent));self.assertNotIn('主项目答复',canonical(sent))
        memory.refresh_view(self.root,view)

    def test_conversation_binding_rejects_other_project_and_running_reply(self):
        chat=self.chats.create(self.project);world=self.domains.create('personal','world','私域',False)['id']
        with self.assertRaises(CoreError):memory_domains.command(self.root,{'action':'bind','chat_id':chat,'scope':world,'revision':0})
        branch=self.branch();self.turn(chat,'busy')
        with self.assertRaises(CoreError):memory_domains.command(self.root,{'action':'bind','chat_id':chat,'scope':branch,'revision':0})

    def test_task_snapshot_uses_branch_and_never_promotes_chat_only_condition(self):
        self.save();branch=self.branch();self.save('分支方案',scope=branch)
        item={**fact('仅聊天','不能用于任务'),'scope':branch,'purpose':'project','applicability':{'valid_from':None,'conditions':{'channel':'chat'}}}
        self.memory.save(item,0)
        view=goal_context.snapshot(self.core,branch,True,[{'id':'openai'}],'接口版本')
        self.assertIn('分支方案',canonical(view));self.assertNotIn('不能用于任务',canonical(view))

    def test_no_nested_domains_or_personal_project_branch(self):
        with self.assertRaises(CoreError):self.domains.create('personal','branch','错误',True)
        branch=self.branch()
        with self.assertRaises(CoreError):self.domains.create(branch,'branch','错误',True)
        with self.assertRaises(CoreError):self.domains.create('personal','world','错误',True)

    def test_collection_restores_base_branch_snapshot_and_history_without_permissions(self):
        self.save();branch=self.branch();self.save('后来修改',1);self.save('分支额外事实',scope=branch,key='材料')
        pack=Collection(self.core.db).export(self.project)
        with tempfile.TemporaryDirectory() as folder:
            target=Core.initialize(Path(folder))
            try:
                collection=Collection(target.db);plan=collection.preview('project-new',pack)
                self.assertTrue(plan['can_apply']);collection.restore('project-new',pack,plan['token'])
                d=Domains(target.db);self.assertEqual(d.list('project-new')[0]['archived'],1)
                d.archive(branch,1,False)
                from modules.context_knowledge.memory import Memory
                mem=Memory(target.db);row=mem.list('project-new')[0]
                self.assertEqual(row['value'],'后来修改');self.assertEqual(mem.view(branch,'openai',True,'接口版本')['facts'],[])
                item={k:row[k] for k in ('scope','key','value','kind','purpose','providers','paused','expires')};item.update(providers=['openai'],paused=False)
                mem.save(item,row['revision'])
                self.assertEqual(mem.view(branch,'openai',True,'接口版本')['facts'][0]['value'],'主项目值')
                mem.forget('project-new','接口版本',row['revision']+1)
                self.assertEqual(mem.view(branch,'openai',True,'接口版本')['facts'],[])
                self.assertEqual(target.db.integrity(),'ok')
            finally:target.close()

    def test_collection_conflict_rolls_back_all_domains(self):
        self.save();branch=self.branch();pack=Collection(self.core.db).export(self.project)
        self.save('独立纠正',1);plan=Collection(self.core.db).preview(self.project,pack)
        self.assertFalse(plan['can_apply'])
        with self.assertRaises(CoreError):Collection(self.core.db).restore(self.project,pack,plan['token'])
        self.assertEqual(self.domains.get(branch)['revision'],1)

    def test_cleanup_preserves_valid_historical_snapshot_then_clears_after_forget(self):
        self.save();branch=self.branch();chat=self.chats.create(self.project)
        memory_domains.command(self.root,{'action':'bind','chat_id':chat,'scope':branch,'revision':0})
        self.turn(chat,'snapshot-turn','接口版本')
        view=memory.dialogue_view(self.root,self.chats.read(chat),{'id':'openai'},True,'接口版本')
        self.chats.context('snapshot-turn',view);self.chats.finish('snapshot-turn',{'status':'SUCCEEDED','text':'旧分支方案'})
        self.save('主项目已更新',1)
        first={'goals':'','turns':''}
        preview=knowledge_cleanup.preview(self.core.db,self.root,branch,first)
        self.assertEqual(preview['counts']['turns'],0)
        self.memory.forget(self.project,'接口版本',2)
        preview=knowledge_cleanup.preview(self.core.db,self.root,branch,first)
        self.assertEqual(preview['counts']['turns'],1)
        result=knowledge_cleanup.apply(self.core.db,self.root,branch,first,preview['token'])
        self.assertEqual(result['receipt']['state'],'completed')
        self.assertNotIn('旧分支方案',self.chats.turn('snapshot-turn')['reply'])


if __name__=='__main__':unittest.main()
