"""Typed chat-to-commitment adapter. Callers hold the source/domain locks on write."""
import re
import time
from host import commitments as service
from modules.dialogue.store import Dialogues
from modules.task_resource.commitments import Commitments, due
from modules.task_resource.commitment_intent import interpret, resolve, TIME, CLOCK
from sdk.protocol import CoreError, decode, digest


def request_id(turn_id): return digest('chat-commitment-operation:'+turn_id)[:32]


def record_id(turn_id): return digest('chat-commitment:'+turn_id)[:32]


def unpack(value): return decode(value) if isinstance(value,str) else value


def source_digest(turn): return digest([unpack(turn['request']),unpack(turn['assistant_action']),turn['created']])


def context(root, chat):
    records=[]
    if service.exists(root):
        with Commitments(root) as store: records=store.conversation_items(chat['id'])
    active=[r for r in records if r['status'] in ('OPEN','DUE')]
    result=[{'resource':'commitment','id':r['id'],'title':r['title'],'revision':r['revision'],
             'status':r['status'],'due_at':r['due_text'],'active_count':len(active)} for r in active[:6]]
    for turn in reversed(chat['turns']):
        action=turn.get('assistant_action') or {}
        if turn['status']!='SUCCEEDED' or turn['cancel'] or action.get('kind')!='commitment':continue
        candidate=action['commitment'];text=unpack(turn['request'])['text']
        if candidate['basis_turn'] or candidate['operation']!='create' or candidate['quote'].strip()!=text.strip():continue
        decision=interpret(text,'create',candidate['title'],turn['created'])
        if decision['mode']=='NEEDS_TIME':
            if service.exists(root):
                with Commitments(root) as store:
                    if store.operation(request_id(turn['id'])) or store.origin(record_id(turn['id'])):continue
            result.append({'resource':'commitment_draft','id':turn['id'],'title':candidate['title'],
                'source_digest':source_digest(turn),'day_hint':decision['day_hint']})
            if sum(r['resource']=='commitment_draft' for r in result)>=6:break
    return result


def decision(root, turn, chat, *, source_store=None):
    action=unpack(turn['assistant_action']) if isinstance(turn['assistant_action'],str) else turn['assistant_action']
    candidate=action['commitment'];request=unpack(turn['request']);text=request['text']
    base={'mode':'REVIEW','message':'请核对原始请求和本地待办候选。','title':candidate['title'],
          'due_at':None,'needs_time':candidate['operation'] in ('create','reschedule')}
    if len(text)>2000 or candidate['quote'].strip()!=text.strip():
        raise CoreError('commitment_source','The candidate must quote the actual user message')
    if not request.get('assistant_mode') or turn.get('lane','foreground')!='foreground':
        raise CoreError('commitment_source','Only a foreground assistant request can create local commitments')
    if candidate['basis_turn']:
        store=source_store or Dialogues(root)
        try:parent=store.turn(candidate['basis_turn'])
        finally:
            if source_store is None:store.close()
        paction=decode(parent['assistant_action']) if parent.get('assistant_action') else {}
        if (parent['chat_id']!=chat['id'] or parent['status']!='SUCCEEDED' or parent['cancel']
                or paction.get('kind')!='commitment' or source_digest(parent)!=action.get('basis_digest')):
            raise CoreError('commitment_source','Clarification source changed')
        pc=paction['commitment'];ptext=decode(parent['request'])['text']
        if pc['basis_turn'] or pc['operation']!='create' or candidate['operation']!='create' or pc['title']!=candidate['title'] or pc['quote'].strip()!=ptext.strip():
            raise CoreError('commitment_source','Not an unresolved reminder in this conversation')
        prior=interpret(ptext,'create',pc['title'],parent['created'])
        if prior['mode']!='NEEDS_TIME':raise CoreError('commitment_source','Source is not awaiting a time')
        if service.exists(root):
            with Commitments(root) as db:
                if db.operation(request_id(parent['id'])) or db.origin(record_id(parent['id'])):raise CoreError('conflict','The earlier request has already been accepted')
        base.update(parent_turn=parent['id'],parent_digest=source_digest(parent))
        # A short answer must consist only of the requested time; the date is
        # anchored to the original request, not the later acceptance time.
        answer=re.sub(r'^(?:就|改为|设为)','',text.strip()).strip()
        if re.fullmatch(TIME,answer) or re.fullmatch(CLOCK+r'\s*UTC[+-]\d\d:\d\d',answer):
            when=resolve(answer,parent['created'],prior['day_hint'])
            if when:return {**base,'mode':'AUTO','message':'原待办与补充时间已核对','due_at':when,'needs_time':False,
                            'parent_turn':parent['id'],'parent_digest':source_digest(parent)}
        return {**base,'mode':'NEEDS_TIME','message':'请给出具体几点和UTC偏移；尚未保存提醒。'}
    target=None;active_count=0
    if candidate['operation']!='create':
        if not service.exists(root):raise CoreError('commitment_source','No conversation commitment is available')
        with Commitments(root) as db:
            origin=db.origin(action['target']);target=db.read(action['target'])
            active_count=sum(r['status'] in ('OPEN','DUE') for r in db.conversation_items(chat['id']))
        if not origin or origin['chat_id']!=chat['id']:raise CoreError('commitment_source','Target does not belong to this conversation')
        if target['revision']!=action['target_revision'] or target['status'] not in ('OPEN','DUE'):
            raise CoreError('conflict','The commitment changed since this suggestion')
    try:return interpret(text,candidate['operation'],candidate['title'],turn['created'],
        target_title=target['title'] if target else None,active_count=active_count)
    except (CoreError,ValueError,OverflowError):return base


def applied(root, turn, *, source_store=None):
    if not service.exists(root):return None
    turn_id=turn['id']
    with Commitments(root) as store:
        row=store.operation(request_id(turn_id));origin=store.conversation_operation(request_id(turn_id))
        if row and (not origin or origin['source_digest']!=source_digest(turn)):
            raise CoreError('commitment_source','The accepted source changed')
        if not row:
            origin=store.origin(record_id(turn_id))
            if origin:
                chats=source_store or Dialogues(root)
                try:child=chats.turn(origin['turn_id'])
                finally:
                    if source_store is None:chats.close()
                action=decode(child['assistant_action']) if child.get('assistant_action') else {}
                if (origin['source_digest']!=source_digest(child) or action.get('basis_digest')!=source_digest(turn)
                        or child['chat_id']!=turn['chat_id']):
                    raise CoreError('commitment_source','Clarification source changed after acceptance')
                row=store.operation(origin['request_id'])
        if not row:return None
        accepted=store.accepted_record(row['request_id'])
    return {'id':row['id'],'accepted_revision':row['accepted_revision'],'accepted':accepted,'current':row['current']}


def apply(root, turn, chat, *, confirmation=None, source_store=None):
    old=applied(root,turn,source_store=source_store)
    if old:
        candidate=unpack(turn['assistant_action'])['commitment']
        expected=old['accepted']['due_text'] if candidate['operation'] in ('create','reschedule') else None
        if confirmation is not None and confirmation['due_at']!=expected:
            raise CoreError('conflict','This request was accepted with different content; edit the current commitment instead')
        return {'mode':'APPLIED','receipt':old}
    action=unpack(turn['assistant_action']);candidate=action['commitment'];chosen=decision(root,turn,chat,source_store=source_store)
    if chosen['mode']=='NOT_REQUEST':return chosen
    if confirmation is None and chosen['mode']!='AUTO':return chosen
    if confirmation is not None:
        if candidate['operation'] in ('create','reschedule'):
            when=confirmation['due_at'];due(when)
            if when is None and chosen['needs_time']:raise CoreError('commitment_time','An exact reminder time is required')
            chosen['due_at']=when
        elif confirmation['due_at'] is not None:raise CoreError('commitment_invalid','This action has no new time')
    if chosen['due_at'] is not None and due(chosen['due_at'])<=time.time():
        return {**chosen,'mode':'NEEDS_TIME','message':'约定时间已经过去，请选择新的明确时间。','needs_time':True}
    # All clarifications of one original request use the same record identity.
    parent=chosen.get('parent_turn',turn['id'])
    body={'action':candidate['operation'],'id':record_id(parent) if candidate['operation']=='create' else action['target'],
          'request_id':request_id(turn['id'])}
    if candidate['operation']=='create':body.update(title=candidate['title'],source=unpack(turn['request'])['text'],due_at=chosen['due_at'])
    else:
        body['revision']=action['target_revision']
        if candidate['operation']=='reschedule':body['due_at']=chosen['due_at']
    result=service.command(root,body,origin={'chat_id':chat['id'],'turn_id':turn['id'],'source_digest':source_digest(turn)})
    return {'mode':'APPLIED','receipt':result}


def view(root, turn, chat, personal):
    if not personal or chat['archived'] or chat['removed'] or turn['cancel']:
        return {'mode':'UNAVAILABLE','message':'只支持未归档的个人会话；此候选当前不能受理。'}
    try:
        old=applied(root,turn)
        if old:return {'mode':'APPLIED','receipt':old}
        result=decision(root,turn,chat)
        if result['due_at'] is not None and due(result['due_at'])<=time.time():
            result.update(mode='NEEDS_TIME',message='原时间已过去，请给出新的明确时间。',needs_time=True)
        return result
    except (CoreError,ValueError,KeyError) as error:
        return {'mode':'UNAVAILABLE','message':'原文、目标或版本需要重新核对。','code':getattr(error,'code','commitment_source')}
