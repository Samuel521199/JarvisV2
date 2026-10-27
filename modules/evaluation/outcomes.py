"""Durable, bounded result reconciliation over the original task ledger.

No model calls, task dispatch, repair, permission changes or knowledge promotion.
All persisted evidence is references/digests, never a second copy of user text.
"""
import hashlib
import time
from contextlib import nullcontext

from adapters.storage.outcome_schema import ensure
from control.paths import child
from control import receipts
from sdk.protocol import CoreError, canonical, contract, decode, digest

VERSION = 'deterministic-1.0.0'
TERMINAL = {'SUCCEEDED', 'FAILED', 'CANCELLED'}
MAX_FILE_BYTES = 262144
MAX_TASK_BYTES = 2 * 1024 * 1024


class Outcomes:
    def __init__(self, db, root, source_check, task_check=lambda task_id:'current'):
        self.db, self.root, self.source_check, self.task_check = db, root, source_check, task_check
        ensure(db)

    def enabled(self):
        row = self.db.one("SELECT value FROM meta WHERE key='outcome_observer_enabled'")
        return not row or row['value'] == '1'

    def configure(self, enabled):
        if type(enabled) is not bool: raise CoreError('invalid_request', 'Expected boolean observer switch')
        with self.db.transaction() as tx:
            tx.execute("INSERT INTO meta VALUES('outcome_observer_enabled',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", ('1' if enabled else '0',))
            self.db.event(tx, None, 'outcome.configured', {'enabled': enabled})
        return {'enabled': enabled}

    def _current(self, task_id):
        row = self.db.one('''SELECT a.*,c.revision FROM outcome_current c
            JOIN outcome_assessments a ON a.id=c.assessment_id WHERE c.task_id=?''', (task_id,))
        return row

    def consume(self, limit=32):
        if type(limit) is not int or not 1 <= limit <= 64:
            raise CoreError('invalid_limit', 'Outcome batch must be 1..64')
        if not self.enabled(): return {'enabled': False, 'processed': 0}
        processed = 0
        started = time.monotonic()
        for _ in range(limit):
            if processed and time.monotonic()-started > .05: break
            with self.db.transaction() as tx:
                cursor = tx.execute("SELECT last_seq FROM outcome_consumers WHERE name='deterministic-v1'").fetchone()[0]
                event = tx.execute('SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT 1', (cursor,)).fetchone()
                if not event: break
                task_id = event['task_id']
                if task_id and event['kind'] in {'task.succeeded', 'task.failed', 'task.cancelled', 'task.cancel_requested'}:
                    self._attempt(tx, task_id)
                # Assessment/current pointer (or durable failure) and checkpoint commit together.
                tx.execute("UPDATE outcome_consumers SET last_seq=? WHERE name='deterministic-v1'", (event['seq'],))
                processed += 1
        cursor = self.db.one("SELECT last_seq FROM outcome_consumers WHERE name='deterministic-v1'")['last_seq']
        newest = self.db.one('SELECT COALESCE(MAX(seq),0) AS seq FROM events')['seq']
        due = self.db.all('SELECT task_id FROM outcome_failures WHERE attempts<3 AND next_retry<=? ORDER BY next_retry LIMIT 2', (time.time(),))
        for row in due:
            if time.monotonic()-started > .05: break
            with self.db.transaction() as tx: self._attempt(tx, row['task_id'])
        return {'enabled': True, 'processed': processed, 'last_seq': cursor, 'lag_events': max(0, newest-cursor)}

    def refresh(self, task_id, *, transaction=None):
        if not self.enabled(): return {'state': 'DISABLED', 'score': None}
        with (nullcontext(transaction) if transaction is not None else self.db.transaction()) as tx:
            state = self._attempt(tx, task_id)
            if state: return state
            current = self._current(task_id)
            return decode(current['body']) if current else {'state': 'PENDING', 'score': None}

    def cached(self, task_id):
        if not self.enabled(): return {'state': 'DISABLED', 'score': None}
        current = self._current(task_id)
        return {'state': 'STALE' if current else 'PENDING', 'score': None,
                'assessment_id': current['id'] if current else ''}

    def retry(self, task_id):
        """Explicit retry only resets this observer's bounded failure counter."""
        with self.db.transaction() as tx:
            tx.execute('DELETE FROM outcome_failures WHERE task_id=?', (task_id,))
        return self.refresh(task_id)

    def history(self, task_id):
        current = self._current(task_id)
        return {'current_id':current['id'] if current else '', 'limit':20,
                'items':[decode(r['body']) for r in self.db.all(
                    'SELECT body FROM outcome_assessments WHERE task_id=? ORDER BY created DESC,id DESC LIMIT 20', (task_id,))],
                'note':'Historical assessments are not current authorization or quality guarantees.'}

    def _attempt(self, tx, task_id):
        task = self.db.one('SELECT * FROM tasks WHERE id=?', (task_id,))
        if not task or task['status'] not in TERMINAL:
            return {'state': 'PENDING', 'score': None}
        failed = self.db.one('SELECT * FROM outcome_failures WHERE task_id=?', (task_id,))
        if failed and (failed['attempts'] >= 3 or failed['next_retry'] > time.time()):
            return {'state': 'UNAVAILABLE', 'score': None, 'error': failed['error'], 'attempts': failed['attempts']}
        # A checker bug must not commit half a projection or erase the original result.
        tx.execute('SAVEPOINT outcome_check')
        try:
            self._assess(tx, task)
            tx.execute('DELETE FROM outcome_failures WHERE task_id=?', (task_id,))
            tx.execute('RELEASE outcome_check')
        except Exception:
            tx.execute('ROLLBACK TO outcome_check'); tx.execute('RELEASE outcome_check')
            attempts = (failed['attempts'] if failed else 0) + 1
            tx.execute('''INSERT INTO outcome_failures VALUES(?,?,?,?) ON CONFLICT(task_id)
                DO UPDATE SET attempts=excluded.attempts,error=excluded.error,next_retry=excluded.next_retry''',
                (task_id, attempts, 'outcome_check_failed', time.time()+5*attempts))
            return {'state': 'UNAVAILABLE', 'score': None, 'error': 'outcome_check_failed', 'attempts': attempts}

    def _artifact(self, task, action, args, result, remaining):
        if result.get('redacted') or not isinstance(args.get('content'), str):
            return {'status': 'invalid', 'reason': 'source_redacted', 'digest': ''}, 0
        expected_path = f"artifacts/{task['id']}/{action['id']}/{args.get('name', '')}"
        if result.get('relative_path') != expected_path:
            return {'status': 'failed', 'reason': 'artifact_binding_changed', 'digest': ''}, 0
        try:
            path = child(self.root, expected_path)
            size = path.stat().st_size
            if size > MAX_FILE_BYTES or size > remaining:
                return {'status': 'unknown', 'reason': 'inspection_budget', 'digest': ''}, 0
            with path.open('rb') as stream: raw = stream.read(min(MAX_FILE_BYTES, remaining)+1)
            if len(raw) > min(MAX_FILE_BYTES, remaining):
                return {'status': 'unknown', 'reason': 'inspection_budget', 'digest': ''}, len(raw)
            actual = hashlib.sha256(raw).hexdigest()
            matched = (actual == result.get('sha256') == hashlib.sha256(args['content'].encode('utf-8')).hexdigest()
                       and len(raw) == result.get('bytes'))
            return {'status': 'passed' if matched else 'failed', 'reason': 'artifact_intact' if matched else 'artifact_changed', 'digest': actual}, len(raw)
        except (OSError, CoreError):
            return {'status': 'failed', 'reason': 'artifact_unavailable', 'digest': ''}, 0

    def _assess(self, tx, task):
        body = decode(task['body'])
        actions = self.db.all('SELECT * FROM actions WHERE task_id=? ORDER BY rowid', (task['id'],))
        goal = self.db.one('SELECT * FROM goal_plans WHERE task_id=?', (task['id'],))
        # The port reuses current source revocations; it cannot authorize an action.
        source = self.source_check(goal['id']) if goal else 'current'
        dependency = self.task_check(task['id'])
        if dependency != 'current': source = dependency
        if goal:
            admitted = self.db.one("SELECT data FROM events WHERE task_id=? AND kind='goal.approved' ORDER BY seq DESC LIMIT 1", (task['id'],))
            if admitted:
                frozen = decode(admitted['data'])
                if goal['revision'] != frozen['revision']+1 or digest(decode(goal['proposal'])) != frozen['proposal_digest']:
                    source = 'invalid'
        criteria, evidence = [], []
        def criterion(ident, status, reason, refs):
            criteria.append({'id': ident, 'status': status, 'reason': reason, 'evidence_refs': refs})
        criterion('execution', 'passed' if task['status']=='SUCCEEDED' and not task['cancel'] else 'failed',
                  'execution_state', ['task:'+task['id']])
        criterion('source', 'passed' if source=='current' else 'invalid' if source=='invalid' else 'unknown',
                  'source_'+source, ['goal:'+goal['id']] if goal else [])
        by_step = {a['step_id']: a for a in actions}
        remaining = MAX_TASK_BYTES
        for step in body['steps']:
            action = by_step.get(step['step_id']); ref = 'action:'+action['id'] if action else 'step:'+step['step_id']
            criterion('receipt:'+step['step_id'], 'passed' if action and action['status']=='CONFIRMED' else 'failed',
                      'confirmed_action' if action and action['status']=='CONFIRMED' else 'missing_confirmation', [ref])
            if not action or action['status']!='CONFIRMED': continue
            args, result = decode(action['arguments']), decode(action['result'])
            evidence.append({'ref': ref, 'digest': digest(result)})
            if result.get('redacted'):
                criterion('result:'+step['step_id'], 'invalid', 'source_redacted', [ref]); continue
            cap = step['capability']
            if cap == 'artifact.write.v1':
                probe, used = self._artifact(task, action, args, result, remaining); remaining -= used
                criterion('artifact:'+step['step_id'], probe['status'], probe['reason'], [ref])
                evidence.append({'ref': 'artifact:'+action['id'], 'digest': probe['digest']})
            elif cap == 'text.analyze.v1':
                text = args.get('text')
                expected = {'characters': len(text), 'lines': len(text.splitlines()),
                            'words': len(text.split()), 'utf8_bytes': len(text.encode('utf-8'))} if isinstance(text, str) else None
                criterion('result:'+step['step_id'], 'passed' if result==expected else 'failed', 'text_statistics', [ref])
            else:
                try:
                    recorded = receipts.read(self.root, receipts.binding(task['id'], action['id'], decode(task['bindings'])[cap], args))
                    matched = recorded == result
                except (CoreError, OSError): matched = False
                criterion('integrity:'+step['step_id'], 'passed' if matched else 'failed', 'computation_receipt', [ref])
                criterion('result:'+step['step_id'], 'failed' if result.get('is_error') else 'unknown',
                          'tool_reported_error' if result.get('is_error') else 'semantic_verifier_missing', [ref])
        # Natural-language intent and recipient acceptance cannot be inferred from exit status.
        criterion('goal_quality', 'unknown', 'goal_verifier_missing', [])
        criterion('recipient_delivery', 'unknown', 'recipient_receipt_missing', [])
        binding = {'task_revision': task['revision'], 'task_digest': digest(body), 'bindings': task['bindings'],
                   'actions': [{k:a[k] for k in ('id','digest','status','arguments','result')} for a in actions],
                   'goal': {k:goal[k] for k in ('id','revision','request','proposal','cancel')} if goal else None,
                   'source': source, 'criteria': criteria, 'evidence': evidence, 'evaluator': VERSION}
        fingerprint = digest(binding)
        current = self._current(task['id'])
        if current and current['fingerprint']==fingerprint: return
        statuses = [c['status'] for c in criteria]
        state = 'INVALIDATED' if 'invalid' in statuses else 'ISSUES' if 'failed' in statuses else 'PARTIAL'
        revision = current['revision']+1 if current else 1
        ident = 'outcome-'+digest([task['id'], revision, fingerprint])[:32]
        result = {'schema':'jarvis.outcome-assessment.v1', 'id':ident, 'task_id':task['id'], 'fingerprint':fingerprint,
                  'task_revision':task['revision'], 'goal_id':goal['id'] if goal else '', 'goal_revision':goal['revision'] if goal else 0,
                  'evaluator':VERSION, 'execution_status':task['status'], 'state':state, 'score':None,
                  'criteria':criteria, 'evidence':evidence, 'coverage':{'total':len(criteria),
                    'known':sum(s in {'passed','failed'} for s in statuses), 'passed':statuses.count('passed')},
                  'source_status':source, 'assessed_at':time.time(), 'supersedes':current['id'] if current else ''}
        contract('outcome-assessment', result)
        tx.execute('INSERT INTO outcome_assessments VALUES(?,?,?,?,?)', (ident,task['id'],fingerprint,canonical(result),result['assessed_at']))
        tx.execute('''INSERT INTO outcome_current VALUES(?,?,?) ON CONFLICT(task_id)
            DO UPDATE SET assessment_id=excluded.assessment_id,revision=excluded.revision''', (task['id'],ident,revision))
