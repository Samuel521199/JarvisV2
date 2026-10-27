"""Conditional method references, never cached answers or unrestricted instructions."""
import time
from adapters.storage.completion_schema import ensure
from sdk.protocol import CoreError,canonical,decode,digest


class Episodes:
    def __init__(self,db): self.db=db;ensure(db)

    def record(self, task, completion, eligible, tx):
        old=self.db.one('SELECT * FROM experience_sources WHERE task_id=?',(task['id'],))
        good=completion['state'] in {'SATISFIED','VERIFIED','ACCEPTED'}
        use=self.db.one('SELECT * FROM experience_uses WHERE task_id=?',(task['id'],))
        if use and completion['state']=='NEEDS_CORRECTION':
            tx.execute("UPDATE experience_methods SET status='QUARANTINED',revision=revision+1,review_after=? WHERE id=? AND status='ACTIVE'",(time.time(),use['method_id']))
        if old and completion['state'] in {'NEEDS_CORRECTION','INVALIDATED','CANCELLED'}:
            tx.execute('UPDATE experience_sources SET state=? WHERE task_id=?',(completion['state'],task['id']))
            tx.execute("UPDATE experience_methods SET status='QUARANTINED',revision=revision+1,review_after=? WHERE id=? AND status='ACTIVE'",(time.time(),old['method_id']))
            return
        if not eligible or not good: return
        binding=canonical(task['bindings']);method='method-'+digest(['personal','text-report-v1',binding])[:32]
        tx.execute('INSERT OR IGNORE INTO experience_methods(id,scope,recipe,bindings,status,revision,created,expires) VALUES(?,?,?,?,?,1,?,?)',
                   (method,'personal','text-report-v1',binding,'ACTIVE',time.time(),time.time()+30*86400))
        tx.execute('''INSERT INTO experience_sources VALUES(?,?,?,?,?) ON CONFLICT(task_id)
            DO UPDATE SET fingerprint=excluded.fingerprint,state=excluded.state''',
            (task['id'],method,completion['fingerprint'],digest(task['body']['steps'][0]['arguments']),completion['state']))

    def source(self, task_id):
        return self.db.one('''SELECT m.*,s.fingerprint,s.state AS source_state FROM experience_sources s
            JOIN experience_methods m ON m.id=s.method_id WHERE s.task_id=?''',(task_id,))

    def use(self, task_id, source_id, method, tx):
        if task_id==source_id: raise CoreError('experience_cycle','Cannot depend on the same task')
        prior=self.db.one('SELECT * FROM experience_uses WHERE task_id=?',(task_id,))
        if prior and (prior['source_task']!=source_id or prior['method_id']!=method['id'] or prior['method_revision']!=method['revision']):
            raise CoreError('conflict','Task already uses different evidence')
        tx.execute('INSERT OR IGNORE INTO experience_uses VALUES(?,?,?,?,?,?)',
                   (task_id,method['id'],method['revision'],source_id,method['fingerprint'],time.time()))

    def check_use(self, task_id):
        use=self.db.one('SELECT * FROM experience_uses WHERE task_id=?',(task_id,))
        if not use:return None
        method=self.source(use['source_task'])
        if (not method or method['status']!='ACTIVE' or method['revision']!=use['method_revision']
                or method['expires']<=time.time() or method['fingerprint']!=use['source_fingerprint']
                or method['source_state'] not in {'SATISFIED','VERIFIED','ACCEPTED'}):
            raise CoreError('experience_changed','Referenced method evidence changed; review before continuing')
        return use
