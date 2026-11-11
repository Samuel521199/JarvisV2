"""Bounded projections of original records, not another task ledger."""
import sqlite3
import hashlib
import time
from control.paths import data_root, child
from host.core import Core
from modules.task_resource.scheduling import Scheduling
from sdk.protocol import CoreError, decode

LABELS = {'running': '运行中', 'queued': '排队中', 'needs_input': '等待你回答',
          'external': '等待外部', 'waiting': '等待条件', 'unknown': '状态待核对',
          'finished': '执行完成', 'failed': '失败', 'cancelled': '已取消'}


def category(status, error=None):
    if status == 'UNKNOWN' or error in {'unknown_effect', 'host_interrupted', 'model_unknown'}: return 'unknown'
    if status in {'RUNNING', 'PLANNING', 'BUILDING', 'GENERATING', 'DISPATCHING', 'running'}: return 'running'
    if status in {'READY', 'QUEUED', 'queued'}: return 'queued'
    if status in {'NEEDS_INPUT', 'REVIEW', 'WAITING_AUTH', 'WAITING_SCOPE', 'WAITING_BROWSER'}: return 'needs_input'
    if status in {'SUCCEEDED', 'DELIVERED', 'COMPLETED', 'finished', 'REJOINED', 'completed'}: return 'finished'
    if status in {'FAILED', 'INVALID', 'failed'}: return 'failed'
    if status in {'CANCELLED', 'cancelled'}: return 'cancelled'
    return 'waiting'


def snapshot(root, server):
    root = data_root(root); now = time.time(); items = []; sources = []; outcome_checks = 0
    core = Core(root)
    try:
        schedule = Scheduling(core.db); metadata = {r['task_id']: r for r in core.db.all('SELECT * FROM task_dispatch ORDER BY requested DESC,queued_at DESC LIMIT 132')}; policy = schedule.policy()
        goals = core.db.all("SELECT id,task_id,status,error,request,proposal FROM goal_plans ORDER BY CASE WHEN status IN ('PLANNING','RUNNING','NEEDS_INPUT','REVIEW') THEN 0 ELSE 1 END,created DESC LIMIT 100")
        by_task = {g['task_id']: g for g in goals if g['task_id']}
        for row in core.db.all("SELECT id,status,body,error,deadline,revision FROM tasks ORDER BY CASE WHEN status='RUNNING' THEN 0 WHEN id IN (SELECT task_id FROM task_dispatch WHERE requested=1) THEN 1 WHEN status IN ('READY','WAITING') THEN 2 ELSE 3 END,created DESC LIMIT 100"):
            meta = metadata.get(row['id'], {}); group = category(row['status'], row['error'])
            if row['status'] in {'READY', 'WAITING'} and group != 'unknown':
                group = 'queued' if meta.get('requested') else 'waiting'
            goal = by_task.get(row['id'])
            wait = (core.db.one('SELECT state,reason,wake_count,deadline FROM task_waits WHERE task_id=?',(row['id'],))
                    if core.db.one("SELECT name FROM sqlite_master WHERE name='task_waits'") else None)
            items.append({'id': row['id'], 'source': 'tasks', 'goal_id': goal['id'] if goal else None,
                          'title': decode(row['body'])['goal'], 'state': group, 'raw_status': row['status'],
                          'reason': meta.get('wait_reason') or row['error'] or ('尚未启动' if group == 'waiting' else ''),
                          'priority': meta.get('priority', 1), 'importance': meta.get('importance', 1),
                          'due_at': meta.get('due_at'), 'priority_reason': meta.get('reason', '普通优先级'),
                          'result_revision': row['revision'], 'revision': meta.get('revision', 0), 'cancelable': row['status'] not in {'SUCCEEDED', 'FAILED', 'CANCELLED'},
                          'queued_at': meta.get('queued_at'), 'started_at': meta.get('started_at')})
            if wait:items[-1]['recovery_wait']=wait
            if goal:items[-1]['work']=core.works.projection(goal['id'])
            if row['status'] in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:
                from host.outcomes import observe
                items[-1]['outcome'] = observe(core, row['id'], cached=outcome_checks >= 4)
                if outcome_checks < 4:
                    from host.completion import projection
                    items[-1]['completion']=projection(core,row['id'])
                outcome_checks += 1
        for row in goals:
            if row['task_id']: continue
            proposal = decode(row['proposal']) if row['proposal'] else {}
            items.append({'id': row['id'], 'source': 'goals', 'title': decode(row['request'])['goal'],
                          'state': category(row['status'], row['error']), 'raw_status': row['status'],
                          'reason': row['error'] or ('；'.join(proposal.get('questions', [])) if proposal else '')})
            items[-1]['work']=core.works.projection(row['id'])
        for row in core.db.all("SELECT id,status,spec,error FROM development_runs ORDER BY CASE WHEN status IN ('RUNNING','PLANNING','BUILDING','REVIEW') THEN 0 ELSE 1 END,created DESC LIMIT 40"):
            linked = core.db.one('SELECT goal_id FROM goal_growth WHERE development_id=?', (row['id'],))
            if linked:
                match = next((i for i in items if i['id'] == linked['goal_id'] or i.get('goal_id') == linked['goal_id']), None)
                if match:
                    match.update(state=category(row['status'], row['error']), phase='能力研发', reason=row['error'] or '')
                    continue
            spec = decode(row['spec'])
            items.append({'id': row['id'], 'source': 'development', 'title': spec.get('goal', '能力研发'),
                          'state': category(row['status'], row['error']), 'reason': row['error'] or ''})
        sources.append({'id': 'core', 'status': 'connected', 'limit': 100})
        from host.outcomes import status as outcome_status
        outcome_observer = outcome_status(core)
    finally: core.close()
    from host.commitments import projection as commitments_projection
    try:
        items.extend(commitments_projection(root))
        sources.append({'id':'commitments','status':'connected','limit':200})
    except (sqlite3.Error, OSError, CoreError):
        sources.append({'id':'commitments','status':'unavailable'})
    from host.standing_work import projection as standing_projection
    try:
        standing_items,standing_tasks=standing_projection(root)
        items=[i for i in items if i.get('id') not in standing_tasks]
        items.extend(standing_items);sources.append({'id':'standing','status':'connected'})
    except (CoreError,OSError,sqlite3.Error):sources.append({'id':'standing','status':'unavailable'})
    suppressed_turns = set()
    for name, path in [('studio3d', 'state/studio3d.sqlite3'), ('images', 'state/image-generation.sqlite3')]:
        target = child(root, path)
        if not target.exists():
            sources.append({'id': name, 'status': 'not_started'}); continue
        db = None
        try:
            db = sqlite3.connect(target.as_uri()+'?mode=ro', uri=True, timeout=.1); db.row_factory = sqlite3.Row
            for row in db.execute('SELECT id,status,error,turn_id FROM jobs ORDER BY created DESC LIMIT 40'):
                if row['turn_id']: suppressed_turns.add(row['turn_id'])
                state = category(row['status'], row['error'])
                if state == 'running':
                    from host import studio3d, image_generation
                    module = studio3d if name == 'studio3d' else image_generation
                    with module.GUARD: live = (str(root), row['id']) in module.ACTIVE
                    if not live: state = 'unknown'
                items.append({'id': row['id'], 'source': name, 'title': '3D 工作室' if name == 'studio3d' else '图片生成',
                              'state': state, 'reason': row['error'] or ''})
            sources.append({'id': name, 'status': 'connected', 'limit': 40})
        except (sqlite3.Error, OSError): sources.append({'id': name, 'status': 'unavailable'})
        finally:
            if db: db.close()
    dialogues = getattr(server, 'dialogues', None)
    if dialogues:
        state = dialogues.state()
        for group in ('running', 'queued'):
            for row in state[group]:
                if row['id'] in suppressed_turns: continue
                items.append({'id': row['id'], 'source': 'dialogue', 'chat_id': row['chat_id'],
                              'title': '聊天回复' if row['lane'] == 'foreground' else '后台模型请求', 'state': group})
        sources.append({'id': 'dialogue', 'status': 'connected'})
    else: sources.append({'id': 'dialogue', 'status': 'not_connected'})
    # Recent terminal replies join the same view. No private-family chat store is read.
    target = child(root, 'state/dialogue.sqlite3')
    if target.exists():
        db = sqlite3.connect(target.as_uri()+'?mode=ro', uri=True, timeout=.1)
        db.row_factory = sqlite3.Row
        try:
            for row in db.execute("SELECT t.id,t.chat_id,t.status,t.reply,t.error,c.title FROM turns t JOIN chats c ON c.id=t.chat_id WHERE t.lane='foreground' AND c.removed=0 AND c.archived=0 AND t.status NOT IN ('READY','RUNNING') ORDER BY t.created DESC LIMIT 40"):
                if row['id'] not in suppressed_turns:
                    items.append(dialogue_item(dict(row)))
        finally: db.close()
    mailbox = getattr(server, 'mailbox', None)
    from host.mail_standing import projection as mail_standing_projection
    try:
        items.extend(mail_standing_projection(root));sources.append({'id':'mail_standing','status':'connected'})
    except (CoreError,sqlite3.Error,OSError):sources.append({'id':'mail_standing','status':'unavailable'})
    if mailbox:
        try:
            from modules.mail.store import MailStore
            store = MailStore(root)
            try:
                for row in store.listing('job', 40):
                    if row.get('mail_watch'):continue
                    items.append({'id': row['id'], 'source': 'mail', 'title': '邮件任务 · '+str(row.get('action', row.get('operation', '处理'))),
                                  'state': category(row['status'], row.get('error')), 'reason': row.get('error') or ''})
            finally: store.close()
            sources.append({'id': 'mail', 'status': 'connected', 'limit': 40})
        except (sqlite3.Error, OSError): sources.append({'id': 'mail', 'status': 'unavailable'})
    else: sources.append({'id': 'mail', 'status': 'not_connected'})
    from host import knowledge, knowledge_extraction
    with knowledge.JOBS_LOCK:
        job = knowledge.JOBS.get(str(root))
        if job: items.append({'id': 'knowledge-index-'+job.get('generation', 'legacy'), 'source': 'knowledge', 'title': '资料库索引', 'state': category(job['state']), 'reason': job.get('error') or ''})
    with knowledge_extraction.LOCK:
        future = knowledge_extraction.ACTIVE.get(str(root))
        if future and not future.done(): items.append({'id': 'knowledge-extraction', 'source': 'knowledge', 'title': '知识提取', 'state': 'running'})
    sources.append({'id': 'knowledge', 'status': 'connected'})
    sources.extend({'id': s, 'status': 'not_connected'} for s in ('private-dialogue', 'anatomy', 'local-model-operations'))
    from modules.continuity.attention import Attention
    attention = Attention(root)
    try: attention.project(items)
    finally: attention.close()
    from host.runtime_participants import snapshot as participants
    activity = participants(root, server)
    counts = {key: sum(i['state'] == key for i in items) for key in LABELS}
    runner = getattr(server, 'task_runner', None)
    return {'sampled_at': now, 'fresh_for_seconds': 5, 'counts': counts, 'items': items, 'labels': LABELS,
            'sources': sources, 'policy': policy, 'runner': runner.state() if runner else None,
            'outcome_observer': outcome_observer, 'activity': activity,
            'unread_count': sum(item['attention']['unread'] for item in items),
            'coverage': '已接入来源的近期记录；未接入来源不等于没有工作'}


def dialogue_item(row):
    return {'id': row['id'], 'source': 'dialogue', 'chat_id': row['chat_id'],
            'title': row.get('title', '聊天回复'), 'state': category(row['status'], row.get('error')),
            'raw_status': row['status'], 'reason': row.get('error') or '',
            'result_revision': hashlib.sha256((row.get('reply') or '').encode()).hexdigest()}


def decorate_chat(root, chat):
    from modules.continuity.attention import Attention
    items = [dialogue_item(turn) for turn in chat['turns']]
    store = Attention(root)
    try: store.project(items)
    finally: store.close()
    for turn, item in zip(chat['turns'], items):
        turn['attention'] = item['attention']
    return chat


def acknowledge(root, server, body):
    from modules.continuity.attention import Attention
    from sdk.protocol import CoreError
    if not isinstance(body, dict) or set(body) != {'action', 'key', 'version'} or body['action'] != 'viewed':
        raise CoreError('attention_invalid', 'Expected a result read receipt')
    if not isinstance(body['key'], str) or len(body['key']) > 200 or not isinstance(body['version'], str) or len(body['version']) != 64:
        raise CoreError('attention_invalid', 'Invalid result identity')
    # A read marker never resumes, retries or changes the original work.
    item = next((row for row in snapshot(root, server)['items'] if row['attention']['key'] == body['key']), None)
    if item is None and body['key'].startswith('dialogue:'):
        from modules.dialogue.store import Dialogues
        chats = Dialogues(root)
        try:
            turn = chats.turn(body['key'].split(':', 1)[1])
            header = chats.header(turn['chat_id'])
            if not header['removed'] and not header['archived'] and turn['lane'] == 'foreground':
                item = dialogue_item(turn)
        finally: chats.close()
    if item is None: raise CoreError('attention_missing', 'This result is no longer available')
    store = Attention(root)
    try: return store.acknowledge(item, body['version'])
    finally: store.close()
