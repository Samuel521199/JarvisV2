import http.client
from http.server import ThreadingHTTPServer
import sqlite3
import threading
import time
import unittest

from test_memory_development_ui import MemoryUI, fact
from apps.workbench.server import Handler
from host import knowledge, memory, goal_context
from host.dialogue import DialogueHost
from modules.context_knowledge.knowledge import Knowledge
from sdk.protocol import CoreError, canonical, decode


class Library(unittest.TestCase):
    setUp=MemoryUI.setUp
    tearDown=MemoryUI.tearDown
    turn=MemoryUI.turn

    def source(self,text='会议地点是北楼。',title='会议说明',scope='personal',providers=None):
        return knowledge.command(self.root,{'action':'save','revision':0,'item':{'id':'','scope':scope,'title':title,'text':text,'providers':['openai'] if providers is None else providers,'paused':False}})

    def update(self,ident,**changes):
        row=knowledge.command(self.root,{'action':'detail','scope':'personal','id':ident})
        item={k:row[k] for k in ('id','scope','title','text','providers')};item['paused']=row['status']=='paused';item.update(changes)
        return knowledge.command(self.root,{'action':'save','item':item,'revision':row['revision']})

    def recall(self,query='会议地点',provider='openai',scope='personal'):
        return memory.retrieve(self.root,scope,provider,True,query)

    def test_fragment_source_offsets_restart_and_multilingual_tokens(self):
        text='# 手册 🧠\n'+('这一段是普通描述。\n'*100)+'\nZX900 torque: 37 Nm.\n会议地点是北楼。'
        saved=self.source(text,'接口手册');library=Knowledge(self.core.db);library.rebuild()
        db,mem=memory.open_memory(self.root)
        try:
            view=mem.view('personal','openai',True,'ZX900 torque')
            self.assertEqual(view['retrieval']['sources']['mode'],'fts5')
            match=next(r for r in view['facts'] if '37 Nm' in r['value']);e=match['evidence']
            self.assertEqual(e['source_id'],saved['id']);self.assertEqual(text[e['start']:e['end']],match['value'])
            self.assertEqual(e['line_start'],text[:e['start']].count('\n')+1)
            self.assertEqual(e['trust'],'reference_unverified')
        finally:db.close()

    def test_import_deduplicates_without_widening_policy(self):
        first=self.source(providers=[]);second=self.source(providers=['openai'])
        self.assertEqual(first['id'],second['id']);self.assertTrue(second['existing'])
        self.assertEqual(self.recall()['facts'],[])

    def test_unauthorized_sources_never_reach_encoder_or_context(self):
        self.source('跨域秘密黑曜石',providers=['bailian'])
        self.source('公开白桦资料',title='白桦')
        seen=[]
        def encoder(rows,query):seen.extend(rows);return {'status':'ready','scores':{}}
        view=self.memory.view('personal','openai',True,'秘密',encoder)
        self.assertNotIn('黑曜石',canonical(seen));self.assertNotIn('黑曜石',canonical(view))
        self.assertEqual(self.memory.view('project-other','bailian',True,'秘密')['facts'],[])
        self.assertEqual(self.memory.view('personal','bailian',False,'秘密')['facts'],[])
        self.assertEqual(self.memory.view('personal','bailian',True)['facts'],[])

    def test_correction_invalidates_history_but_unrelated_edit_does_not(self):
        saved=self.source();chat=self.chats.create();self.turn(chat,'old','会议地点在哪里')
        view=self.recall();self.chats.context('old',view);self.chats.finish('old',{'status':'SUCCEEDED','text':'在北楼','provider':'openai'})
        self.source('其他不相关','另一个资料')
        memory.refresh_view(self.root,view)
        self.update(saved['id'],text='会议地点改为南楼。')
        with self.assertRaises(CoreError):memory.refresh_view(self.root,view)
        self.turn(chat,'new','会议地点在哪里')
        messages=canonical(self.chats.context('new',self.recall()))
        self.assertNotIn('北楼',messages);self.assertIn('南楼',messages)

    def test_pause_and_provider_changes_invalidate_existing_refs(self):
        saved=self.source();view=self.recall();self.update(saved['id'],paused=True)
        with self.assertRaises(CoreError):memory.refresh_view(self.root,view)
        self.assertEqual(self.recall()['facts'],[])
        self.update(saved['id'],paused=False,providers=['bailian'])
        self.assertEqual(self.recall()['facts'],[]);self.assertTrue(self.recall(provider='bailian')['facts'])

    def test_delete_clears_managed_text_chunks_indices_and_cannot_reuse_id(self):
        saved=self.source('稀有隐私金丝雀','保密');library=Knowledge(self.core.db);library.rebuild()
        view=self.recall('金丝雀')
        value=knowledge.command(self.root,{'action':'delete','scope':'personal','id':saved['id'],'revision':1})
        self.assertFalse(value['historical_outputs_cleared']);self.assertGreater(value['cleared_chunks'],0)
        self.assertNotIn('金丝雀',canonical(self.core.db.all('SELECT * FROM knowledge_sources')))
        self.assertEqual(self.core.db.all('SELECT * FROM knowledge_chunks'),[])
        self.assertEqual(self.core.db.all('SELECT * FROM '+library.slot()),[])
        with self.assertRaises(CoreError):memory.refresh_view(self.root,view)
        with self.assertRaises(CoreError):self.update(saved['id'],text='复活')
        library.rebuild();self.assertEqual(self.recall('金丝雀')['facts'],[])

    def test_stale_write_and_invalid_input_do_not_change_source(self):
        saved=self.source();row=knowledge.command(self.root,{'action':'detail','scope':'personal','id':saved['id']})
        for change in ({'text':'x'*80001},{'text':'中'*30000},{'text':'abc\x00def'},{'providers':['unregistered']},{'scope':'project-missing'},{'id':'../file'}):
            with self.assertRaises(CoreError):self.update(saved['id'],**change)
        with self.assertRaises(CoreError):knowledge.command(self.root,{'action':'delete','scope':'personal','id':saved['id'],'revision':0})
        self.assertEqual(Knowledge(self.core.db).detail('personal',saved['id']),row)

    def test_missing_index_falls_back_and_rebuild_recovers(self):
        self.source();library=Knowledge(self.core.db);library.rebuild();slot=library.slot()
        self.core.db.connection.execute('DROP TABLE '+slot)
        view=self.recall();self.assertEqual(view['retrieval']['sources']['mode'],'scan_fallback');self.assertTrue(view['facts'])
        library.rebuild();self.assertEqual(self.recall()['retrieval']['sources']['mode'],'fts5')

    def test_cancelled_shadow_rebuild_preserves_live_index(self):
        self.source();library=Knowledge(self.core.db);library.rebuild();slot=library.slot()
        def cancel():raise CoreError('knowledge_cancelled','cancel')
        with self.assertRaises(CoreError):library.rebuild(cancel)
        self.assertEqual(library.slot(),slot);self.assertTrue(self.recall()['facts'])

    def test_concurrent_update_replays_current_source_without_losing_new_value(self):
        saved=self.source();library=Knowledge(self.core.db);library.rebuild();slot=library.slot()
        def update(_):self.update(saved['id'],text='会议地点是新楼。')
        result=library.rebuild(progress=update)
        self.assertNotEqual(library.slot(),slot);self.assertEqual(result['replayed_sources'],1)
        view=canonical(self.recall());self.assertIn('新楼',view);self.assertNotIn('北楼',view)

    def test_rebuild_replays_insert_delete_and_does_not_keep_orphan_text(self):
        saved=self.source('待删除的金丝雀原文。');library=Knowledge(self.core.db);library.rebuild();changed=[]
        def update(_):
            if changed:return
            changed.append(True);library.delete('personal',saved['id'],1);self.source('新导入的会议资料在南楼。','新增资料')
        result=library.rebuild(progress=update)
        self.assertEqual(result['replayed_sources'],2)
        self.assertNotIn('金丝',canonical(self.core.db.all('SELECT terms FROM '+library.slot())))
        self.assertIn('南楼',canonical(self.recall('会议资料')))

    def test_endlessly_changing_reconciliation_keeps_current_live_index(self):
        from unittest.mock import patch
        self.source();library=Knowledge(self.core.db);library.rebuild();active=library.slot();original=library.epoch;calls=[]
        def moving():
            calls.append(1);return original()+len(calls)
        with patch.object(library,'epoch',side_effect=moving):
            with self.assertRaises(CoreError):library.rebuild()
        self.assertEqual(library.slot(),active);self.assertIn('北楼',canonical(self.recall()))

    def test_failed_import_rolls_back_sources_fragments_and_index(self):
        saved=self.source();library=Knowledge(self.core.db);library.rebuild()
        self.core.db.connection.execute("CREATE TRIGGER test_fail BEFORE INSERT ON knowledge_chunks BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.Error):self.update(saved['id'],text='破坏性半写入')
        self.assertEqual(library.detail('personal',saved['id'])['revision'],1)
        self.assertIn('北楼',canonical(self.recall()))

    def test_goal_snapshot_uses_reference_metadata_and_shared_destination_intersection(self):
        self.source('接口版本固定 v9，超时时间 37 秒。','接口规范')
        result=goal_context.snapshot(self.core,'personal',True,[{'id':'openai'}],'接口版本')
        self.assertEqual(result['facts'][0]['kind'],'source');self.assertTrue(result['dependencies'])
        self.assertEqual(goal_context.snapshot(self.core,'personal',True,[{'id':'openai'},{'id':'bailian'}],'接口版本')['facts'],[])

    def test_inflight_source_deletion_rejects_stale_answer(self):
        from unittest.mock import patch
        saved=self.source();started=threading.Event();proceed=threading.Event();host=DialogueHost(self.root)
        class Client:
            def __init__(self,*_):pass
            def available(self):return True
            def complete(self,messages,checkpoint):
                started.set();proceed.wait(3);checkpoint();return {'status':'SUCCEEDED','text':'北楼'}
        try:
            with patch('host.dialogue.NativeModel',Client):
                host.submit(dict(chat_id=self.chats.create(),request_id='inflight',text='会议地点',provider='openai',model='test-model',reasoning='default'))
                self.assertTrue(started.wait(2));knowledge.command(self.root,{'action':'delete','scope':'personal','id':saved['id'],'revision':1});proceed.set()
                for _ in range(100):
                    if self.chats.turn('inflight')['status'] not in {'READY','RUNNING'}:break
                    time.sleep(.02)
                self.assertEqual(self.chats.turn('inflight')['error'],'memory_changed');self.assertIsNone(self.chats.turn('inflight')['reply'])
        finally:proceed.set();host.close()

    def test_http_origin_nonce_and_async_index_lifecycle(self):
        self.source();server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='test'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            def post(body,auth=True):
                c=http.client.HTTPConnection('127.0.0.1',server.server_port)
                headers={'Content-Type':'application/json'}
                if auth:headers.update(Origin='http://127.0.0.1:'+str(server.server_port),**{'X-Jarvis-Token':'test'})
                c.request('POST','/api/knowledge',canonical(body).encode(),headers);r=c.getresponse();data=decode(r.read());c.close();return r.status,data
            self.assertEqual(post({'action':'list','scope':'personal'},False)[0],403)
            self.assertEqual(post({'action':'list','scope':'personal'})[0],200)
            self.assertEqual(post({'action':'rebuild'})[0],200)
            for _ in range(100):
                state=post({'action':'index_status'})[1]
                if state['state'] not in {'queued','running'}:break
                time.sleep(.02)
            self.assertEqual(state['state'],'succeeded');self.assertTrue(state['available'])
            self.assertEqual(state['result']['index_version'],'knowledge-fts-incremental-1.0.0')
            self.assertEqual(state['result']['replayed_sources'],0)
        finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
