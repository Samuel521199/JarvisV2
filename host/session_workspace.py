"""Host-owned binding of chats/projects to local folders and result projections."""
import hashlib
from pathlib import Path
import sqlite3

from adapters.desktop.locations import reveal_folder
from control.paths import child
from modules.dialogue.store import Dialogues
from modules.workspace.store import Workspace
from modules.workspace.sessions import Sessions, component
from sdk.protocol import CoreError, decode


def ensure(root,chat,write=False):
    project=None
    if write and (chat['removed'] or chat['archived']): raise CoreError('chat_archived','Restore this conversation first')
    if chat['project_id']:
        workspace=Workspace(root)
        try:
            p=workspace.get(chat['project_id'])
            if write or not p['removed']: project=workspace.path(p['id'])
            else: project=Path(p['path'])
        finally: workspace.close()
        # Own source is not a project output destination. Its chats use runtime storage.
        if project.resolve().is_relative_to(Path(__file__).resolve().parents[1]): project=None
    sessions=Sessions(root)
    try: return sessions.ensure(chat,project)
    finally: sessions.close()


def create(root, project_id=''):
    if not isinstance(project_id,str): raise CoreError('chat_invalid','Invalid project identity')
    if project_id:
        workspace=Workspace(root)
        try: workspace.path(project_id)
        finally: workspace.close()
    chats=Dialogues(root)
    try:
        ident=chats.create(project_id)
        try: ensure(root,chats.read(ident),write=True)
        except BaseException:
            # Only this new, empty chat row; no user content or directory is deleted.
            chats.db.execute('DELETE FROM chats WHERE id=? AND NOT EXISTS(SELECT 1 FROM turns WHERE chat_id=?)',(ident,ident)); raise
        return ident
    finally: chats.close()


def projection(root,chat):
    try: return ensure(root,chat)
    except (CoreError,OSError,sqlite3.Error) as exc:
        return {'status':'unavailable','error':exc.code if isinstance(exc,CoreError) else 'session_folder_unavailable'}


def pending(root,ident,exc):
    sessions=Sessions(root)
    try: sessions.delivery_error(ident,exc.code if isinstance(exc,CoreError) else 'session_folder_unavailable')
    finally: sessions.close()


def publish_reply(root,chat,turn):
    if turn['status']!='SUCCEEDED' or not turn['reply']: return
    if turn.get('memory_context') and decode(turn['memory_context']).get('redacted'):return
    ensure(root,chat,write=True); sessions=Sessions(root)
    try: sessions.publish(chat['id'],'replies/'+component(turn['id'])+'.md',turn['reply'].encode())
    finally: sessions.close()


def deliver_task(core,task_id):
    link=core.db.one('''SELECT g.chat_id FROM goal_plans p LEFT JOIN work_revisions r ON r.goal_id=p.id
        JOIN chat_goals g ON g.goal_id=COALESCE(r.root_goal,p.id) WHERE p.task_id=?''',(task_id,))
    if not link: return
    chats=Dialogues(core.root); sessions=Sessions(core.root)
    try:
        chat=chats.read(link['chat_id']); ensure(core.root,chat,write=True)
        for action in core.tasks.actions(task_id):
            if action['capability']!='artifact.write.v1' or action['status']!='CONFIRMED': continue
            result=decode(action['result'])
            if result.get('redacted'):continue
            path=child(core.root,result['relative_path'])
            if not path.is_file() or path.stat().st_size>2000000: raise CoreError('session_output_invalid','Original artifact is unavailable')
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=result['sha256']: raise CoreError('session_output_invalid','Original artifact changed')
            relative='artifacts/'+component(task_id)+'/'+component(action['id'])+'/'+path.name
            sessions.publish(chat['id'],relative,raw)
    except (CoreError,OSError,sqlite3.Error) as exc:
        pending(core.root,link['chat_id'],exc); raise
    finally: chats.close(); sessions.close()


def command(root,value):
    fields={'detail':set(),'save':{'config','revision'},'reveal':set(),'sync':set()}
    if not isinstance(value,dict) or not isinstance(value.get('action'),str) or value['action'] not in fields or set(value)!={'id','action'}|fields[value['action']]:
        raise CoreError('invalid_request','Unexpected conversation folder command')
    chats=Dialogues(root); sessions=Sessions(root)
    try:
        chat=chats.read(value['id']); action=value['action']
        info=ensure(root,chat,write=action in {'save','sync'})
        if action=='save': return sessions.save(chat['id'],value['config'],value['revision'])
        if action=='reveal': return reveal_folder(sessions.path(chat['id']))
        if action=='sync':
            for turn in chat['turns']: publish_reply(root,chat,turn)
            from host.core import Core
            core=Core(root)
            try:
                for row in core.db.all('''SELECT p.task_id FROM goal_plans p LEFT JOIN work_revisions r ON r.goal_id=p.id
                    JOIN chat_goals g ON g.goal_id=COALESCE(r.root_goal,p.id) WHERE g.chat_id=? AND p.task_id IS NOT NULL''',(chat['id'],)):
                    deliver_task(core,row['task_id'])
            finally: core.close()
            sessions.delivery_error(chat['id'],None)
            info=sessions.info(chat['id'])
        return {**info,**sessions.files(chat['id'])}
    finally: sessions.close(); chats.close()
