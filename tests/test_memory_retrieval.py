import time
import threading
import unittest
from unittest.mock import patch

from test_memory_development_ui import MemoryUI, fact
from test_local_models import ModelsCase, FakeWorker
from host import memory, goal_context, assistant
from host.dialogue import DialogueHost
from modules.context_knowledge.retrieval import rank
from modules.dialogue.store import Dialogues
from sdk.protocol import canonical, decode, CoreError


class Retrieval(unittest.TestCase):
    setUp=MemoryUI.setUp
    tearDown=MemoryUI.tearDown
    save=MemoryUI.save
    turn=MemoryUI.turn

    def knowledge(self,key,value,**kw):
        return {**fact(key,value),'kind':'knowledge',**kw}

    def test_question_recalls_thirteenth_fact_without_raising_budget(self):
        for i in range(30):self.save(self.knowledge(f'资料-{i:02d}',f'物品编号 {i}'))
        self.save(self.knowledge('最后的会议','周五下午三点讨论量子计算'))
        v=memory.retrieve(self.root,'personal','openai',True,'量子计算会议是什么时候？')
        self.assertEqual(v['facts'][0]['key'],'最后的会议')
        self.assertLessEqual(len(v['facts']),12);self.assertLessEqual(v['retrieval']['bytes'],5000)
        self.assertEqual(v['retrieval']['eligible'],31)

    def test_exact_version_and_unicode_query_and_no_answer(self):
        self.save(self.knowledge('API-v3.8','当前版本需要 header-X'))
        self.save(self.knowledge('café','Le café est fermé le lundi.'))
        self.assertEqual(memory.retrieve(self.root,'personal','openai',True,'ＡＰＩ-v3.8')['facts'][0]['key'],'API-v3.8')
        self.assertEqual(memory.retrieve(self.root,'personal','openai',True,'cafe\u0301 fermé')['facts'][0]['key'],'café')
        self.assertEqual(memory.retrieve(self.root,'personal','openai',True,'火星种植土豆')['facts'],[])

    def test_filter_before_encoder_and_keep_full_long_fact(self):
        self.save(self.knowledge('private','personal secret'))
        self.memory.save(self.knowledge('A','项目甲独有资料',scope='project-A',purpose='project'),0)
        self.memory.save(self.knowledge('B','项目乙独有资料',scope='project-B',purpose='project'),0)
        self.memory.save(self.knowledge('other','different destination',scope='project-A',purpose='project',providers=['bailian']),0)
        seen=[]
        def encoder(rows,query):
            seen.extend(rows);return {'status':'ready','scores':{r['id']:.9 for r in rows},'count':len(rows),'model':'test'}
        self.memory.view('project-A','openai',True,'project',encoder)
        self.assertEqual([r['key'] for r in seen],['A'])
        seen.clear();self.memory.view('personal','openai',False,'private',encoder);self.assertEqual(seen,[])
        self.save(self.knowledge('long','甲'*1500+'末尾验收编号ZX900'))
        self.assertIn('末尾验收编号ZX900',self.memory.view('personal','openai',True,'ZX900')['facts'][0]['value'])

    def test_ranker_cannot_inject_unowned_id(self):
        self.save(self.knowledge('a','plain text'))
        v=self.memory.view('personal','openai',True,'unrelated',lambda *_:{'status':'ready','scores':{'forged-secret':1.0}})
        self.assertEqual(v['facts'],[])

    def test_inflections_and_question_words_do_not_displace_subject(self):
        from modules.context_knowledge.knowledge import Knowledge
        lib=Knowledge(self.core.db)
        for i in range(80):
            lib.save(dict(id='',scope='personal',title=f'Generic {i}',text='How many are there in total? There are 40 nodes in the decision tree.',providers=['openai'],paused=False),0)
        item=lib.save(dict(id='',scope='personal',title='Journal',text='My aquarium contains 7 fish. The second aquarium contains 10 fish.',providers=['openai'],paused=False),0)
        for indexed in (False,True):
            if indexed:lib.rebuild()
            view=self.memory.view('personal','openai',True,'How many fish are there in total in both of my aquariums?')
            self.assertEqual(view['facts'][0]['id'],item['id'])
            self.assertIn('10 fish',view['facts'][0]['value'])
        self.save(self.knowledge('lens','My new lens is a zoom lens.'))
        self.assertEqual(self.memory.view('personal','openai',True,'Which lenses?')['facts'][0]['key'],'lens')

    def test_correction_during_semantic_inference_never_returns_old_value(self):
        self.save(self.knowledge('接口','接口版本v1'))
        class Ranker:
            def rank_memory(_,rows,query):
                self.save(self.knowledge('接口','接口版本v2'),1)
                return {'status':'ready','scores':{r['id']:.9 for r in rows}}
        with patch('host.local_models.MANAGERS',{str(self.root):Ranker()}):
            v=memory.retrieve(self.root,'personal','openai',True,'接口版本')
        self.assertEqual(v['facts'][0]['value'],'接口版本v2')
        self.assertEqual(v['retrieval']['semantic'],'changed_during_retrieval')

    def make_context(self,chat,ident,query,reply):
        self.turn(chat,ident,query)
        v=memory.dialogue_view(self.root,self.chats.read(chat),{'id':'openai'},True,query)
        messages=self.chats.context(ident,v)
        self.chats.finish(ident,{'status':'SUCCEEDED','text':reply,'provider':'openai'})
        return messages,v

    def test_unrelated_change_preserves_history_transitive_forget_removes_it(self):
        self.save(self.knowledge('天文','望远镜需要校准星镜'))
        self.save(self.knowledge('菜谱','番茄浓汤'))
        chat=self.chats.create();self.make_context(chat,'one','望远镜','星镜答案')
        self.save(self.knowledge('菜谱','蘑菇浓汤'),1)
        messages,v=self.make_context(chat,'two','继续说','延续旧星镜答案')
        self.assertIn('星镜答案',canonical(messages));self.assertEqual(v['facts'],[])
        self.assertEqual(len(v['dependencies']),1)
        self.memory.forget('personal','天文',1)
        messages,_=self.make_context(chat,'three','继续说','无答案')
        self.assertNotIn('星镜',canonical(messages))

    def test_relevant_expiry_checked_even_when_global_epoch_unchanged(self):
        self.save({**fact('提醒','稍后喝水'),'expires':time.time()+10})
        v=memory.retrieve(self.root,'personal','openai',True,'喝水')
        with patch('modules.context_knowledge.memory.time.time',return_value=time.time()+20):
            with self.assertRaises(CoreError):memory.refresh_view(self.root,v)

    def test_unrelated_edit_does_not_cancel_inflight_answer(self):
        self.save(self.knowledge('目标资料','望远镜需要校准'))
        self.save(self.knowledge('其他资料','果树种植'))
        host=DialogueHost(self.root);started=threading.Event();proceed=threading.Event()
        class Client:
            def __init__(self,*_):pass
            def available(self):return True
            def complete(self,messages,checkpoint):
                started.set();proceed.wait(3);checkpoint();return {'status':'SUCCEEDED','text':'望远镜答案'}
        try:
            with patch('host.dialogue.NativeModel',Client):
                host.submit(dict(chat_id=self.chats.create(),request_id='inflight',text='望远镜',provider='openai',model='test-model',reasoning='default'))
                self.assertTrue(started.wait(2));self.save(self.knowledge('其他资料','果树施肥'),1);proceed.set()
                host.pool.shutdown(wait=True)
                self.assertEqual(self.chats.turn('inflight')['status'],'SUCCEEDED')
        finally:proceed.set();host.close()

    def test_goal_retrieval_and_revalidation_do_not_use_top_twelve_membership(self):
        for i in range(20):self.save(self.knowledge(f'编号{i:02d}',f'静态资料{i}'))
        self.save(self.knowledge('装配规范','ZX900螺栓要求扭矩10牛米'))
        view=goal_context.snapshot(self.core,'personal',True,[{'id':'openai'}],'ZX900螺栓扭矩')
        self.assertEqual(view['facts'][0]['key'],'装配规范')
        self.assertTrue(self.memory.references_valid('personal','openai',True,view['dependencies']))

    def test_goal_output_dependencies_join_receipt(self):
        self.save(self.knowledge('资料','望远镜校准'))
        ref=self.memory.references('personal','openai')[0]
        chat=self.chats.create();self.turn(chat,'goal-output','进度')
        v=memory.retrieve(self.root,'personal','openai',True,'进度')
        v['dependencies']=[ref];self.chats.context('goal-output',v)
        self.assertEqual(decode(self.chats.turn('goal-output')['memory_context'])['dependencies'],[ref])
        self.memory.forget('personal','资料',1)
        with self.assertRaises(CoreError):memory.refresh_view(self.root,v)


class EncoderLane(unittest.TestCase):
    setUp=ModelsCase.setUp
    tearDown=ModelsCase.tearDown
    fixture=ModelsCase.fixture
    run_command=ModelsCase.run_command

    def test_selected_encoder_only_and_no_memory_text_on_disk(self):
        self.fixture('a');self.run_command('start',id='a')
        rows=[{'id':'fact-synthetic','key':'canary','value':'private-memory-canary'}]
        self.assertEqual(self.m.rank_memory(rows,'canary')['status'],'not_selected')
        self.run_command('activate',id='a')
        result=self.m.rank_memory(rows,'canary')
        self.assertEqual(result['status'],'ready');self.assertIn('fact-synthetic',result['scores'])
        self.assertNotIn(b'private-memory-canary',self.m.path.read_bytes())
        self.run_command('standby',id='a');self.assertEqual(self.m.rank_memory(rows,'canary')['status'],'not_loaded')

    def test_slow_encoder_has_bounded_wait_and_busy_fallback(self):
        self.fixture('a');self.run_command('activate',id='a')
        original=self.m.worker.request
        def slow(*args):time.sleep(.3);return original(*args)
        self.m.worker.request=slow;rows=[{'id':'a','key':'短','value':'资料'}]
        start=time.monotonic();r=self.m.rank_memory(rows,'问题',wait_seconds=.02)
        self.assertEqual(r['status'],'timeout');self.assertLess(time.monotonic()-start,.2)
        self.assertEqual(self.m.rank_memory(rows,'另一个问题')['status'],'busy')
        self.m.recall_future.result(timeout=3)
        self.assertIsNone(self.m.future.result().get('error'))

    def test_worker_failure_falls_back_and_can_restart(self):
        self.fixture('a');self.run_command('activate',id='a')
        FakeWorker.fail=True
        try:self.assertEqual(self.m.rank_memory([{'id':'a','key':'x','value':'y'}],'z')['status'],'worker_failed')
        finally:FakeWorker.fail=False
        self.assertIsNone(self.m.worker)
        self.assertEqual(self.run_command('start',id='a')['status'],'succeeded')


    def test_deadline_timeout_keeps_model_loaded_and_caches_fact_vectors(self):
        self.fixture('a');self.run_command('activate',id='a')
        calls=[];original=self.m.worker.request
        def counting(texts,role,check):calls.append((role,len(texts)));return original(texts,role,check)
        self.m.worker.request=counting
        rows=[{'id':'f%d'%i,'key':'k%d'%i,'value':'v'} for i in range(6)]
        self.assertEqual(self.m.rank_memory(rows,'q1')['encoded'],6)
        calls.clear();second=self.m.rank_memory(rows,'q2')
        self.assertEqual((second['status'],second['encoded']),('ready',0))
        self.assertEqual(calls,[('query',1)])  # cached passages are not re-encoded
        def late(texts,role,check):raise CoreError('local_timeout','Memory encoding deadline')
        self.m.worker.request=late
        self.assertEqual(self.m.rank_memory(rows,'q3')['status'],'timeout')
        self.assertIsNotNone(self.m.worker);self.assertEqual(self.m.loaded,'a')

    def test_worker_discards_late_reply_to_timed_out_request(self):
        from host.local_models import Worker
        import queue
        worker=Worker.__new__(Worker);worker.queue=queue.Queue()
        worker.queue.put({'id':1,'vectors':[[0.0]]});worker.queue.put({'id':2,'vectors':[[1.0]]})
        self.assertEqual(worker.wait(lambda:None,timeout=1,expect=2)['vectors'],[[1.0]])
        worker.queue.put({'id':3,'error':'bad input'})
        with self.assertRaises(CoreError):worker.wait(lambda:None,timeout=1,expect=3)


if __name__=='__main__':unittest.main()
