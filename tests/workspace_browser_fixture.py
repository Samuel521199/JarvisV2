"""Disposable actual owner HTTP surface; synthetic projects/chats only, no inference."""
import json,sys,threading,uuid
from pathlib import Path
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.workbench.server import Handler
from host.core import Core
from control.local_access import LocalAccess
from control.runtime_activity import RequestActivity
from control.application_runtime import publish
from control.atomic import write_json
from modules.workspace.store import Workspace
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences

folder=Path(sys.argv[1]).resolve();folder.mkdir(parents=True,exist_ok=False);root=folder/'user-data';Core.initialize(root).close()
location=folder/'示例项目';location.mkdir();(location/'notes.md').write_text('Synthetic project file retained.\n',encoding='utf-8')
ws=Workspace(root);project=ws.open(str(location));ws.close()
library_preview='--library-preview' in sys.argv[2:]
if library_preview:
    from test_library_preview import add_display_asset
    add_display_asset(root)
else:
    prefs=Preferences(root);prefs.install({'schema_version':1,'default_provider':'fixture','automatic_fallback':False,'fallback_order':['fixture'],'providers':{'fixture':{'adapter':'eachlabs','model':'synthetic-model','enabled':True,'models':{'synthetic-model':{'parameters':{'max_output_tokens':128},'reasoning_levels':[],'enabled':True}}}}},{});prefs.close()
store=Dialogues(root);ids=[]
for index in range(12):
    key=store.create(project['id']);store.update(key,{'title':'同名设计讨论' if index>1 else ['原对话','草稿对话'][index]})
    turn='fixture-'+uuid.uuid4().hex;store.begin({'chat_id':key,'request_id':turn,'text':'合成问题 '+str(index),'provider':'fixture','model':'synthetic-model','reasoning':'default'},[])
    store.finish(turn,{'status':'SUCCEEDED','text':'合成回答与项目记录保留 '+str(index)});ids.append(key)
store.close()
managed='--managed-presentation' in sys.argv[2:]
class Fixture(Handler):
    def _do_GET(self):
        if self.path=='/api/mail/companion':return self.json({'status':'disconnected','unread_count':0,'items':[],'snapshot_at':None,'account_generation':'fixture'})
        if self.path=='/__fixture__/state':
            ws=Workspace(root);d=Dialogues(root)
            try:return self.json({'projects':ws.list(),'chats':d.list(),'turns':d.db.execute('SELECT COUNT(*) FROM turns').fetchone()[0],'original_file_exists':(location/'notes.md').is_file()})
            finally:ws.close();d.close()
        return super()._do_GET()
    def _do_POST(self):
        if managed and self.path=='/__fixture__/presentation' and self.origin_allowed(write=True) and self.headers.get('X-Jarvis-Token')==self.server.nonce:
            change=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            build=change['build']*64;epoch=change['epoch']
            self.server.application_build=build;self.server.application_epoch=epoch
            publish(root,build,epoch,'active')
            write_json(root/'deployment/automation/journal.json',{'phase':change['phase']})
            self.json({'updated':True});return
        if self.path=='/__fixture__/shutdown' and self.origin_allowed(write=True) and self.headers.get('X-Jarvis-Token')==self.server.nonce:
            self.json({'stopped':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
        return super()._do_POST()
server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);server.data_root=root;server.nonce='synthetic-workspace-browser';server.request_activity=RequestActivity()
key='fixture-access-'+uuid.uuid4().hex;server.access=LocalAccess(root,key=key);server.dialogues=SimpleNamespace(state=lambda:{'running':[],'queued':[]})
if managed:
    server.application_build='a'*64;server.application_epoch=1
    publish(root,server.application_build,1,'active')
    (root/'deployment/automation').mkdir(parents=True)
if library_preview:
    from host.dialogue import DialogueHost
    server.dialogues=DialogueHost(root)
(folder/'fixture.json').write_text(json.dumps({'root':str(root),'port':server.server_port,'key':key,'project':project,'ids':ids},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'port':server.server_port,'scope':'synthetic records only'}),flush=True)
try:server.serve_forever()
finally:
    server.server_close()
    if library_preview:server.dialogues.close()
