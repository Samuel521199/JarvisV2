"""Personal local commitments over the existing scheduler and attention projection."""
from control.paths import child, data_root
from control.recovery.gate import StopGate
from control.application_runtime import require_accepting, accepting
from modules.task_resource.commitments import Commitments
from sdk.protocol import CoreError


def exists(root): return child(data_root(root),'state/commitments.sqlite3').exists()


def command(root, body, runner=None, *, origin=None):
    # Cancellation remains available while paused/draining; all fields are
    # validated by the domain command before any write.
    if not isinstance(body,dict) or body.get('action') != 'cancel':
        require_accepting(root); StopGate(root).require_running()
    with Commitments(root) as store: result=store.command(body,origin=origin)
    if runner is not None: runner.wake.set()
    return result


def advance(root):
    if not exists(root) or not accepting(root) or StopGate(root).state() != 'ready': return 0
    with Commitments(root) as store: return store.advance()


def projection(root):
    if not exists(root): return []
    with Commitments(root) as store: rows=store.listing()
    items=[]
    for row in rows:
        state={'OPEN':'waiting','DUE':'needs_input','DONE':'finished','CANCELLED':'cancelled'}[row['status']]
        items.append({'id':row['id'],'source':'commitments','title':row['title'],'state':state,
            'raw_status':row['status'],'reason':{'OPEN':'等待约定时间' if row['due_at'] is not None else '个人待办，尚未标记完成',
            'DUE':'已到期并进入本地提醒视图；已阅不等于事项已完成','DONE':'主人已标记完成','CANCELLED':'主人已取消'}[row['status']],
            'result_revision':row['revision'],'revision':row['revision'],'due_at':row['due_at'],
            'due_text':row['due_text'],'posted_at':row['posted_at'],'source_note':row['source'],
            'cancelable':row['status'] in ('OPEN','DUE')})
    return items


def read(root):
    from modules.continuity.attention import Attention
    items=projection(root)
    store=Attention(root)
    try: store.project(items)
    finally: store.close()
    return {'schema':'jarvis.commitments.v1','items':items,'delivery':'local_work_view_only'}


def detail(root, ident):
    if not exists(root): raise CoreError('commitment_missing','Commitment does not exist')
    with Commitments(root) as store:
        origin=store.origin(ident)
        return {'current':store.read(ident),'history':store.history(ident),'source_kind':'chat_turn' if origin else 'user_note',
                'conversation_origin':origin,
                'completion_evidence':'user_marked_only','delivery':'local_work_view_only'}
