"""Disposable owner HTTP fixture for actual browser checks; no paid calls."""
import json,sys,threading,time,uuid
from pathlib import Path
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from host.core import Core
from apps.workbench.server import Handler
from control.local_access import LocalAccess
from control.runtime_activity import RequestActivity
from modules.dialogue.store import Dialogues
from modules.workspace.store import Workspace
from modules.task_resource.plans import Plans
from sdk.protocol import canonical

folder=Path(sys.argv[1]).resolve();folder.mkdir(parents=True,exist_ok=False);root=folder/'user-data';Core.initialize(root).close()
workspace=Workspace(root);projects=[]
for name in ('PaK38 · 游戏资产','英语学习 · 日常交流'):
    project=folder/name;project.mkdir();projects.append(workspace.open(str(project)))
workspace.close();store=Dialogues(root);ids={};running=[];queued=[]
def chat(title,project):
    ident=store.create(project);store.db.execute('UPDATE chats SET title=? WHERE id=?',(title,ident));return ident
def turn(cid,title,reply=None,state=None):
    ident='turn-'+uuid.uuid4().hex
    store.begin({'chat_id':cid,'request_id':ident,'text':title,'provider':'synthetic','model':'fixture','reasoning':'default'},[],allow_queue=True)
    if reply:store.finish(ident,{'status':'SUCCEEDED','text':reply})
    if state:(running if state=='running' else queued).append({'id':ident,'chat_id':cid,'lane':'foreground'})
    return ident
a=chat('火炮游戏模型 · LOD交付',projects[0]['id']);ids['model_chat']=a
turn(a,'PaK38 的 LOD0–3 已整理好','已保留高模，四级游戏模型和贴图已整理。LOD0 为 18,420 三角面；LOD3 保留远景轮廓。\n请在模型库检查轮组和炮盾后给我反馈。')
turn(a,'补充模型库中的查看说明','模型库可以切换高模与 LOD，旋转和缩放查看。你提出的新标签会保留在原项目里。')
b=chat('轮组材质与贴图',projects[0]['id']);turn(b,'正在检查轮盘金属与橡胶表现',state='running')
turn(b,'生成固定光照下的材质对比',state='queued')
c=chat('咖啡店口语练习',projects[1]['id']);turn(c,'本轮口语场景已准备好','街角咖啡店已经准备好。你可以用英语点一杯小杯热咖啡，确认转写后提交。\n这里只是场景准备，没有计入你的学习成绩。')
d=chat('日常安排','')
long_result='--long-result' in sys.argv[2:]
turn(d,'合成测试清单按名称合计并保存结果。'*60 if long_result else '今天的工作反馈已整理',
     '\n\n'.join('这是合成测试的成果段落 '+str(i) for i in range(160)) if long_result else '待办与已完成反馈已归入原会话，随时可以继续。')
if long_result:
    archive_dir=folder/'升级验收项目';archive_dir.mkdir()
    workspace=Workspace(root);archive_project=workspace.open(str(archive_dir));workspace.close()
    archived=chat('仅供升级验收的合成会话',archive_project['id'])
    turn(archived,'仅供升级验收的合成会话','合成结果保留在归档。')
    header=store.header(archived);ids['validation_chat']=archived
    (root/'state/validation-archive.json').write_text(canonical({'schema':1,
        'chats':{archived:[header['updated'],header['project_id']]},
        'projects':{archive_project['id']:[archive_project['path'],archive_project['name']]},'work':{}}),encoding='utf-8')
core=Core(root)
with core.db.transaction() as tx:
    goal,_=Plans(core.db).create({'request_id':'fixture-review','goal':'确认模型交付后的下一步'},[],[],tx)
    tx.execute("UPDATE goal_plans SET status='NEEDS_INPUT',proposal=? WHERE id=?",(canonical({'questions':['这次先检查材质，还是先导出游戏资源？']}),goal))
    tx.execute('INSERT INTO chat_goals VALUES(?,?,?)',('fixture-goal-origin',a,goal))
core.close();store.close()
class Fixture(Handler):
    def _do_POST(self):
        if self.path=='/__fixture__/shutdown' and self.origin_allowed(write=True) and self.headers.get('X-Jarvis-Token')==self.server.nonce:
            self.json({'stopped':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
        return super()._do_POST()
    def _do_GET(self):
        if self.path=='/api/mail/companion':return self.json({'status':'disconnected','unread_count':0,'items':[],'snapshot_at':None,'account_generation':'fixture'})
        return super()._do_GET()
server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);server.data_root=root;server.nonce='fixture-work-overview';server.request_activity=RequestActivity()
key='fixture-access-'+uuid.uuid4().hex;server.access=LocalAccess(root,key=key)
server.dialogues=SimpleNamespace(state=lambda:{'running':running,'queued':queued})
(folder/'fixture.json').write_text(json.dumps({'root':str(root),'port':server.server_port,'key':key,'ids':ids,'scope':'Synthetic work and owner only; no real user records or model/provider requests'},indent=2),encoding='utf-8')
print(json.dumps({'port':server.server_port,'folder':str(folder)}),flush=True)
try:server.serve_forever()
finally:server.server_close()
