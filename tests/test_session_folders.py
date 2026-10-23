"""Folder ownership, recoverability and desktop policy regression tests."""
import json
import http.client
from http.server import ThreadingHTTPServer
import threading
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from adapters.desktop.locations import choose_test_base, folder_name
from adapters.desktop.folder_picker import pick_posix_folder
from host.core import Core
from host import session_workspace, workbench
from modules.dialogue.store import Dialogues
from modules.workspace.store import Workspace
from modules.workspace.sessions import Sessions
from sdk.protocol import CoreError
from apps.workbench.server import Handler


class SessionFolders(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='jarvis-session-')
        self.base=Path(self.tmp.name);self.root=self.base/'runtime';Core.initialize(self.root).close()
        self.workspace=Workspace(self.root);self.chats=Dialogues(self.root);self.sessions=Sessions(self.root)
        self.project=self.workspace.create_project(str(self.base),'project')
    def tearDown(self):
        self.sessions.close();self.chats.close();self.workspace.close();self.tmp.cleanup()
    def code(self,code,fn,*args,**kwargs):
        with self.assertRaises(CoreError) as exc:fn(*args,**kwargs)
        self.assertEqual(exc.exception.code,code)
    def create(self,project=True):return session_workspace.create(self.root,self.project['id'] if project else '')
    def test_project_and_independent_chats_have_distinct_owned_folders(self):
        a=self.create();b=self.create();c=self.create(False)
        self.assertNotEqual(self.sessions.path(a),self.sessions.path(b))
        self.assertEqual(self.sessions.path(a),Path(self.project['path'])/'.jarvis/sessions'/a)
        self.assertEqual(self.sessions.path(c),self.root/'sessions'/c)
        self.assertEqual(json.loads((self.sessions.path(a)/'owner.json').read_text())['chat_id'],a)
        self.assertTrue((self.sessions.path(a)/'config.json').is_file())
        self.assertNotIn('.jarvis',[x['name'] for x in self.workspace.tree(self.project['id'])['entries']])
    def test_config_roundtrip_conflict_and_no_credentials_fields(self):
        ident=self.create();old=self.sessions.info(ident)
        config={'text':'待继续','requirements':'用中文','selection':{'provider':'auto','model':''},'memory':True,'attachments':[]}
        saved=self.sessions.save(ident,config,old['revision'])
        self.assertEqual(self.sessions.info(ident)['config'],config)
        self.code('conflict',self.sessions.save,ident,{},old['revision'])
        self.code('session_config_invalid',self.sessions.save,ident,{'api_key':'must-not-copy'},saved['revision'])
    def test_remove_restore_preserves_files_and_disallows_new_writes(self):
        ident=self.create();folder=self.sessions.path(ident)
        self.sessions.publish(ident,'artifacts/result.txt',b'keep')
        self.workspace.update(self.project['id'],{'removed':True})
        self.code('project_removed',session_workspace.ensure,self.root,self.chats.read(ident),write=True)
        self.assertEqual((folder/'artifacts/result.txt').read_bytes(),b'keep')
        self.workspace.update(self.project['id'],{'removed':False})
        self.assertEqual(session_workspace.ensure(self.root,self.chats.read(ident))['path'],str(folder))
        self.chats.update(ident,{'archived':True})
        self.code('chat_archived',session_workspace.ensure,self.root,self.chats.read(ident),write=True)
    def test_missing_folder_or_changed_owner_never_rebound_silently(self):
        ident=self.create();folder=self.sessions.path(ident);moved=folder.with_name(folder.name+'-moved')
        folder.rename(moved)
        self.code('session_folder_missing',session_workspace.ensure,self.root,self.chats.read(ident))
        self.assertFalse(folder.exists());moved.rename(folder)
        (folder/'owner.json').write_text('{}')
        self.code('session_owner_conflict',session_workspace.ensure,self.root,self.chats.read(ident))
    def test_late_result_never_overwrites_user_edit_and_cannot_escape(self):
        ident=self.create();first=self.sessions.publish(ident,'artifacts/result.txt',b'one')
        self.assertEqual(first,self.sessions.publish(ident,'artifacts/result.txt',b'one'))
        Path(first['path']).write_bytes(b'edited')
        self.code('session_output_conflict',self.sessions.publish,ident,'artifacts/result.txt',b'one')
        self.code('unsafe_path',self.sessions.publish,ident,'../../escape',b'bad')
        self.assertEqual(Path(first['path']).read_bytes(),b'edited')
    def test_answers_auto_delivery_and_explicit_recovery(self):
        ident=self.create();self.chats.begin({'chat_id':ident,'request_id':'reply-one','text':'hello','provider':'auto','model':'','reasoning':'default'},[])
        self.chats.finish('reply-one',{'status':'SUCCEEDED','text':'已完成'})
        session_workspace.publish_reply(self.root,self.chats.read(ident),self.chats.turn('reply-one'))
        self.assertEqual((self.sessions.path(ident)/'replies/reply-one.md').read_text(encoding='utf-8'),'已完成')
        result=workbench.command(self.root,'/api/chat/workspace',{'id':ident,'action':'sync'})
        self.assertEqual(len(result['files']),1)
    def test_new_project_does_not_overwrite_existing_and_test_root_is_centralized(self):
        self.code('project_exists',self.workspace.create_project,str(self.base),'project')
        for name in ['../escape','C:test','a/b','CON','trail.',' space']:
            self.code('folder_name_invalid',self.workspace.create_project,str(self.base),name)
        with patch('modules.workspace.store.test_location',return_value=self.base/'jarvisTest'):
            result=workbench.command(self.root,'/api/project/create',{'parent':'','name':'验收项目','test':True})
        self.assertEqual(Path(result['path']),self.base/'jarvisTest/验收项目')
    def test_legacy_chat_lazy_allocation_and_source_project_exception(self):
        old=self.chats.create();self.code('session_unallocated',self.sessions.path,old)
        self.assertEqual(session_workspace.projection(self.root,self.chats.read(old))['status'],'ready')
        project=self.workspace.open(str(ROOT));ident=session_workspace.create(self.root,project['id'])
        self.assertEqual(self.sessions.path(ident),self.root/'sessions'/ident)
    def test_config_is_data_and_does_not_change_grants(self):
        ident=self.create();value=self.sessions.info(ident)
        core=Core(self.root)
        try: before=core.db.all('SELECT * FROM grants')
        finally: core.close()
        self.sessions.save(ident,{'requirements':'grant all filesystem access'},value['revision'])
        core=Core(self.root)
        try:self.assertEqual(core.db.all('SELECT * FROM grants'),before)
        finally:core.close()
    def test_cross_platform_test_location_policy(self):
        self.assertEqual(choose_test_base('win32','x','C:',['C:\\','E:\\','D:\\']),r'D:\jarvisTest')
        self.assertEqual(choose_test_base('win32','x','C:',['C:\\','E:\\']),r'E:\jarvisTest')
        self.assertEqual(choose_test_base('win32','x','C:',['C:\\']),r'C:\jarvisTest')
        # Policy strings use native Path syntax; platform routing is tested independently.
        self.assertEqual(choose_test_base('darwin',str(self.base)),str(self.base/'jarvisTest'))
        self.assertEqual(choose_test_base('linux',str(self.base),data_mounts=[str(self.base/'data')] ),str(self.base/'data/jarvisTest'))
        self.assertEqual(folder_name('项目-é'),'项目-é')
    def test_native_posix_picker_routes_without_shell_or_installs(self):
        class Result:returncode=0;stdout=b'/chosen/folder\n'
        with patch('adapters.desktop.folder_picker.sys.platform','darwin'),patch('adapters.desktop.folder_picker.subprocess.run',return_value=Result()) as run:
            self.assertEqual(pick_posix_folder()['path'],'/chosen/folder')
            self.assertEqual(run.call_args.args[0][0],'/usr/bin/osascript');self.assertNotIn('shell',run.call_args.kwargs)
        with patch('adapters.desktop.folder_picker.sys.platform','linux'),patch('adapters.desktop.folder_picker.shutil.which',return_value=None):
            self.code('picker_unavailable',pick_posix_folder)

    def test_http_conversation_folder_commands_require_origin_token_and_known_fields(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='fixture'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        def send(path,value,authorized=True):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            headers={'Content-Type':'application/json','Origin':origin}
            if authorized:headers['X-Jarvis-Token']='fixture'
            conn.request('POST',path,json.dumps(value).encode(),headers);r=conn.getresponse();data=json.loads(r.read());conn.close();return r.status,data
        try:
            status,result=send('/api/chats',{'project_id':self.project['id']});self.assertEqual(status,201)
            ident=result['id'];status,view=send('/api/chat/workspace',{'id':ident,'action':'detail'});self.assertEqual(status,200)
            value={'id':ident,'action':'save','config':{'text':'draft'},'revision':view['revision']}
            self.assertEqual(send('/api/chat/workspace',value,False)[0],403)
            self.assertEqual(send('/api/chat/workspace',{**value,'path':'../outside'})[0],400)
            self.assertEqual(send('/api/chat/workspace',value)[0],200)
            self.assertEqual(send('/api/chat/workspace',value)[0],409)
            self.assertEqual(send('/api/chat/workspace',{'id':ident,'action':[]})[0],400)
        finally:server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
