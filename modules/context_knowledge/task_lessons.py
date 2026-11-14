"""Task-derived method candidates in the existing audit ledger, never active memory.

Only structured references and hashes are retained. A shared procedure or new
input is not independent proof of quality; historical observations are not live
validation. The normal completion/source checks must precede each current view.
"""
from sdk.protocol import decode,digest

VERSION='task-lesson-1'
EVENT='learning.candidate_observed'
BAD={'NEEDS_CORRECTION'}


def describe(task,plan,context,completion,source_error=None,*,purpose=None):
    """Extract a bounded procedure shape without storing inputs, answers or notes."""
    if not plan or not context:return None
    steps=task['body']['steps'];positions={s['step_id']:i for i,s in enumerate(steps)}
    procedure=[]
    for index,step in enumerate(steps):
        arguments={}
        for key,value in step.get('arguments',{}).items():
            arguments[key]={'role':'current_input'} if index==0 and key=='text' and value==plan['request']['input_text'] else {'role':'bound_literal','digest':digest(value)}
        procedure.append({'capability':step['capability'],'from_step':positions.get(step.get('input_from')),
            'arguments':arguments,'binding_digest':digest(task['bindings'].get(step['capability']))})
    # Unknown purposes are not generalized across differently worded goals.
    applicability={'purpose':purpose} if purpose else {'goal_digest':digest(plan['request']['goal'])}
    scope=context['scope']
    family=digest({'version':VERSION,'scope':scope,'procedure':procedure,'applicability':applicability})
    if not source_error and completion['state'] in {'INVALIDATED','CANCELLED'}:source_error='completion_not_current'
    state=('WITHDRAWN' if source_error else 'COUNTEREVIDENCE' if completion['state'] in BAD
        else 'CANDIDATE' if completion['evidence_ready'] and completion['requirement_coverage']['complete']
        else 'INCOMPLETE')
    return {'version':VERSION,'task_id':task['id'],'goal_id':plan['id'],'scope':scope,'family':family,
        'procedure':procedure,'applicability':applicability,'input_digest':digest(plan['request']['input_text']),
        'fingerprint':completion['fingerprint'],'completion_state':completion['state'],'state':state,
        'source_error':source_error,'condition_score':completion['condition_score'],
        'requirements_complete':completion['requirement_coverage']['complete']}


class TaskLessons:
    def __init__(self,db):self.db=db

    def record(self,task_id,value,tx):
        prior=self.db.one('SELECT data FROM events WHERE task_id=? AND kind=? ORDER BY seq DESC LIMIT 1',(task_id,EVENT))
        # Memory opt-out must not start a new learning record. Existing records
        # become unusable in the projection, and receive a withdrawal tombstone.
        if value is None or not prior and value['state']=='WITHDRAWN':return None
        if not prior or decode(prior['data'])!=value:self.db.event(tx,task_id,EVENT,value)
        return value

    def projection(self,value):
        if value is None:return None
        # A bounded history view, not a global support counter or promotion gate.
        history=self.db.all('SELECT task_id,data FROM events WHERE kind=? AND json_extract(data,\'$.scope\')=? '
            'ORDER BY seq DESC LIMIT 201',(EVENT,value['scope']))
        latest={}
        for row in history[:200]:
            if row['task_id'] not in latest:latest[row['task_id']]=decode(row['data'])
        related=[row for row in latest.values() if row.get('version')==VERSION and row.get('family')==value['family']]
        states={state:sum(r['state']==state for r in related) for state in ('CANDIDATE','COUNTEREVIDENCE','INCOMPLETE','WITHDRAWN')}
        return {**value,'history':{'observations':len(related),'distinct_inputs':len({r['input_digest'] for r in related}),
            'states':states,'event_window':200,'window_truncated':len(history)>200,'live_revalidated':False},
            'independent_successes':None,'causal_contribution':None,'automatic_promotion':False,
            'execution_authorized':False,'retrievable_as_memory':False,
            'next_step':'restore_current_sources' if value['state']=='WITHDRAWN'
                else 'resolve_counterevidence' if value['state']=='COUNTEREVIDENCE' or states['COUNTEREVIDENCE']
                else 'complete_acceptance' if value['state']=='INCOMPLETE'
                else 'review_history_window' if len(history)>200 else 'independent_validation'}
