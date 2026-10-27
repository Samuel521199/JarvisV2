"""Read-only origin capture and local, explicitly previewed memory transfer."""
from host.memory import open_memory, scope_for
from modules.context_knowledge.bundle import Bundle
from modules.context_knowledge.collection import Collection,FORMAT as COLLECTION
from modules.dialogue.store import Dialogues
from sdk.protocol import CoreError, decode, digest


def origin(root,db,scope,kind,row):
    ref=row['source'] if kind=='fact' else row['source_id']
    if ref.startswith('turn:'):
        chats=Dialogues(root)
        try:
            turn=chats.db.execute('SELECT * FROM turns WHERE id=?',(ref[5:],)).fetchone()
            if not turn:return {'kind':'unavailable','reference':ref}
            chat=chats.read(turn['chat_id'])
            context=decode(turn['memory_context']) if turn['memory_context'] else {}
            if chat['removed'] or context.get('scope',chat['project_id'] or 'personal')!=scope:return {'kind':'unavailable','reference':ref}
            return {'kind':'user_statement','reference':ref,'text':decode(turn['request'])['text'],
                    'trust':'imported_statement_not_independent_verification'}
        finally:chats.close()
    if ref.startswith('goal:'):
        goal=db.one('SELECT g.*,c.scope FROM goal_plans g JOIN goal_context c ON g.id=c.goal_id WHERE g.id=?',(ref[5:],))
        if not goal or goal['scope']!=scope:return {'kind':'unavailable','reference':ref}
        actions=db.all('SELECT id,capability,status,digest FROM actions WHERE task_id=?',(goal['task_id'],)) if goal['task_id'] else []
        return {'kind':'task_receipt','reference':ref,'request':decode(goal['request']),'actions':actions,
                'trust':'imported_receipt_not_local_execution','task_id':goal['task_id']}
    return {'kind':'statement','reference':ref,'trust':'owner_reviewed' if ref=='owner:explicit' else 'unverified_origin'}


def command(root,value):
    fields={'export':{'scope'},'export_collection':{'scope'},'preview':{'scope','bundle'},'restore':{'scope','bundle','token'},'origin':{'scope','id'}}
    if not isinstance(value,dict) or value.get('action') not in fields or set(value)!={'action'}|fields[value['action']]:
        raise CoreError('memory_invalid','Unexpected memory transfer command')
    from modules.context_knowledge.joint import writable
    writable(value['scope'])
    scope=scope_for(root,value['scope']);db,_=open_memory(root)
    try:
        transfer=Bundle(db)
        if value['action']=='export':return transfer.export(scope,lambda k,r:origin(root,db,scope,k,r))
        if value['action']=='export_collection':
            if db.one('SELECT 1 FROM memory_domains WHERE id=?',(scope,)):raise CoreError('memory_domain_export','Select the parent project or personal root to migrate its domains')
            return Collection(db).export(scope,lambda s,k,r:origin(root,db,s,k,r))
        if isinstance(value.get('bundle'),dict) and value['bundle'].get('format') in {COLLECTION,'jarvis.memory-collection.v1'}:transfer=Collection(db)
        if value['action']=='preview':return transfer.preview(scope,value['bundle'])
        if value['action']=='restore':return transfer.restore(scope,value['bundle'],value['token'])
        row=db.one('SELECT body,checksum FROM memory_origins WHERE id=? AND scope=?',(value['id'],scope))
        if not row:raise CoreError('memory_missing','No imported origin')
        return {'origin':decode(row['body']),'checksum':row['checksum'],'trusted_execution':False}
    finally:db.close()
