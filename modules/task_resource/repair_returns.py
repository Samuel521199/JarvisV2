"""One-shot repair return mandates; execution remains in existing work ledgers."""
import time
from sdk.protocol import CoreError,decode

EVENT='learning.repair_return'
TERMINAL={'CLOSED','FAILED','CANCELLED','REGRESSED','UNSUPPORTED'}

def get(db,ident):
    row=db.one("SELECT data FROM events WHERE kind=? AND json_extract(data,'$.development_id')=? ORDER BY seq DESC LIMIT 1",(EVENT,ident))
    return decode(row['data']) if row else None

def save(db,value,tx):
    prior=get(db,value['development_id'])
    if prior and value.get('revision')!=prior['revision']:
        raise CoreError('repair_return_conflict','Repair mandate changed; stale progress cannot replace it')
    value={**value,'revision':prior['revision']+1 if prior else 1,'updated':time.time()}
    db.event(tx,value['source_task'],EVENT,value)
    return value

def guard(db,ident):
    value=get(db,ident)
    if not value:return None
    if value['status'] in {'FAILED','CANCELLED','REGRESSED','UNSUPPORTED'}:raise CoreError('cancelled','Automatic repair mandate is no longer active')
    if value['deadline']<=time.time():raise CoreError('deadline','Automatic repair mandate expired')
    context=db.one('SELECT enabled FROM goal_context WHERE goal_id=?',(value['source_goal'],))
    if not context or not context['enabled']:raise CoreError('denied','Source learning consent was withdrawn')
    return value['source_task'] if not value.get('child_goal') else None


def guard_task(db,goal):
    row=db.one("SELECT data FROM events WHERE kind=? AND json_extract(data,'$.child_goal')=? ORDER BY seq DESC LIMIT 1",(EVENT,goal))
    if row:
        value=decode(row['data'])
        if value['status'] in TERMINAL-{'CLOSED'} or value['status']!='CLOSED' and value['deadline']<=time.time():
            raise CoreError('cancelled','Automatic return is no longer authorized for execution')
        grant=db.one("SELECT g.revoked FROM tasks t JOIN grants g ON g.id=json_extract(t.body,'$.grant_id') WHERE t.id=?",(value['source_task'],))
        context=db.one('SELECT enabled FROM goal_context WHERE goal_id=?',(value['source_goal'],))
        if not grant or grant['revoked'] or not context or not context['enabled']:
            raise CoreError('denied','Original repair source authority was withdrawn')
