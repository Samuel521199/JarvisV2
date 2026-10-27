"""Explicit, paginated redaction of source-dependent local projections.

The two SQLite stores commit independently. A durable pending receipt precedes
chat redaction; interruption is visible and a new preview safely resumes work.
No source files, original user requests, task results or external copies touched.
"""
import time
import uuid
import hashlib

from modules.context_knowledge.knowledge import Knowledge, VERSION
from modules.context_knowledge.memory import Memory
from modules.dialogue.store import Dialogues
from modules.workspace.sessions import Sessions
from sdk.protocol import CoreError, canonical, decode, digest
from host import knowledge_outputs

PAGE = 200
EXCLUDED = ['original_requests','development_code_and_packages','unattributed_outputs','modified_projection_files',
            'exports_and_backups','external_providers','sqlite_recoverable_pages']


def inspect(db, chats, scope, cursor):
    if (not isinstance(cursor,dict) or set(cursor)!={'goals','turns'} or
        any(not isinstance(v,str) or len(v)>100 for v in cursor.values())):
        raise CoreError('knowledge_invalid','Invalid cleanup cursor')
    sources={r['id']:r for r in db.all("SELECT id,revision,status FROM knowledge_sources s WHERE scope=? OR EXISTS(SELECT 1 FROM memory_snapshots m WHERE m.domain_id=? AND m.kind='source' AND m.id=s.id) OR EXISTS(SELECT 1 FROM memory_source_branches b JOIN knowledge_sources p ON p.id=b.parent_id WHERE b.source_id=s.id AND p.scope=?)",(scope,scope,scope))}
    for r in db.all("SELECT f.id,f.revision,f.deleted,u.paused,u.expires FROM facts f LEFT JOIN memory_usage u ON u.fact_id=f.id WHERE f.scope=? OR (f.scope='personal' AND u.purpose='style') OR EXISTS(SELECT 1 FROM memory_snapshots m WHERE m.domain_id=? AND m.kind='fact' AND m.id=f.id) OR EXISTS(SELECT 1 FROM knowledge_claims c JOIN memory_source_branches b ON b.source_id=c.source_id JOIN knowledge_sources p ON p.id=b.parent_id WHERE c.fact_id=f.id AND p.scope=?)",(scope,scope,scope)):
        r['status']='active' if not r['deleted'] and r['paused']==0 and (r['expires'] is None or r['expires']>time.time()) else 'inactive'
        sources[r['id']]=r
    def relevant(view):return [r for r in view.get('dependencies',view.get('facts',[])) if r.get('id') in sources]
    def affected(view):
        refs=relevant(view)
        if not refs:return False
        if view.get('scope') and view.get('provider'):
            return not Memory(db).references_valid(view['scope'],view['provider'],view.get('enabled',True),refs,view.get('selectors'))
        return any(r.get('id') in sources and (sources[r['id']]['status']!='active' or sources[r['id']]['revision']!=r.get('revision'))
                   for r in refs)
    goals=db.all('SELECT goal_id,scope,view FROM goal_context WHERE goal_id>? ORDER BY goal_id LIMIT ?', (cursor['goals'],PAGE+1))
    turns=chats.cleanup_page(scope,cursor['turns'],PAGE+1,all_scopes=True)
    selected_goals=[];selected_turns=[];busy=0;busy_goals=0;unknown=0
    for row in goals[:PAGE]:
        view=decode(row['view'])
        refs=relevant(view)
        stale=bool(refs) and (any(not Memory(db).references_valid(row['scope'],p,True,refs,view.get('selectors')) for p in view.get('providers',[])) if view.get('providers') else affected(view))
        if not view.get('redacted') and stale:
            outputs=knowledge_outputs.inspect(db,row['goal_id'])
            if outputs['busy']:busy_goals+=1
            else:row['outputs']=outputs;selected_goals.append(row)
    for row in turns[:PAGE]:
        view=decode(row['memory_context']) if row['memory_context'] else {}
        if not view:unknown+=1;continue
        if not view.get('redacted') and affected(view):
            if row['status'] in {'READY','RUNNING'}:busy+=1
            else:selected_turns.append(row)
    basis={'scope':scope,'epoch':Memory(db).epoch(),'cursor':cursor,'goals':selected_goals,'turns':selected_turns}
    return {'goals':selected_goals,'turns':selected_turns,'token':digest(basis),
            'counts':{'goals':len(selected_goals),'turns':len(selected_turns),'busy_turns':busy,'busy_goals':busy_goals,'unknown_provenance':unknown,
                      'tasks':sum(bool(r['outputs']['task']) for r in selected_goals),'model_results':sum(len(r['outputs']['calls']) for r in selected_goals)},
            'next_cursor':{'goals':goals[PAGE-1]['goal_id'] if len(goals)>PAGE else (goals[-1]['goal_id'] if goals else cursor['goals']),
                           'turns':turns[PAGE-1]['id'] if len(turns)>PAGE else (turns[-1]['id'] if turns else cursor['turns'])},
            'has_more':len(goals)>PAGE or len(turns)>PAGE,'excluded':EXCLUDED,'version':VERSION}


def public(plan):
    return {**{k:v for k,v in plan.items() if k not in {'goals','turns'}},
            'targets':{'goals':[r['goal_id'] for r in plan['goals']],
                       'turns':[{'id':r['id'],'chat_id':r['chat_id'],'title':r['chat_title']} for r in plan['turns']]}}


def preview(db, root, scope, cursor):
    chats=Dialogues(root)
    try:return public(inspect(db,chats,scope,cursor))
    finally:chats.close()


def apply(db, root, scope, cursor, token):
    chats=Dialogues(root);ident='cleanup-'+uuid.uuid4().hex;now=time.time()
    try:
        with db.transaction() as tx:
            plan=inspect(db,chats,scope,cursor)
            if token!=plan['token']:raise CoreError('conflict','Cleanup preview changed')
            for row in plan['goals']:
                view=decode(row['view'])
                # Keep dependency IDs and an explicit latch, so removing text cannot
                # make a revoked goal admissible again, even after a later restore.
                view['dependencies']=view.get('dependencies', [{k:f[k] for k in ('id','revision')} for f in view.get('facts',[])])
                view['facts']=[];view['redacted']=True
                tx.execute('UPDATE goal_context SET view=? WHERE goal_id=? AND view=?',(canonical(view),row['goal_id'],row['view']))
                knowledge_outputs.clear(tx,db,row['goal_id'],scope,row['outputs'])
            tx.execute('INSERT INTO knowledge_cleanups VALUES(?,?,?,?,?,?,?,?)',
                       (ident,scope,'pending',len(plan['goals']),0,now,now,None))
            for row in plan['turns']:
                tx.execute('INSERT OR IGNORE INTO knowledge_file_retractions VALUES(?,?,?,?,?,?,?,?)',
                           ('reply:'+row['id'],scope,row['chat_id'],row['id'],hashlib.sha256((row['reply'] or '').encode()).hexdigest(),'pending',None,now))
        try:
            cleared=chats.clear_projections(plan['turns'])
            state='completed';error=None
            files=retry_files(db,root,scope)
            if files['pending'] or files['modified_preserved']:state='partial';error='knowledge_files_remaining'
        except Exception as exc:
            cleared=0;state='partial';error=exc.code if isinstance(exc,CoreError) else 'knowledge_cleanup_failed'
        with db.transaction() as tx:
            tx.execute('UPDATE knowledge_cleanups SET state=?,turns=?,updated=?,error=? WHERE id=?',(state,cleared,time.time(),error,ident))
        return {'receipt':db.one('SELECT * FROM knowledge_cleanups WHERE id=?',(ident,)),**public(plan)}
    finally:chats.close()


def retry_files(db,root,scope):
    sessions=Sessions(root)
    try:
        rows=db.all("SELECT * FROM knowledge_file_retractions WHERE scope=? AND state NOT IN ('cleared','absent') ORDER BY updated LIMIT 200",(scope,))
        for row in rows:
            # Chat redaction must have committed before we remove its projection.
            chats=Dialogues(root)
            try:turn=chats.turn(row['turn_id'])
            finally:chats.close()
            receipt=decode(turn['memory_context']) if turn and turn['memory_context'] else {}
            if not receipt.get('redacted'):continue
            try:state=sessions.retract_reply(row['chat_id'],row['turn_id'],row['sha256']);error=None
            except Exception as exc:state='pending';error=exc.code if isinstance(exc,CoreError) else 'file_unavailable'
            with db.transaction() as tx:
                tx.execute('UPDATE knowledge_file_retractions SET state=?,error=?,updated=? WHERE id=?',(state,error,time.time(),row['id']))
        counts={r['state']:r['n'] for r in db.all('SELECT state,count(*) AS n FROM knowledge_file_retractions WHERE scope=? GROUP BY state',(scope,))}
        artifacts=knowledge_outputs.retry(db,root,scope)
        counts={s:counts.get(s,0)+artifacts[s] for s in artifacts}
        return {s:counts.get(s,0) for s in ('pending','modified_preserved','cleared','absent')}
    finally:sessions.close()
