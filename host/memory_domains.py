"""Owner-selected conversation domains. No path, task execution or grant changes."""
from host.memory import LOCK,open_memory,scope_for
from modules.context_knowledge.domains import Domains
from modules.context_knowledge import joint
from modules.dialogue.store import Dialogues
from sdk.protocol import CoreError


def chat_scope(root,chat,*,db=None):
    base=chat['project_id'] or 'personal';owned=db is None
    if owned:db,_=open_memory(root)
    try:
        row=db.one('SELECT scope FROM memory_chat_scopes WHERE chat_id=?',(chat['id'],))
        if not row or row['scope']==base:return scope_for(root,base)
        if scopes:=joint.members(row['scope']):
            if base not in scopes:raise CoreError('memory_invalid','Joint context must explicitly include the conversation scope')
            return scope_for(root,row['scope'])
        domain=Domains(db).get(row['scope'])
        if domain['parent']!=base:raise CoreError('memory_domain_missing','Domain does not belong to this conversation project')
        scope_for(root,base);return domain['id']
    finally:
        if owned:db.close()


def command(root,value):
    fields={'list':{'parent'},'create':{'parent','kind','name','snapshot'},'archive':{'id','revision','archived'},
            'binding':{'chat_id'},'bind':{'chat_id','scope','revision'},'source':{'scope','id','revision'},
            'merge_preview':{'scope'},'merge':{'scope','token','choices'},'source_inherited':{'scope'},
            'source_fork':{'scope','id','revision'},'source_merge_preview':{'scope'},
            'source_merge_detail':{'scope','id'},'source_merge':{'scope','token','choices'}}
    if not isinstance(value,dict) or value.get('action') not in fields or set(value)!={'action'}|fields[value['action']]:
        raise CoreError('memory_invalid','Unexpected domain command')
    db,_=open_memory(root)
    try:
        with LOCK:
            domains=Domains(db);action=value['action']
            if action in {'source_inherited','source_fork','source_merge_preview','source_merge_detail','source_merge'}:
                from modules.context_knowledge.source_merge import SourceMerge
                scope_for(root,value['scope']);manager=SourceMerge(db)
                if action=='source_inherited':return {'sources':manager.inherited(value['scope'])}
                if action=='source_fork':return manager.fork(value['scope'],value['id'],value['revision'])
                if action=='source_merge_preview':return manager.preview(value['scope'])
                if action=='source_merge_detail':return manager.detail(value['scope'],value['id'])
                return manager.apply(value['scope'],value['token'],value['choices'])
            if action in {'merge_preview','merge'}:
                from modules.context_knowledge.merge import Merge
                scope_for(root,value['scope'])
                if action=='merge_preview':return Merge(db).preview(value['scope'])
                return Merge(db).apply(value['scope'],value['token'],value['choices'])
            if action in {'list','create'}:
                joint.writable(value['parent'])
                parent=scope_for(root,value['parent'])
                if action=='list':return {'domains':domains.list(parent)}
                return domains.create(parent,value['kind'],value['name'],value['snapshot'])
            if action=='archive':return domains.archive(value['id'],value['revision'],value['archived'])
            if action=='source':
                scope_for(root,value['scope']);return domains.historical_source(value['scope'],value['id'],value['revision'])
            chats=Dialogues(root)
            try:
                chat=chats.read(value['chat_id']);base=chat['project_id'] or 'personal'
                scope_for(root,base)
                row=db.one('SELECT * FROM memory_chat_scopes WHERE chat_id=?',(chat['id'],)) or {'chat_id':chat['id'],'scope':base,'revision':0}
                if action=='binding':
                    named=db.one('SELECT name FROM memory_domains WHERE id=?',(row['scope'],))
                    members=joint.members(row['scope'])
                    return row|{'parent':base,'label':('联合检索 · '+str(len(members))+' 个范围') if members else named['name'] if named else None,
                                'scopes':members or [row['scope']]}
                scope=scope_for(root,value['scope'])
                members=joint.members(scope)
                if members:
                    if base not in members:raise CoreError('memory_invalid','Explicitly include the current conversation scope')
                elif scope!=base and domains.get(scope)['parent']!=base:raise CoreError('memory_invalid','Domain belongs to another project')
                if type(value['revision']) is not int or row['revision']!=value['revision']:raise CoreError('conflict','Conversation scope changed')
                if any(t['status'] in {'READY','RUNNING'} for t in chat['turns']):raise CoreError('chat_busy','Stop the current reply before switching scope')
                with db.transaction() as tx:
                    tx.execute('INSERT INTO memory_chat_scopes VALUES(?,?,?) ON CONFLICT(chat_id) DO UPDATE SET scope=excluded.scope,revision=excluded.revision',
                               (chat['id'],scope,row['revision']+1))
                return {'scope':scope,'revision':row['revision']+1}
            finally:chats.close()
    finally:db.close()
