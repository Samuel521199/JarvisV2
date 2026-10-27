"""Frozen acceptance and owner feedback; never edits action facts or dispatches."""
import time
from contextlib import nullcontext
from adapters.storage.completion_schema import ensure
from modules.task_resource import coverage, quote_checks, quote_request, source_checks, change_checks, inheritance_checks, recovery_checks
from sdk.protocol import CoreError, canonical, decode, digest


def text_report(body):
    steps=body['steps']
    return (len(steps)==2 and steps[0]['capability']=='text.analyze.v1'
            and steps[1]['capability']=='artifact.write.v1' and steps[1].get('input_from')==steps[0]['step_id'])


class Completion:
    def __init__(self, db, source_review=None, change_review=None, rework_review=None, recovery_review=None):
        self.db=db;self.source_review=source_review;self.change_review=change_review;self.rework_review=rework_review;self.recovery_review=recovery_review;ensure(db)

    def default(self, task_id, body, tx):
        if not text_report(body): return
        rules={'coverage':'recipe', 'criteria':[{'id':'statistics','step_id':body['steps'][0]['step_id'],
                                                'check':'text_statistics','expected':''}]}
        tx.execute('INSERT INTO task_acceptance VALUES(?,1,?,?)', (task_id,canonical(rules),time.time()))

    def criteria(self, task_id):
        row=self.db.one('SELECT * FROM task_acceptance WHERE task_id=?',(task_id,))
        return {'revision':row['revision'],'rules':decode(row['body'])} if row else {'revision':0,'rules':None}

    def configure(self, task_id, revision, rules, *, transaction=None):
        if (type(revision) is not int or not isinstance(rules,dict) or set(rules) not in ({'coverage','criteria'},{'coverage','criteria','requirements'})
                or not isinstance(rules['coverage'],str) or rules['coverage'] not in {'recipe','complete'} or not isinstance(rules['criteria'],list)
                or not 1<=len(rules['criteria'])<=16):
            raise CoreError('acceptance_invalid','Expected bounded, declared acceptance conditions')
        with (nullcontext(transaction) if transaction is not None else self.db.transaction()) as tx:
            task=self.db.one('SELECT * FROM tasks WHERE id=?',(task_id,))
            if not task: raise CoreError('not_found','Task missing')
            if task['status']!='READY' or task['cancel'] or self.db.one('SELECT 1 FROM actions WHERE task_id=?',(task_id,)):
                raise CoreError('acceptance_frozen','Acceptance is frozen before the first action')
            old=self.criteria(task_id)
            if old['revision']!=revision: raise CoreError('conflict','Acceptance changed')
            steps={s['step_id']:s for s in decode(task['body'])['steps']};seen=set()
            for rule in rules['criteria']:
                if (not isinstance(rule,dict) or set(rule)!={'id','step_id','check','expected'}
                        or any(not isinstance(v,str) for v in rule.values())
                        or not 1<=len(rule['id'])<=80 or rule['id'] in seen or rule['step_id'] not in steps
                        or rule['check'] not in {'text_statistics','text_equals','text_contains','quote_selection','quote_request','quote_sources','quote_changes','quote_rework','quote_recovery'} or len(rule['expected'])>12000):
                    raise CoreError('acceptance_invalid','Invalid or duplicated condition')
                seen.add(rule['id']);cap=steps[rule['step_id']]['capability']
                if rule['check']=='text_statistics' and (cap!='text.analyze.v1' or rule['expected']):
                    raise CoreError('acceptance_invalid','Statistics verifier requires the statistics capability')
                if rule['check']!='text_statistics' and (not cap.startswith('plugin.') or rule['check']=='text_contains' and not rule['expected']):
                    raise CoreError('acceptance_invalid','Text verifier requires a bounded pure text tool')
                if rule['check']=='quote_selection': quote_checks.bound_source(decode(task['body']),rule)
                if rule['check']=='quote_request':
                    linked=self.db.one('SELECT request FROM goal_plans WHERE task_id=?',(task_id,))
                    if linked and decode(linked['request'])['goal']!=decode(task['body'])['goal']:
                        raise CoreError('acceptance_invalid','Request review must include the untruncated goal')
                    quote_request.bound_review(decode(task['body']),rule)
                if rule['check'] in {'quote_sources','quote_changes','quote_rework','quote_recovery'}:
                    port=self.recovery_review if rule['check']=='quote_recovery' else self.rework_review if rule['check']=='quote_rework' else self.change_review if rule['check']=='quote_changes' else self.source_review
                    if port is None:raise CoreError('acceptance_invalid','Source review port is required')
                    body=decode(task['body'])
                    source_checks.validate(body,rule,port(task_id,body))
            coverage.validate(rules)
            tx.execute('''INSERT INTO task_acceptance VALUES(?,?,?,?) ON CONFLICT(task_id)
                DO UPDATE SET revision=excluded.revision,body=excluded.body,created=excluded.created''',
                (task_id,revision+1,canonical(rules),time.time()))
            self.db.event(tx,task_id,'acceptance.configured',{'revision':revision+1,'digest':digest(rules)})
        return self.criteria(task_id)

    def evaluate(self, task_id, outcome, tx):
        task=self.db.one('SELECT * FROM tasks WHERE id=?',(task_id,))
        if not task: raise CoreError('not_found','Task missing')
        accepted=self.criteria(task_id)
        checks=[]; rules=accepted['rules']; actual={a['step_id']:a for a in self.db.all('SELECT * FROM actions WHERE task_id=?',(task_id,))}
        for rule in rules['criteria'] if rules else []:
            action=actual.get(rule['step_id']);state='unknown';evidence={}
            if action and action['status']=='CONFIRMED':
                result=decode(action['result']);args=decode(action['arguments'])
                if result.get('redacted'): state='invalid'
                elif rule['check']=='text_statistics':
                    item=next((c for c in outcome.get('criteria',[]) if c['id']=='result:'+rule['step_id']),None)
                    state=item['status'] if item else 'unknown'
                elif rule['check'] in {'quote_selection','quote_request'}:
                    verifier=quote_request if rule['check']=='quote_request' else quote_checks
                    evidence=verifier.verify(decode(task['body']),rule,result.get('text'))
                    state=evidence['status']
                elif rule['check'] in {'quote_sources','quote_changes','quote_rework','quote_recovery'}:
                    body=decode(task['body'])
                    port=self.recovery_review if rule['check']=='quote_recovery' else self.rework_review if rule['check']=='quote_rework' else self.change_review if rule['check']=='quote_changes' else self.source_review
                    verifier=recovery_checks if rule['check']=='quote_recovery' else inheritance_checks if rule['check']=='quote_rework' else change_checks if rule['check']=='quote_changes' else source_checks
                    try:review=port(task_id,body) if port else None
                    except CoreError:review=None
                    evidence=verifier.verify(body,rule,result.get('text'),review)
                    state=evidence['status']
                elif isinstance(result.get('text'),str):
                    state='passed' if (result['text']==rule['expected'] if rule['check']=='text_equals' else rule['expected'] in result['text']) else 'failed'
            checks.append({'id':rule['id'],'step_id':rule['step_id'],'status':state,**evidence})
        coverage_result=coverage.evaluate(rules,checks)
        fingerprint=digest({'version':'completion-1.1.0','outcome':outcome.get('id'), 'acceptance':accepted,
                            'task_revision':task['revision'],'checks':checks,'coverage':coverage_result})
        feedback=self.db.one('SELECT * FROM completion_feedback WHERE task_id=? ORDER BY created DESC,rowid DESC LIMIT 1',(task_id,))
        covered={r['step_id'] for r in rules['criteria']} if rules else set()
        unresolved=[c for c in outcome.get('criteria',[]) if c['status']=='unknown' and c['id'] not in {'goal_quality','recipient_delivery'}
                    and not (c['id'].startswith('result:') and c['id'][7:] in covered)]
        if task['cancel'] or task['status']=='CANCELLED': state='CANCELLED'
        elif task['status'] not in {'SUCCEEDED','FAILED'}: state='WAITING'
        elif outcome.get('state')=='INVALIDATED' or any(c['status']=='invalid' for c in checks): state='INVALIDATED'
        elif outcome.get('state') in {'UNAVAILABLE','DISABLED','PENDING','STALE'}: state='UNAVAILABLE'
        elif outcome.get('state')=='ISSUES' or any(c['status']=='failed' for c in checks): state='NEEDS_CORRECTION'
        elif not rules: state='UNSPECIFIED'
        elif any(c['status']!='passed' for c in checks) or unresolved: state='WAITING_EVIDENCE'
        else: state='VERIFIED' if coverage_result['complete'] else 'SATISFIED'
        evidence_ready=state in {'VERIFIED','SATISFIED'}
        if feedback and feedback['kind']=='reject' and state!='CANCELLED': state='NEEDS_CORRECTION'
        elif feedback and feedback['kind']=='accept' and feedback['fingerprint']==fingerprint and state in {'VERIFIED','SATISFIED'}: state='ACCEPTED'
        if state not in {'VERIFIED','SATISFIED','ACCEPTED'}:
            coverage_result={**coverage_result,'complete':False,'state':'INVALIDATED' if state=='INVALIDATED' else 'INCOMPLETE'}
        known=sum(c['status'] in {'passed','failed'} for c in checks); passed=sum(c['status']=='passed' for c in checks)
        result={'version':'completion-1.1.0','task_id':task_id,'state':state,'fingerprint':fingerprint,
                'acceptance':accepted,'checks':checks,'condition_score':100*passed/len(checks) if checks and known==len(checks) else None,
                'score_scope':'declared_conditions_only','outcome_id':outcome.get('id'),
                'requirement_coverage':coverage_result,
                'evidence_ready':evidence_ready,
                'feedback':{k:feedback[k] for k in ('id','kind','note','fingerprint','created')} if feedback else None}
        previous=tx.execute('SELECT body,checked FROM task_completion WHERE task_id=?',(task_id,)).fetchone()
        if previous and previous['body']!=canonical(result):
            old=decode(previous['body'])
            tx.execute('INSERT OR IGNORE INTO completion_history VALUES(?,?,?,?)',
                       (task_id,digest(old),previous['body'],previous['checked']))
        tx.execute('''INSERT INTO task_completion VALUES(?,?,?) ON CONFLICT(task_id)
            DO UPDATE SET body=excluded.body,checked=excluded.checked''',(task_id,canonical(result),time.time()))
        return result

    def feedback(self, task_id, request_id, fingerprint, kind, note, current, tx):
        if (not isinstance(request_id,str) or not 1<=len(request_id)<=80 or not isinstance(fingerprint,str)
                or len(fingerprint)!=64 or not isinstance(kind,str) or kind not in {'accept','reject','withdraw'} or not isinstance(note,str) or len(note)>2000
                or kind in {'reject','withdraw'} and not note.strip()):
            raise CoreError('feedback_invalid','Expected bounded feedback with an evidence reference')
        body={'fingerprint':fingerprint,'kind':kind,'note':note};key=digest(body)
        prior=self.db.one('SELECT * FROM completion_feedback WHERE task_id=? AND request_id=?',(task_id,request_id))
        if prior:
            if prior['digest']!=key: raise CoreError('conflict','Feedback request changed')
            return prior['id']
        if current['fingerprint']!=fingerprint: raise CoreError('conflict','Evidence changed; review the current result')
        if kind=='withdraw' and (not current['feedback'] or current['feedback']['kind']!='reject'):
            raise CoreError('feedback_invalid','Only an existing correction can be withdrawn')
        # A later acceptance can resolve a rejection, but cannot bless failed checks.
        if kind=='accept' and not current['evidence_ready']:
            raise CoreError('feedback_invalid','Cannot accept unverified evidence')
        ident='feedback-'+digest([task_id,request_id])[:32]
        tx.execute('INSERT INTO completion_feedback VALUES(?,?,?,?,?,?,?,?)',
                   (ident,task_id,request_id,key,fingerprint,kind,note,time.time()))
        self.db.event(tx,task_id,'completion.feedback',{'id':ident,'kind':kind})
        return ident
