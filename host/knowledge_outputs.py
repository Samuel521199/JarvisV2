"""Revocation of terminal goal outputs, preserving original requests and receipts."""
import hashlib
import re
import time

from control.paths import child, reject_links
from modules.workspace.sessions import Sessions, component
from sdk.protocol import CoreError, canonical, decode

REDACTED={'text':'正文已按要求清理，原执行回执保留。','redacted':True}


def inspect(db,goal_id):
    plan=db.one('SELECT * FROM goal_plans WHERE id=?',(goal_id,))
    if not plan:return {'busy':False,'plan':None,'task':None,'actions':[],'calls':[]}
    task=db.one('SELECT * FROM tasks WHERE id=?',(plan['task_id'],)) if plan['task_id'] else None
    actions=db.all('SELECT * FROM actions WHERE task_id=? ORDER BY id',(task['id'],)) if task else []
    keys=[goal_id+suffix+('-g'+str(g) if g else '') for g in range(plan['generation']+1) for suffix in ('','-return')]
    calls=db.all('SELECT id,run_id,status,result FROM model_calls WHERE run_id IN ('+','.join('?' for _ in keys)+') ORDER BY id',keys)
    growth=db.one('SELECT status FROM goal_growth WHERE goal_id=?',(goal_id,))
    busy=(plan['status']=='PLANNING' or (task and task['status'] not in {'SUCCEEDED','FAILED','CANCELLED'})
          or any(a['status'] in {'DISPATCHING','UNKNOWN'} for a in actions) or any(c['status']=='DISPATCHING' for c in calls)
          or (growth and growth['status'] not in {'REJOINED','CANCELLED'}))
    return {'busy':bool(busy),'plan':plan,'task':task,'actions':actions,'calls':calls}


def clear(tx,db,goal_id,scope,outputs):
    if not outputs['plan']:return
    plan=outputs['plan'];task=outputs['task'];now=time.time()
    link=db.one('SELECT chat_id FROM chat_goals WHERE goal_id=?',(goal_id,))
    for a in outputs['actions']:
        result=decode(a['result']) if a['result'] else {}
        if a['capability']=='artifact.write.v1' and a['status']=='CONFIRMED' and not result.get('redacted'):
            relative=result.get('relative_path','');sha=result.get('sha256','')
            prefix='artifacts/'+component(task['id'])+'/'+component(a['id'])+'/'
            if not relative.startswith(prefix) or '/' in relative[len(prefix):] or not re.fullmatch('[0-9a-f]{64}',sha):
                raise CoreError('knowledge_output_invalid','Artifact provenance is incomplete; preserve and inspect it')
            tx.execute('INSERT OR IGNORE INTO knowledge_artifact_retractions VALUES(?,?,?,?,?,?,?,?)',
                       (a['id'],scope,link['chat_id'] if link else None,relative,sha,'pending',None,now))
        tx.execute('UPDATE actions SET arguments=?,result=?,error=? WHERE id=?',
                   (canonical({'redacted':True}),canonical(REDACTED),'memory_projection_redacted',a['id']))
    if task:
        body=decode(task['body']);body.update(goal='任务正文已清理',steps=[],redacted=True)
        tx.execute('UPDATE tasks SET body=?,cancel=1,revision=revision+1 WHERE id=?',(canonical(body),task['id']))
    for call in outputs['calls']:
        tx.execute('UPDATE model_calls SET result=?,error=? WHERE id=?',(canonical(REDACTED),'memory_projection_redacted',call['id']))
    context=db.one('SELECT history FROM goal_context WHERE goal_id=?',(goal_id,))
    history=decode(context['history']) if context else []
    for version in history:version['proposal']=None;version['redacted']=True
    tx.execute('UPDATE goal_context SET history=? WHERE goal_id=?',(canonical(history),goal_id))
    tx.execute("UPDATE goal_plans SET proposal=NULL,cancel=1,revision=revision+1,error='memory_projection_redacted' WHERE id=?",(goal_id,))


def retry(db,root,scope):
    sessions=Sessions(root)
    try:
        for r in db.all("SELECT * FROM knowledge_artifact_retractions WHERE scope=? AND state NOT IN ('cleared','absent') ORDER BY updated LIMIT 200",(scope,)):
            state='pending';error=None
            try:
                path=child(root,r['relative']);original='absent'
                if path.exists():
                    if not path.is_file() or path.stat().st_size>2000000 or hashlib.sha256(path.read_bytes()).hexdigest()!=r['sha256']:
                        original='modified_preserved'
                    else:reject_links(path);path.unlink();original='cleared'
                copy=sessions.retract_projection(r['chat_id'],r['relative'],r['sha256']) if r['chat_id'] else 'absent'
                state='modified_preserved' if 'modified_preserved' in (original,copy) else ('cleared' if 'cleared' in (original,copy) else 'absent')
            except Exception as exc:error=exc.code if isinstance(exc,CoreError) else 'file_unavailable'
            with db.transaction() as tx:tx.execute('UPDATE knowledge_artifact_retractions SET state=?,error=?,updated=? WHERE id=?',(state,error,time.time(),r['id']))
        counts={r['state']:r['n'] for r in db.all('SELECT state,count(*) AS n FROM knowledge_artifact_retractions WHERE scope=? GROUP BY state',(scope,))}
        return {s:counts.get(s,0) for s in ('pending','modified_preserved','cleared','absent')}
    finally:sessions.close()
