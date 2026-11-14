"""Bounded local-test policy and durable trial receipts; never an adoption gate."""
import time
from sdk.protocol import CoreError,canonical,decode

POLICY_KEY='lesson_validation_policy'
START='learning.validation_started'
FINISH='learning.validation_finished'
DEFAULT={'enabled':False,'max_trials_24h':4,'revision':1}


class LessonTrials:
    def __init__(self,db):self.db=db

    def policy(self):
        row=self.db.one('SELECT value FROM meta WHERE key=?',(POLICY_KEY,))
        value=decode(row['value']) if row else dict(DEFAULT)
        if (not isinstance(value,dict) or set(value)!=set(DEFAULT) or type(value['enabled']) is not bool
            or type(value['revision']) is not int or value['revision']<1
            or type(value['max_trials_24h']) is not int or not 1<=value['max_trials_24h']<=4):
            raise CoreError('lesson_policy','Unknown local-test policy; no execution')
        return value

    def configure(self,value):
        if (not isinstance(value,dict) or set(value)!=set(DEFAULT) or type(value['enabled']) is not bool
            or type(value['revision']) is not int or type(value['max_trials_24h']) is not int or not 1<=value['max_trials_24h']<=4):
            raise CoreError('lesson_policy','Expected local-test policy, at most four trials per 24 hours')
        with self.db.transaction() as tx:
            old=self.policy()
            if old['revision']!=value['revision']:raise CoreError('conflict','Local-test policy changed')
            value={**value,'revision':old['revision']+1}
            tx.execute('INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(POLICY_KEY,canonical(value)))
            self.db.event(tx,None,'learning.validation_policy',value)
        return value

    def prior(self,key):
        row=self.db.one('SELECT data FROM events WHERE kind=? AND json_extract(data,\'$.key\')=? ORDER BY seq DESC LIMIT 1',(START,key))
        if not row:return None
        value=decode(row['data']);done=self.db.one('SELECT data FROM events WHERE kind=? AND json_extract(data,\'$.key\')=? ORDER BY seq DESC LIMIT 1',(FINISH,key))
        return {**value,'result':decode(done['data']) if done else None,'state':'FINISHED' if done else 'UNKNOWN_OR_RUNNING'}

    def used(self):
        return self.db.one('SELECT count(*) AS n FROM events WHERE kind=? AND occurred>=?',(START,time.time()-86400))['n']

    def reserve(self,task_id,key,body,revision,tx):
        policy=self.policy()
        if not policy['enabled'] or policy['revision']!=revision:raise CoreError('lesson_policy','Local validation disabled or changed')
        if self.prior(key):raise CoreError('lesson_already_tested','A trial already binds this family and verifier; no automatic replay')
        if self.used()>=policy['max_trials_24h']:raise CoreError('lesson_budget','Local-test daily budget exhausted')
        self.db.event(tx,task_id,START,{**body,'key':key,'policy_revision':revision})

    def finish(self,task_id,key,result,tx):
        prior=self.prior(key)
        if not prior:raise CoreError('lesson_trial','Missing trial reservation')
        if prior['result']:raise CoreError('lesson_trial','Trial already completed')
        self.db.event(tx,task_id,FINISH,{'key':key,**result})

    def view(self,candidate):
        if candidate is None:return None
        error=None
        try:policy=self.policy()
        except (CoreError,ValueError,TypeError):
            # Unreadable optional settings must not roll back task assessment.
            policy=dict(DEFAULT);error='invalid_policy'
        rows=self.db.all('SELECT data FROM events WHERE kind=? AND json_extract(data,\'$.family\')=? ORDER BY seq DESC LIMIT 1',(START,candidate['family']))
        trial=self.prior(decode(rows[0]['data'])['key']) if rows else None
        # A successful historical trial cannot turn a withdrawn/currently failed
        # candidate into usable knowledge. It remains a scoped test receipt.
        return {'policy':policy,'policy_error':error,'trials_in_24h':self.used(),'trial':trial,'current_source_eligible':candidate['state']=='CANDIDATE',
            'automatic_promotion':False,'execution_authorized':False,'independent_successes':None}
