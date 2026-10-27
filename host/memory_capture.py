"""Explicit remember requests become review candidates, even without a cloud reply."""
import re
import sqlite3
from host import memory
from sdk.protocol import CoreError

REQUEST=re.compile(r'^(?:(?:请|帮我|请帮我)\s*)?(?:记住|记一下|记录一下)(?:[：:，,\s]+|(?=我|本项目|这个项目))|^(?:please\s+)?remember\s+(?:that\s+)?',re.I)
SECRET=re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|xai)-[A-Za-z0-9_-]{12,}|(?:\b(?:api[_ -]?key|password)|密码|密钥)\s*(?:[:：=]|是|为|is\b)',re.I)
NO_SAVE=re.compile(r'(?:不要|不许|禁止|别).{0,8}(?:记住|记录|保存|留存)|(?:do not|don\x27t|never|not to).{0,12}(?:remember|record|save|store)',re.I)


def capture(root,command):
    if not command.get('memory_enabled',True) or not REQUEST.match(command['text'].strip()):return {'state':'not_requested'}
    if NO_SAVE.search(command['text']):return {'state':'excluded','reason':'explicit_no_save'}
    if SECRET.search(command['text']):return {'state':'excluded','reason':'possible_credential'}
    if len(command['text'].strip())>4000:return {'state':'excluded','reason':'too_long'}
    try:
        result=memory.command(root,{'action':'propose','turn_id':command['request_id']})
        return {'state':result['state'].lower(),'id':result['id']}
    except (CoreError,OSError,sqlite3.Error) as exc:
        return {'state':'unavailable','reason':exc.code if isinstance(exc,CoreError) else 'memory_unavailable'}


def annotate(root,ident,view,request=None):
    explicit=bool(request and REQUEST.match(request['text'].strip()))
    if not view['enabled']:
        if explicit:view['capture_note']='本轮记忆开关关闭，未自动保存这条记住请求；不要声称已经保存为记忆。'
        return
    db,_=memory.open_memory(root)
    try:row=db.one('SELECT id,state,scope FROM memory_candidates WHERE source_id=?',('turn:'+ident,))
    finally:db.close()
    if row and row['scope']==view['scope'] and row['state']=='PENDING':
        view['capture_note']='本轮原始陈述已保存为待核对记忆候选，尚未成为长期事实，也未新增外发许可。请如实说明需要在“个人记忆与知识 → 待核对”审阅，不声称已经正式记住。'
        view['capture_candidate']=row['id']
    elif explicit:
        view['capture_note']='当前没有属于本轮范围的待核对候选。不要声称本次已经自动记住；已审阅的信息只以当前获准事实为准，必要时请用户在记忆页检查。'
