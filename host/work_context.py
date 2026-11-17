"""Read-only owner context for work cards; no second task or receipt store."""
import json
import sqlite3
from control.paths import child


def text(value,limit=160):
    return ' '.join(str(value or '').split())[:limit]


def read(root,name,sql,params=()):
    path=child(root,name)
    if not path.exists():return []
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.1);db.row_factory=sqlite3.Row
    try:return [dict(r) for r in db.execute(sql,params)]
    finally:db.close()


def attach(root,items):
    """Only explicit chat/turn/goal links supply project identity, never titles."""
    try:
        projects={r['id']:r for r in read(root,'state/workspace.sqlite3','SELECT id,name FROM projects WHERE removed=0')}
        model_assets={}
        if any(i['source']=='studio3d' for i in items):
            from host.work_artifact_context import model_links
            try:model_assets=model_links(root)
            except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):pass
        goal_ids={i.get('goal_id') or (i['id'] if i['source']=='goals' else None) for i in items}-{None}
        roots={}
        for item in items:
            if item['source']=='mail':
                item['title']={'send':'发送邮件','read':'读取邮件','sync':'同步邮箱','list':'读取邮件列表','check':'检查邮箱连接','trash':'移入邮件回收站','labels':'整理邮件标签'}.get(item.get('operation'),item['title'])
            ident=item.get('goal_id') or (item['id'] if item['source']=='goals' else None)
            if ident:roots[ident]=(item.get('work') or {}).get('root_goal') or ident
        goal_ids.update(roots.values())
        links={}
        if goal_ids:
            # The current chat-goal association is used only for that exact goal.
            names=sorted(goal_ids);marks=','.join('?' for _ in names)
            links={r['goal_id']:r['chat_id'] for r in read(root,'state/core.sqlite3','SELECT goal_id,chat_id FROM chat_goals WHERE goal_id IN ('+marks+')',names)}
        turns={};names=list({i['id'] if i['source']=='dialogue' else i.get('turn_id') for i in items}-{None})
        if names:
            marks=','.join('?' for _ in names)
            turns={r['id']:r for r in read(root,'state/dialogue.sqlite3',
                "SELECT t.id,t.chat_id,t.request,t.reply,t.created,t.assistant_action FROM turns t JOIN chats c ON c.id=t.chat_id WHERE c.removed=0 AND c.archived=0 AND t.lane='foreground' AND t.id IN ("+marks+')',names)}
        chat_ids={i.get('chat_id') for i in items}|set(links.values())|{t['chat_id'] for t in turns.values()};chat_ids.discard(None)
        chats={}
        if chat_ids:
            names=sorted(chat_ids);marks=','.join('?' for _ in names)
            chats={r['id']:r for r in read(root,'state/dialogue.sqlite3','SELECT id,title,project_id FROM chats WHERE removed=0 AND archived=0 AND id IN ('+marks+')',names)}
        for source,path in [('studio3d','state/studio3d.sqlite3'),('images','state/image-generation.sqlite3')]:
            names=[i['id'] for i in items if i['source']==source]
            if not names:continue
            marks=','.join('?' for _ in names)
            titles={r['id']:r['title'] for r in read(root,path,"SELECT id,json_extract(receipt,'$.title') AS title FROM jobs WHERE id IN ("+marks+')',names)}
            for item in items:
                if item['source']==source and titles.get(item['id']):item['title']=text(titles[item['id']],120)
        for item in items:
            goal=item.get('goal_id') or (item['id'] if item['source']=='goals' else None)
            work_goal=roots.get(goal,goal)
            turn=turns.get(item['id'] if item['source']=='dialogue' else item.get('turn_id'))
            chat_id=item.get('chat_id') or links.get(work_goal) or links.get(goal) or (turn['chat_id'] if turn else None)
            chat=chats.get(chat_id);project=projects.get(chat['project_id']) if chat else None
            removed_project=bool(chat and chat['project_id'] and not project)
            asset=model_assets.get(item['id']) if item['source']=='studio3d' and not chat else None
            summary='';action=None
            if turn:
                try:
                    request=json.loads(turn['request']);action=json.loads(turn['assistant_action']) if turn['assistant_action'] else None
                except (ValueError,TypeError):request={}
                if item['source']=='dialogue':
                    summary=text(turn['reply'])
                    item['title']=text(request.get('text'),90) or item['title']
                    if isinstance(action,dict) and action.get('kind')=='goal':
                        # Do not infer that every reply in a chat is its latest goal.
                        bound=action.get('goal_id') or action.get('id')
                        if bound in goal_ids:goal=bound;work_goal=roots.get(bound,bound)
            fallback={'studio3d':'模型工作室 · 未关联项目','images':'图片工作室 · 未关联项目','commitments':'个人待办','standing':'持续安排','mail_standing':'邮件持续安排','mail':'邮件工作','knowledge':'资料库工作','tasks':'独立任务','goals':'目标工作','development':'能力研发'}.get(item['source'],'其他工作')
            item['context']={'project_id':project['id'] if project else '',
                'group_id':project['id'] if project else '$removed' if removed_project else '$independent' if chat else '$library:'+asset[0] if asset else '$'+item['source'],
                'project_name':text(project['name'],100) if project else '项目已移除的工作' if removed_project else '独立会话' if chat else '模型库 · '+text(asset[1],100) if asset else fallback,
                'chat_id':chat['id'] if chat else None,'chat_title':text(chat['title'],100) if chat else '',
                'summary':summary,'updated_at':item.get('updated_at') or (turn['created'] if turn else item.get('created')) or item.get('posted_at') or 0,
                'unit_id':'goal:'+work_goal if work_goal else 'chat:'+chat['id'] if chat else 'library:'+asset[0] if asset else item['source']+':'+item['id'],
                'routine':item['source']=='mail' and item.get('operation') in {'read','check','sync','list'} and item['state']=='finished'}
        return True
    except (sqlite3.Error,OSError):
        # Preserve work and original read receipts if a context source is offline.
        return False
