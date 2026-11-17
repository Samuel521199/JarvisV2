"""Owner project context reuses explicit records without altering attention."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from host.core import Core
from host.work_status import snapshot,acknowledge
from host.work_context import attach
from modules.workspace.store import Workspace
from modules.dialogue.store import Dialogues
from modules.continuity.attention import Attention,identity


class WorkContext(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'data';Core.initialize(self.root).close()
        folder=Path(self.tmp.name)/'project';folder.mkdir();store=Workspace(self.root)
        self.project=store.open(str(folder));store.update(self.project['id'],{'name':'游戏模型库'});store.close()

    def reply(self,ident,project=''):
        store=Dialogues(self.root)
        try:
            chat=store.create(project)
            store.begin({'chat_id':chat,'request_id':ident,'text':'检查模型库的 LOD 与贴图','provider':'fixture','model':'fixture','reasoning':'default'},[])
            store.finish(ident,{'status':'SUCCEEDED','text':'三角面和贴图已完成检查，等待你验收。'})
            return chat
        finally:store.close()

    def test_explicit_project_context_and_result_do_not_change_receipt_version(self):
        chat=self.reply('project-reply',self.project['id']);before={'id':'project-reply','source':'dialogue','state':'finished','raw_status':'SUCCEEDED','reason':'','result_revision':__import__('hashlib').sha256('三角面和贴图已完成检查，等待你验收。'.encode()).hexdigest()}
        item=next(x for x in snapshot(self.root,SimpleNamespace())['items'] if x['id']=='project-reply')
        self.assertEqual(item['context']['project_name'],'游戏模型库');self.assertEqual(item['context']['chat_id'],chat)
        self.assertEqual(item['title'],'检查模型库的 LOD 与贴图')
        self.assertIn('等待你验收',item['context']['summary']);self.assertEqual(identity(before),identity(item))
        receipt=item['attention'];acknowledge(self.root,SimpleNamespace(),{'action':'viewed','key':receipt['key'],'version':receipt['version']})
        self.assertEqual(snapshot(self.root,SimpleNamespace())['unread_count'],0)

    def test_project_words_in_text_do_not_bind_an_independent_chat(self):
        self.reply('independent-reply')
        item=next(x for x in snapshot(self.root,SimpleNamespace())['items'] if x['id']=='independent-reply')
        self.assertEqual(item['context']['project_id'],'');self.assertEqual(item['context']['project_name'],'独立会话')

    def test_removed_project_is_not_resurrected_by_context(self):
        self.reply('old-project-reply',self.project['id']);store=Workspace(self.root);store.update(self.project['id'],{'removed':True});store.close()
        item=next(x for x in snapshot(self.root,SimpleNamespace())['items'] if x['id']=='old-project-reply')
        self.assertEqual(item['context']['project_id'],'');self.assertNotEqual(item['context']['project_name'],'游戏模型库')

    def test_context_only_never_creates_a_receipt_or_changes_work(self):
        chat=self.reply('unread-reply',self.project['id']);item={'source':'dialogue','id':'unread-reply','chat_id':chat,'title':'原回复','state':'finished'}
        before=identity(item);self.assertTrue(attach(self.root,[item]));self.assertEqual(identity(item),before)
        self.assertFalse((self.root/'state/attention.sqlite3').exists())

    def test_explicit_turn_link_connects_studio_result_to_same_chat(self):
        chat=self.reply('job-plan',self.project['id']);job={'source':'studio3d','id':'job','turn_id':'job-plan','title':'3D工作室','state':'finished'}
        self.assertTrue(attach(self.root,[job]));self.assertEqual(job['context']['chat_id'],chat);self.assertEqual(job['context']['project_name'],'游戏模型库')

    def test_revised_goal_uses_explicit_original_work_root_and_chat(self):
        from modules.task_resource.plans import Plans
        chat=self.reply('root-origin',self.project['id']);core=Core(self.root)
        try:
            with core.db.transaction() as tx:
                root,_=Plans(core.db).create({'request_id':'root','goal':'原工作'},[],[],tx)
                revision,_=Plans(core.db).create({'request_id':'revision','goal':'修订'},[],[],tx)
                tx.execute('INSERT INTO chat_goals VALUES(?,?,?)',('origin',chat,root))
            rows=[{'id':'first','source':'tasks','goal_id':root,'title':'原版','state':'finished','work':{'root_goal':root}},
                  {'id':'second','source':'tasks','goal_id':revision,'title':'修订版','state':'finished','work':{'root_goal':root}}]
            self.assertTrue(attach(self.root,rows))
            self.assertEqual(rows[0]['context']['unit_id'],rows[1]['context']['unit_id'])
            self.assertEqual(rows[1]['context']['chat_id'],chat)
        finally:core.close()
