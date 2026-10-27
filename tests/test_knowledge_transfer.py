import copy
import http.client
from http.server import ThreadingHTTPServer
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import test_memory_development_ui as base
from apps.workbench.server import Handler
from host import goal_context, knowledge, knowledge_cleanup, memory
from host.core import Core
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.transfer import Transfer, decode_transfer, validate_bundle
from modules.dialogue.store import Dialogues
from modules.task_resource.plans import Plans
from sdk.protocol import CoreError, canonical, decode, digest


class TransferTests(unittest.TestCase):
    setUp=base.MemoryUI.setUp
    tearDown=base.MemoryUI.tearDown
    turn=base.MemoryUI.turn

    def source(self,text='会议在北楼，内部编号 BLUE-42。',title='会议资料',scope='personal'):
        return Knowledge(self.core.db).save({'id':'','scope':scope,'title':title,'text':text,'providers':['openai'],'paused':False},0)

    def update(self,ident,**patches):
        row=Knowledge(self.core.db).detail('personal',ident)
        item={k:row[k] for k in ('id','scope','title','text','providers')};item['paused']=row['status']=='paused';item.update(patches)
        return Knowledge(self.core.db).save(item,row['revision'])

    def bundle(self):return Transfer(self.core.db).export('personal')
    def sign(self,bundle):bundle['checksum']=digest({k:v for k,v in bundle.items() if k!='checksum'});return bundle
    def apply_bundle(self,bundle,scope='personal'):
        service=Transfer(self.core.db);plan=service.preview(scope,bundle)
        return service.restore(scope,bundle,plan['token'])

    def goal(self,view=None):
        with self.core.db.transaction() as tx:
            ident,_=Plans(self.core.db).create({'request_id':'request-'+str(threading.get_ident())+'-'+str(self.core.db.one('SELECT count(*) n FROM goal_plans')['n']),'goal':'会议','input_text':'用户原始输入'},[],[{'id':'openai'}],tx)
            if view is None:view=goal_context.snapshot(self.core,'personal',True,[{'id':'openai'}],'会议')
            tx.execute('INSERT INTO goal_context(goal_id,scope,enabled,view) VALUES(?,?,?,?)',(ident,'personal',1,canonical(view)))
        return ident

    def reply(self,chat,ident,view=None):
        self.turn(chat,ident,'请告诉我会议地点')
        self.chats.context(ident,view or memory.retrieve(self.root,'personal','openai',True,'会议'))
        self.chats.finish(ident,{'status':'SUCCEEDED','text':'北楼 BLUE-42','provider':'openai','assistant_action':{'kind':'chat','reply':'北楼 BLUE-42'}})

    def cleanup(self):
        cursor={'goals':'','turns':''};plan=knowledge_cleanup.preview(self.core.db,self.root,'personal',cursor)
        return knowledge_cleanup.apply(self.core.db,self.root,'personal',cursor,plan['token'])

    def test_portable_roundtrip_reopen_and_permissions_disabled(self):
        saved=self.source();bundle=self.bundle()
        with tempfile.TemporaryDirectory(prefix='jarvis-transfer-') as folder:
            root=Path(folder);core=Core.initialize(root)
            try:
                transfer=Transfer(core.db);p=transfer.preview('personal',bundle)
                self.assertEqual(p['counts']['create'],1)
                result=transfer.restore('personal',bundle,p['token']);self.assertEqual(result['applied'],1)
                core.close();core=Core(root)
                row=Knowledge(core.db).detail('personal',saved['id'])
                self.assertEqual(row['text'],bundle['sources'][0]['text']);self.assertEqual(row['status'],'paused');self.assertEqual(row['providers'],[])
                self.assertEqual(Knowledge(core.db).references('personal','openai'),[])
                again=Transfer(core.db);p=again.preview('personal',bundle)
                self.assertEqual(again.restore('personal',bundle,p['token'])['applied'],0)
            finally:core.close()

    def test_old_backup_cannot_resurrect_tombstone_even_with_higher_revision(self):
        source=self.source();bundle=self.bundle()
        Knowledge(self.core.db).delete('personal',source['id'],1)
        bundle['sources'][0]['revision']=999;self.sign(bundle)
        result=self.apply_bundle(bundle);self.assertEqual(result['counts']['skip_deleted'],1)
        Knowledge(self.core.db).rebuild()
        self.assertEqual(Knowledge(self.core.db).list('personal'),[])
        self.assertEqual(self.bundle()['tombstones'],[{'id':source['id'],'revision':2}])

    def test_revocation_pack_wins_and_never_retains_deleted_body(self):
        source=self.source();bundle=self.bundle();row=bundle['sources'].pop()
        bundle['tombstones']=[{k:row[k] for k in ('id','revision')}];self.sign(bundle)
        result=self.apply_bundle(bundle);self.assertEqual(result['counts']['delete'],1)
        self.assertNotIn('BLUE-42',canonical(self.bundle()))
        self.assertEqual(self.core.db.all('SELECT * FROM knowledge_chunks'),[])

    def test_newer_restore_replaces_atomically_and_invalidates_refs(self):
        saved=self.source();old=memory.retrieve(self.root,'personal','openai',True,'会议');bundle=self.bundle()
        bundle['sources'][0].update(text='会议改为南楼。',revision=2);self.sign(bundle)
        Knowledge(self.core.db).rebuild();result=self.apply_bundle(bundle)
        self.assertEqual(result['counts']['replace'],1);self.assertIsNone(Knowledge(self.core.db).slot())
        row=Knowledge(self.core.db).detail('personal',saved['id']);self.assertEqual(row['providers'],[]);self.assertEqual(row['status'],'paused')
        with self.assertRaises(CoreError):memory.refresh_view(self.root,old)

    def test_local_newer_and_equal_revision_divergence_block_whole_package(self):
        source=self.source();bundle=self.bundle();bundle['sources'][0]['text']='旧包分叉';self.sign(bundle)
        plan=Transfer(self.core.db).preview('personal',bundle);self.assertFalse(plan['can_apply'])
        with self.assertRaises(CoreError):Transfer(self.core.db).restore('personal',bundle,plan['token'])
        self.update(source['id'],text='本地已纠正')
        self.assertFalse(Transfer(self.core.db).preview('personal',bundle)['can_apply'])
        self.assertEqual(Knowledge(self.core.db).detail('personal',source['id'])['text'],'本地已纠正')

    def test_scope_mapping_collision_and_capacity_fail_closed(self):
        self.source();bundle=self.bundle()
        plan=Transfer(self.core.db).preview('project-other',bundle)
        self.assertFalse(plan['can_apply']);self.assertEqual(plan['actions'][0]['reason'],'different_scope')
        for i in range(199):self.source('资料 '+str(i),'资料 '+str(i))
        bundle['sources'][0]['id']='source-'+'b'*32;self.sign(bundle)
        plan=Transfer(self.core.db).preview('personal',bundle);self.assertFalse(plan['capacity_ok'])
        with self.assertRaises(CoreError):Transfer(self.core.db).restore('personal',bundle,plan['token'])
        self.assertEqual(len(Knowledge(self.core.db).list('personal')),200)

    def test_tombstones_can_be_transferred_before_old_backup_on_new_machine(self):
        source=self.source();old=self.bundle();Knowledge(self.core.db).delete('personal',source['id'],1);revocations=self.bundle()
        with tempfile.TemporaryDirectory(prefix='jarvis-revocations-') as folder:
            core=Core.initialize(Path(folder))
            try:
                service=Transfer(core.db)
                for bundle in (revocations,old):
                    plan=service.preview('personal',bundle);service.restore('personal',bundle,plan['token'])
                self.assertEqual(Knowledge(core.db).list('personal'),[])
                self.assertEqual(service.export('personal')['tombstones'],revocations['tombstones'])
            finally:core.close()

    def test_stale_preview_and_modified_package_rejected(self):
        source=self.source();bundle=self.bundle();service=Transfer(self.core.db);p=service.preview('personal',bundle)
        self.update(source['id'],text='更新')
        with self.assertRaises(CoreError):service.restore('personal',bundle,p['token'])
        bundle['sources'][0]['text']='篡改';self.sign(bundle)
        with self.assertRaises(CoreError):service.restore('personal',bundle,p['token'])

    def test_restore_failure_rolls_back_tombstones_sources_index_and_epoch(self):
        self.source();bundle=self.bundle();bundle['sources'][0].update(revision=2,text='第二版');self.sign(bundle)
        library=Knowledge(self.core.db);library.rebuild();epoch=library.epoch();slot=library.slot();before=self.bundle()
        self.core.db.connection.execute("CREATE TRIGGER reject_restore BEFORE INSERT ON knowledge_chunks BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.apply_bundle(bundle)
        self.assertEqual(self.bundle(),before);self.assertEqual(library.epoch(),epoch);self.assertEqual(library.slot(),slot)
        self.assertTrue(library.search('personal','openai','会议')[0])

    def test_strict_format_checksum_duplicate_keys_and_unicode(self):
        self.source();bundle=self.bundle()
        for change in ({'format':'v99'},{'checksum':'bad'},{'extra':'x'}):
            with self.assertRaises(CoreError):validate_bundle(bundle|change)
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":"\\ud800"}',b'\xff'):
            with self.assertRaises(CoreError):decode_transfer(raw)
        duplicate=copy.deepcopy(bundle);duplicate['sources']*=2;self.sign(duplicate)
        with self.assertRaises(CoreError):validate_bundle(duplicate)
        self.assertEqual(decode_transfer(canonical(bundle).encode()),bundle)

    def test_reimport_does_not_revoke_existing_unchanged_policy(self):
        source=self.source();bundle=self.bundle();self.assertEqual(self.apply_bundle(bundle)['applied'],0)
        row=Knowledge(self.core.db).detail('personal',source['id']);self.assertEqual(row['providers'],['openai']);self.assertEqual(row['status'],'active')

    def test_schema_one_migrates_without_changing_main_schema_or_sources(self):
        self.source();self.core.db.connection.execute("UPDATE meta SET value='1' WHERE key='knowledge_schema'")
        self.core.db.connection.execute('DROP TABLE knowledge_cleanups')
        db,_=memory.open_memory(self.root)
        try:
            self.assertEqual(db.one("SELECT value FROM meta WHERE key='knowledge_schema'")['value'],'4')
            self.assertEqual(db.connection.execute('PRAGMA user_version').fetchone()[0],7)
            self.assertEqual(len(Knowledge(db).list('personal')),1)
        finally:db.close()

    def test_cleanup_redacts_transitive_replies_and_background_preserves_originals(self):
        source=self.source();chat=self.chats.create();self.reply(chat,'first');self.reply(chat,'second');goal=self.goal()
        self.update(source['id'],text='会议迁移到南楼')
        result=self.cleanup();self.assertEqual(result['receipt']['state'],'completed')
        self.assertEqual(result['receipt']['turns'],2);self.assertEqual(result['receipt']['goals'],1)
        for ident in ('first','second'):
            row=self.chats.turn(ident);self.assertNotIn('BLUE-42',row['reply']);self.assertIsNone(row['assistant_action'])
            self.assertIn('请告诉我',row['request']);self.assertTrue(decode(row['memory_context'])['dependencies'])
        view=goal_context.get(self.core,goal)['view'];self.assertEqual(view['facts'],[]);self.assertTrue(view['dependencies'])
        with self.assertRaises(CoreError):goal_context.check(self.core,goal)
        self.turn(chat,'after','会议在哪里');messages=canonical(self.chats.context('after'))
        self.assertNotIn('BLUE-42',messages);self.assertNotIn('正文已按要求清理',messages)
        self.assertEqual(self.cleanup()['receipt']['turns'],0)

    def test_cleanup_unrelated_source_preserved_and_busy_deferred(self):
        source=self.source();chat=self.chats.create();self.reply(chat,'good')
        other=self.source('不相关的鱼缸内容','鱼缸');self.update(other['id'],text='鱼缸修订')
        self.assertEqual(self.cleanup()['receipt']['turns'],0)
        self.turn(chat,'busy','会议');self.chats.context('busy',memory.retrieve(self.root,'personal','openai',True,'会议'))
        self.update(source['id'],paused=True)
        p=knowledge_cleanup.preview(self.core.db,self.root,'personal',{'goals':'','turns':''})
        self.assertEqual(p['counts']['busy_turns'],1)
        self.cleanup();self.assertEqual(self.chats.turn('busy')['status'],'RUNNING')

    def test_cleanup_partial_failure_visible_and_retry_after_reopen(self):
        source=self.source();chat=self.chats.create();self.reply(chat,'one');goal=self.goal();self.update(source['id'],text='会议改动')
        with patch.object(Dialogues,'clear_projections',side_effect=RuntimeError('injected')):r=self.cleanup()
        self.assertEqual(r['receipt']['state'],'partial');self.assertEqual(r['receipt']['goals'],1);self.assertIn('BLUE-42',self.chats.turn('one')['reply'])
        db,_=memory.open_memory(self.root)
        try:
            self.assertEqual(db.one('SELECT state FROM knowledge_cleanups WHERE id=?',(r['receipt']['id'],))['state'],'partial')
            self.assertTrue(decode(db.one('SELECT view FROM goal_context WHERE goal_id=?',(goal,))['view'])['redacted'])
        finally:db.close()
        r=self.cleanup();self.assertEqual(r['receipt']['state'],'completed');self.assertEqual(r['receipt']['turns'],1)

    def test_interrupt_between_store_commits_leaves_pending_receipt_and_can_resume(self):
        source=self.source();chat=self.chats.create();self.reply(chat,'interrupt');self.goal();self.update(source['id'],paused=True)
        with patch.object(Dialogues,'clear_projections',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.cleanup()
        row=self.core.db.one('SELECT * FROM knowledge_cleanups')
        self.assertEqual(row['state'],'pending');self.assertEqual(row['goals'],1)
        self.assertIn('BLUE-42',self.chats.turn('interrupt')['reply'])
        self.assertEqual(self.cleanup()['receipt']['turns'],1)

    def test_cleanup_stale_preview_and_chat_cas_roll_back(self):
        source=self.source();chat=self.chats.create();self.reply(chat,'one');self.update(source['id'],paused=True)
        cursor={'goals':'','turns':''};p=knowledge_cleanup.preview(self.core.db,self.root,'personal',cursor)
        self.chats.db.execute("UPDATE turns SET reply='changed' WHERE id='one'")
        with self.assertRaises(CoreError):knowledge_cleanup.apply(self.core.db,self.root,'personal',cursor,p['token'])
        rows=self.chats.cleanup_page('personal','',10);self.chats.db.execute("UPDATE turns SET reply='changed again' WHERE id='one'")
        with self.assertRaises(CoreError):self.chats.clear_projections(rows)
        self.assertEqual(self.chats.turn('one')['reply'],'changed again')

    def test_cleanup_pagination_and_unknown_provenance_are_explicit(self):
        source=self.source();chat=self.chats.create()
        for i in range(3):self.reply(chat,'turn'+str(i))
        self.update(source['id'],paused=True)
        cursor={'goals':'','turns':''}
        with patch('host.knowledge_cleanup.PAGE',2):
            first=knowledge_cleanup.preview(self.core.db,self.root,'personal',cursor)
            self.assertTrue(first['has_more']);self.assertEqual(first['counts']['turns'],2)
            second=knowledge_cleanup.preview(self.core.db,self.root,'personal',first['next_cursor'])
            self.assertFalse(second['has_more']);self.assertEqual(second['counts']['turns'],1)
        self.chats.db.execute("UPDATE turns SET memory_context=NULL WHERE id='turn0'")
        self.assertEqual(knowledge_cleanup.preview(self.core.db,self.root,'personal',cursor)['counts']['unknown_provenance'],1)

    def test_http_large_bundle_security_strict_decoder_and_default_size_unchanged(self):
        for i in range(5):self.source('文'*26000,'大资料'+str(i))
        bundle=self.bundle();server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='test'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            def send(raw,path='/api/knowledge-transfer',auth=True):
                c=http.client.HTTPConnection('127.0.0.1',server.server_port);headers={'Content-Type':'application/json'}
                if auth:headers.update(Origin='http://127.0.0.1:'+str(server.server_port),**{'X-Jarvis-Token':'test'})
                c.request('POST',path,raw,headers);r=c.getresponse();result=decode_transfer(r.read());c.close();return r.status,result
            request=canonical({'action':'restore_preview','scope':'personal','bundle':bundle}).encode()
            self.assertGreater(len(request),262144)
            self.assertEqual(send(request,auth=False)[0],403)
            self.assertEqual(send(request,path='/api/knowledge')[0],413)
            status,p=send(request);self.assertEqual(status,200);self.assertTrue(p['can_apply'])
            self.assertEqual(send(b'{"action":"restore_preview","scope":"personal","scope":"x","bundle":{}}')[0],400)
            status,result=send(canonical({'action':'restore','scope':'personal','bundle':bundle,'token':p['token']}).encode())
            self.assertEqual(status,200);self.assertEqual(result['applied'],0)
        finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
