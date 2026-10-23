"""Natural conversation proposals remain scoped, revocable and attached to real receipts."""
import copy
import sqlite3
import unittest
from unittest.mock import patch

import test_goal_plans as base
from test_development import Provider
from test_memory_development_ui import fact
from host import assistant, goals, goal_context, memory
from host.core import Core
from host.dialogue import DialogueHost
from modules.dialogue.store import Dialogues
from modules.context_knowledge.memory import Memory
from modules.task_resource.plans import Plans
from sdk.protocol import CoreError, canonical, decode


def action(kind='goal',target='',goal='将文本转为大写并保存',text='Jarvis 中文'):
    return {'kind':kind,'target':target,'goal':goal,'input_text':text}


class AssistantGoals(unittest.TestCase):
    setUp=base.GoalPlans.setUp
    tearDown=base.GoalPlans.tearDown
    publish=base.GoalPlans.publish
    req=base.GoalPlans.req
    create=base.GoalPlans.create
    detail=base.GoalPlans.detail
    approve=base.GoalPlans.approve
    plan=base.GoalPlans.plan
    code=base.GoalPlans.code

    def chat(self,ident='chat-turn-1',proposal=None,chat=None,view=None):
        store=Dialogues(self.root)
        try:
            chat=chat or store.create()
            store.begin({'chat_id':chat,'request_id':ident,'text':'麻烦把这份文字处理好','provider':'openai','model':'test-model','reasoning':'default','assistant_mode':True},[])
            if view:store.context(ident,view)
            store.finish(ident,{'status':'SUCCEEDED','text':'已整理成待核对目标。','provider':'openai','model':'test-model','assistant_action':proposal or action()})
            return chat
        finally:store.close()

    def test_natural_reply_creates_one_goal_and_no_execution_grant(self):
        chat=self.chat();one=assistant.goal_from_turn(self.root,'chat-turn-1');two=assistant.goal_from_turn(self.root,'chat-turn-1')
        self.assertEqual(one['id'],two['id']);self.assertTrue(two['existing'])
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        grants=self.core.db.all('SELECT body FROM grants WHERE id LIKE ?',(one['id']+'%',))
        self.assertEqual(decode(grants[0]['body'])['capabilities'],['model.generate.v1'])
        self.assertEqual(assistant.context(self.root,chat)[0]['id'],one['id'])
        self.plan(one['id']);tid=self.approve(one['id']);self.core.run_task(tid)
        store=Dialogues(self.root)
        try:result=assistant.projection(self.root,store.read(chat))
        finally:store.close()
        self.assertEqual(result['turns'][0]['linked_goal']['output'],'JARVIS 中文')
        self.assertEqual(result['turns'][0]['linked_goal']['status'],'SUCCEEDED')
        from modules.workspace.sessions import Sessions
        folders=Sessions(self.root)
        try:
            files=folders.files(chat)['files']
            self.assertTrue(any(f['path'].startswith('artifacts/'+tid+'/') for f in files))
            self.assertFalse(folders.info(chat)['delivery_error'])
        finally:folders.close()

    def test_chat_hallucinated_targets_and_invalid_envelope_do_not_dispatch(self):
        raw={'schema':'jarvis.assistant-turn.v1','reply':'你好','action':action('chat',goal='',text='')}
        self.assertEqual(assistant.parse(canonical(raw),[])[1]['kind'],'chat')
        raw['action']=action('cancel',target='goal-not-in-chat')
        self.code('assistant_invalid',assistant.parse,canonical(raw),[])
        raw['action']=action('goal',target='grant-anything')
        self.code('assistant_invalid',assistant.parse,canonical(raw),[])
        self.assertEqual(self.core.db.all('SELECT * FROM goal_plans'),[])

    def test_dialogue_single_call_structured_response_and_durable_callback_failure(self):
        store=Dialogues(self.root);chat=store.create();store.close();seen=[]
        class Client:
            def __init__(self,*_):pass
            def available(self):return True
            def complete(self,messages,checkpoint,**kwargs):
                checkpoint();seen.append((messages,kwargs))
                return {'status':'SUCCEEDED','text':canonical({'schema':'jarvis.assistant-turn.v1','reply':'我会先准备计划。','action':action()})}
        host=DialogueHost(self.root,on_goal=lambda _:(_ for _ in ()).throw(CoreError('busy','slot busy')))
        try:
            with patch('host.dialogue.NativeModel',Client):
                host.submit({'chat_id':chat,'request_id':'natural-request','text':'帮我弄一下这份文字','provider':'openai','model':'test-model','reasoning':'default','assistant_mode':True})
                host.pool.shutdown(wait=True)
            store=Dialogues(self.root)
            try:self.assertEqual(store.turn('natural-request')['status'],'SUCCEEDED')
            finally:store.close()
            self.assertEqual(len(seen),1);self.assertTrue(seen[0][1]['json_mode'])
            self.assertEqual(len(goals.listing(self.root)),1)
        finally:host.close()

    def test_amend_same_goal_exactly_once_then_cancel_and_no_cross_chat(self):
        chat=self.chat();ident=assistant.goal_from_turn(self.root,'chat-turn-1')['id'];self.plan(ident)
        p=self.detail(ident)['plan'];amend={**action('amend',ident,goal='转换文字并保留中文',text='hello 中文'),'target_revision':p['revision']}
        self.chat('change-turn',amend,chat)
        one=assistant.accept(self.root,{'turn_id':'change-turn'});two=assistant.accept(self.root,{'turn_id':'change-turn'})
        self.assertEqual(one,two);self.assertEqual(one['id'],ident);self.assertEqual(one['generation'],1)
        self.assertEqual(self.detail(ident)['plan']['request']['input_text'],'hello 中文')
        self.assertEqual(len(self.core.db.all('SELECT * FROM goal_plans')),1)
        other=self.chat('other-chat',{**action('cancel',ident),'target_revision':self.detail(ident)['plan']['revision']})
        self.code('denied',assistant.accept,self.root,{'turn_id':'other-chat'})
        self.assertNotEqual(chat,other)
        self.chat('cancel-turn',{**action('cancel',ident),'target_revision':self.detail(ident)['plan']['revision']},chat)
        self.assertTrue(assistant.accept(self.root,{'turn_id':'cancel-turn'})['cancelled'])
        self.assertEqual(self.detail(ident)['plan']['status'],'CANCELLED')
        self.assertEqual(assistant.accept(self.root,{'turn_id':'cancel-turn'})['id'],ident)
        store=Dialogues(self.root)
        try:
            projection=assistant.projection(self.root,store.read(chat))
            self.assertTrue(next(t for t in projection['turns'] if t['id']=='cancel-turn')['applied_action']['cancelled'])
        finally:store.close()

    def test_amend_record_and_goal_are_atomic_on_database_failure(self):
        chat=self.chat();ident=assistant.goal_from_turn(self.root,'chat-turn-1')['id'];p=self.detail(ident)['plan']
        self.chat('change-turn',{**action('amend',ident,goal='changed'),'target_revision':p['revision']},chat)
        self.core.db.connection.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON assistant_operations BEGIN SELECT RAISE(ABORT,'fail'); END")
        with self.assertRaises(sqlite3.IntegrityError):assistant.accept(self.root,{'turn_id':'change-turn'})
        self.assertEqual(self.detail(ident)['plan']['generation'],0)
        self.assertEqual(self.detail(ident)['plan']['request'],p['request'])
        self.assertIsNone(self.core.db.one('SELECT id FROM grants WHERE id=?',(ident+'-g1-plan',)))

    def contextual(self,scope='personal',provider='openai',enabled=True):
        return goals.command(self.root,{'action':'create','request':self.req(provider=provider),
            'context':{'scope':scope,'enabled':enabled,'chat_id':'','turn_id':''}})['id']

    def test_memory_destination_intersection_and_revocation_before_admission(self):
        Memory(self.core.db).save(fact('偏好','保留中文'),0)
        ident=self.contextual();p,model=self.plan(ident)
        self.assertIn('保留中文',model.prompts[0]);self.assertEqual(len(self.detail(ident)['context']['view']['facts']),1)
        self.code('goal_context_changed',goal_context.check,self.core,ident,['bailian'])
        Memory(self.core.db).forget('personal','偏好',1)
        self.code('goal_context_changed',self.approve,ident)
        self.assertEqual(self.core.db.all('SELECT * FROM tasks'),[])
        reset=goals.command(self.root,{'action':'amend','id':ident,'revision':p['revision'],'goal':p['request']['goal'],'input_text':p['request']['input_text']})
        self.assertEqual(reset['generation'],1);new,model=self.plan(ident)
        self.assertNotIn('保留中文',model.prompts[0]);self.assertEqual(new['status'],'REVIEW')
        self.assertEqual(len(self.core.db.all('SELECT * FROM model_calls')),2)

    def test_memory_changes_after_admission_block_execution(self):
        Memory(self.core.db).save(fact('偏好','保留中文'),0)
        ident=self.contextual();self.plan(ident);tid=self.approve(ident)
        Memory(self.core.db).save(fact('偏好','改成英文'),1)
        result=self.core.run_task(tid)
        self.assertEqual(result['status'],'WAITING');self.assertEqual(result['error'],'goal_context_changed')
        self.assertEqual(self.core.tasks.actions(tid),[])

    def test_chat_memory_correction_blocks_late_goal_creation(self):
        Memory(self.core.db).save(fact('偏好','保留中文'),0)
        view={**Memory(self.core.db).view('personal','openai'),'scope':'personal','provider':'openai','enabled':True}
        self.chat(view=view);Memory(self.core.db).forget('personal','偏好',1)
        self.code('goal_context_changed',assistant.goal_from_turn,self.root,'chat-turn-1')
        self.assertEqual(self.core.db.all('SELECT * FROM goal_plans'),[])

    def test_goal_experience_is_pending_and_withdrawal_does_not_resurrect(self):
        ident=self.create();self.plan(ident);self.core.run_task(self.approve(ident))
        item=memory.command(self.root,{'action':'propose_goal','goal_id':ident})
        self.assertEqual(Memory(self.core.db).view('personal','openai')['facts'],[])
        value={**fact('文字整理经验','可用大写工具'),'kind':'knowledge'}
        memory.command(self.root,{'action':'save','item':value,'revision':0,'candidate':{'id':item['id'],'revision':1}})
        Memory(self.core.db).forget('personal','文字整理经验',1)
        again=memory.command(self.root,{'action':'propose_goal','goal_id':ident})
        self.assertEqual(again['state'],'WITHDRAWN')

    def test_schema_six_upgrade_preserves_goal(self):
        ident=self.create();self.core.close();db=sqlite3.connect(self.root/'state/core.sqlite3')
        for table in ('assistant_operations','chat_goals','goal_context'):db.execute('DROP TABLE '+table)
        db.execute('ALTER TABLE goal_plans DROP COLUMN generation');db.execute('PRAGMA user_version=6');db.commit();db.close()
        self.core=Core(self.root)
        self.assertEqual(self.detail(ident)['plan']['generation'],0)
        self.assertEqual(self.core.db.one('PRAGMA user_version')['user_version'],7)

    def test_switch_provider_does_not_forward_task_output(self):
        chat=self.chat();ident=assistant.goal_from_turn(self.root,'chat-turn-1')['id'];self.plan(ident)
        self.core.run_task(self.approve(ident))
        allowed=assistant.context(self.root,chat,'openai')[0]
        self.assertEqual(allowed['confirmed_output'],'JARVIS 中文')
        blocked=assistant.context(self.root,chat,'bailian')[0]
        self.assertEqual(blocked['goal'],'');self.assertEqual(blocked['confirmed_output'],'')
        self.assertFalse(blocked['context_current'])

    def test_terminal_task_cannot_be_reported_as_cancelled(self):
        chat=self.chat();ident=assistant.goal_from_turn(self.root,'chat-turn-1')['id'];self.plan(ident)
        tid=self.approve(ident);self.core.run_task(tid);p=self.detail(ident)['plan']
        self.chat('cancel-finished',{**action('cancel',ident),'target_revision':p['revision']},chat)
        self.code('invalid_state',assistant.accept,self.root,{'turn_id':'cancel-finished'})
        self.assertEqual(self.core.tasks.get(tid)['status'],'SUCCEEDED')
        self.assertIsNone(self.core.db.one('SELECT * FROM assistant_operations WHERE turn_id=?',('cancel-finished',)))


if __name__=='__main__':unittest.main()
