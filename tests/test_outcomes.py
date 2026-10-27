"""Result evidence must not become another executor or a fabricated quality score."""
import concurrent.futures
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_core as base
from test_core import task
from host.core import Core
from host.outcomes import observe, service
from host.settings_operations import command
from host.work_status import snapshot
from modules.evaluation.outcomes import Outcomes, MAX_FILE_BYTES
from sdk.protocol import CoreError, canonical, contract, decode, digest


class OutcomeCase(unittest.TestCase):
    setUp = base.CoreCase.setUp
    tearDown = base.CoreCase.tearDown

    def complete(self, key='outcome', artifact=True):
        ident = self.core.tasks.submit(task(key, artifact=artifact))
        self.core.run_task(ident)
        return ident

    def count(self, ident):
        return self.core.db.one('SELECT COUNT(*) AS n FROM outcome_assessments WHERE task_id=?', (ident,))['n']

    def link_goal(self, ident):
        proposal = {'test':'approved expectation'}
        with self.core.db.transaction() as tx:
            tx.execute('''INSERT INTO goal_plans(id,request_id,digest,request,catalog,routes,proposal,status,revision,
                task_id,created,deadline) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('goal-outcome','goal-outcome','fixture','{}','[]','[]',canonical(proposal),'ACCEPTED',2,ident,time.time(),time.time()+600))
            self.core.db.event(tx, ident, 'goal.approved', {'goal_id':'goal-outcome','revision':1,'proposal_digest':digest(proposal)})

    def artifact(self, ident):
        result = decode(self.core.tasks.actions(ident)[-1]['result'])
        return self.root / result['relative_path']

    def drain(self, observer=None):
        observer = observer or service(self.core)
        for _ in range(20):
            result = observer.consume(64)
            if not result.get('lag_events'): return result
        self.fail('Consumer did not drain its bounded fixture')

    def test_deterministic_evidence_is_persisted_without_fabricating_goal_score(self):
        ident = self.complete()
        result = observe(self.core, ident)
        contract('outcome-assessment', result)
        self.assertEqual(result['state'], 'PARTIAL')
        self.assertIsNone(result['score'])
        self.assertGreater(result['coverage']['known'], 0)
        self.assertLess(result['coverage']['known'], result['coverage']['total'])
        checks = {c['id']: c['status'] for c in result['criteria']}
        self.assertEqual(checks['artifact:deliver'], 'passed')
        self.assertEqual(checks['result:analyze'], 'passed')
        self.assertEqual(checks['goal_quality'], 'unknown')
        self.assertEqual(checks['recipient_delivery'], 'unknown')
        raw = self.core.db.one('SELECT body FROM outcome_assessments WHERE id=?', (result['id'],))['body']
        self.assertNotIn('hello world', raw)

    def test_duplicate_terminal_events_commit_one_current_assessment_and_no_effect(self):
        ident = self.complete(); before = self.core.tasks.actions(ident)
        stamp = self.artifact(ident).stat().st_mtime_ns
        with self.core.db.transaction() as tx:
            for _ in range(5): self.core.db.event(tx, ident, 'task.succeeded', {})
        self.drain()
        self.assertEqual(self.count(ident), 1)
        self.assertEqual(self.core.tasks.actions(ident), before)
        self.assertEqual(self.artifact(ident).stat().st_mtime_ns, stamp)

    def test_restart_after_terminal_commit_only_resumes_observation(self):
        service(self.core).configure(False)
        ident = self.complete(); actions = self.core.tasks.actions(ident)
        self.assertEqual(self.count(ident), 0)
        service(self.core).configure(True)
        self.core.close(); self.core = Core(self.root)
        with patch.object(self.core, '_execute', side_effect=AssertionError('Must not replay')):
            self.drain()
        self.assertEqual(observe(self.core, ident)['state'], 'PARTIAL')
        self.assertEqual(self.core.tasks.actions(ident), actions)

    def test_crash_between_projection_and_checkpoint_rolls_back_both(self):
        service(self.core).configure(False); ident = self.complete(); service(self.core).configure(True)
        observer = service(self.core); original = observer._assess
        def crash(tx, task_row):
            original(tx, task_row)
            raise SystemExit('simulated observer process loss')
        with patch.object(observer, '_assess', side_effect=crash), self.assertRaises(SystemExit):
            observer.consume(64)
        self.assertEqual(self.count(ident), 0)
        seq = self.core.db.one("SELECT seq FROM events WHERE task_id=? AND kind='task.succeeded'", (ident,))['seq']
        self.assertLess(self.core.db.one('SELECT last_seq FROM outcome_consumers')['last_seq'], seq)
        self.drain(); self.assertEqual(self.count(ident), 1)

    def test_file_change_and_restoration_append_history_without_reusing_old_verdict(self):
        ident = self.complete(); first = observe(self.core, ident); original = self.artifact(ident).read_bytes()
        self.artifact(ident).write_text('changed', encoding='utf-8')
        changed = observe(self.core, ident)
        self.assertEqual(changed['state'], 'ISSUES'); self.assertEqual(changed['supersedes'], first['id'])
        self.artifact(ident).write_bytes(original)
        restored = observe(self.core, ident)
        self.assertEqual(restored['state'], 'PARTIAL'); self.assertNotEqual(first['id'], restored['id'])
        self.assertEqual(restored['supersedes'], changed['id']); self.assertEqual(self.count(ident), 3)
        self.assertEqual(self.core.tasks.get(ident)['status'], 'SUCCEEDED')
        history = command(self.root, {'action':'outcome_history','id':ident})
        self.assertEqual(history['current_id'], restored['id']); self.assertEqual(len(history['items']), 3)

    def test_missing_file_does_not_hide_the_confirmed_output(self):
        ident = self.complete(); actions = self.core.tasks.actions(ident); self.artifact(ident).unlink()
        result = observe(self.core, ident)
        self.assertEqual(result['state'], 'ISSUES')
        self.assertIn('artifact_unavailable', [c['reason'] for c in result['criteria']])
        self.assertEqual(self.core.tasks.actions(ident), actions)

    def test_changed_goal_revision_invalidates_evidence_without_rewriting_execution(self):
        ident = self.complete(); self.link_goal(ident)
        first = observe(self.core, ident); self.assertEqual(first['source_status'], 'current')
        with self.core.db.transaction() as tx: tx.execute("UPDATE goal_plans SET revision=3 WHERE id='goal-outcome'")
        result = observe(self.core, ident)
        self.assertEqual(result['state'], 'INVALIDATED'); self.assertEqual(result['supersedes'], first['id'])

    def test_actual_memory_revocation_invalidates_assessment_across_restart(self):
        from modules.context_knowledge.memory import Memory
        from test_memory_development_ui import fact
        memory = Memory(self.core.db); memory.save(fact(), 0)
        ident = self.complete(); self.link_goal(ident)
        view = memory.view('personal','openai',True)
        view['providers'] = ['openai']; view['selectors'] = {'channel':'task'}
        self.core.db.connection.execute('INSERT INTO goal_context VALUES(?,?,?,?,?)',
                                       ('goal-outcome','personal',1,canonical(view),'[]'))
        first = observe(self.core, ident); self.assertEqual(first['source_status'], 'current')
        memory.forget('personal','称呼',1)
        self.core.close(); self.core = Core(self.root)
        result = observe(self.core, ident)
        self.assertEqual(result['state'], 'INVALIDATED'); self.assertEqual(result['supersedes'], first['id'])

    def test_checker_failure_preserves_result_and_is_visible_and_retryable(self):
        identity = self.core.identity.describe()
        with patch.object(Outcomes, '_assess', side_effect=RuntimeError('sensitive exception must not be persisted')):
            ident = self.complete()
        actions = self.core.tasks.actions(ident)
        self.assertTrue(self.artifact(ident).exists())
        self.assertEqual(observe(self.core, ident)['state'], 'UNAVAILABLE')
        self.assertEqual(self.core.tasks.get(ident)['status'], 'SUCCEEDED')
        self.assertEqual(self.core.identity.describe(), identity)
        self.assertEqual(command(self.root, {'action':'outcome_retry','id':ident})['state'], 'PARTIAL')
        self.assertEqual(self.core.tasks.actions(ident), actions)

    def test_optional_schema_failure_cannot_fail_the_task(self):
        with patch('modules.evaluation.outcomes.ensure', side_effect=CoreError('outcome_schema','fixture')):
            ident = self.complete()
            self.assertEqual(observe(self.core, ident)['state'], 'UNAVAILABLE')
        self.assertEqual(self.core.tasks.get(ident)['status'], 'SUCCEEDED')
        self.assertTrue(self.artifact(ident).exists())

    def test_poison_event_does_not_starve_another_task(self):
        observer = service(self.core); observer.configure(False)
        bad = self.complete('bad'); good = self.complete('good'); observer.configure(True)
        original = observer._assess
        def checker(tx, row):
            if row['id']==bad: raise ValueError('bad checker')
            return original(tx, row)
        with patch.object(observer, '_assess', side_effect=checker): self.drain(observer)
        self.assertEqual(observer.refresh(bad)['state'], 'UNAVAILABLE')
        self.assertEqual(observer.refresh(good)['state'], 'PARTIAL')
        self.assertEqual(self.core.db.one('SELECT attempts FROM outcome_failures WHERE task_id=?', (bad,))['attempts'], 1)

    def test_checker_retries_are_bounded_even_with_repeated_refresh(self):
        with patch.object(Outcomes, '_assess', side_effect=ValueError('fixture')) as fail:
            ident = self.complete()
            for _ in range(8):
                self.core.db.connection.execute('UPDATE outcome_failures SET next_retry=0 WHERE task_id=?', (ident,))
                observe(self.core, ident)
        self.assertEqual(fail.call_count, 3)
        self.assertEqual(self.core.db.one('SELECT attempts FROM outcome_failures')['attempts'], 3)

    def test_due_observer_failure_is_recovered_by_existing_consumer_without_new_event(self):
        with patch.object(Outcomes, '_assess', side_effect=ValueError('fixture')):
            ident = self.complete(); self.drain()
        self.core.db.connection.execute('UPDATE outcome_failures SET next_retry=0 WHERE task_id=?', (ident,))
        self.core.close(); self.core = Core(self.root)
        service(self.core).consume()
        self.assertEqual(self.core.db.all('SELECT * FROM outcome_failures'), [])
        self.assertEqual(self.count(ident), 1)

    def test_wrong_statistics_are_not_accepted_just_because_execution_succeeded(self):
        ident = self.complete(); action = self.core.tasks.actions(ident)[0]
        result = decode(action['result']); result['words'] = 999
        self.core.db.connection.execute('UPDATE actions SET result=? WHERE id=?', (canonical(result), action['id']))
        outcome = observe(self.core, ident)
        self.assertEqual(outcome['state'], 'ISSUES')
        self.assertEqual(next(c['status'] for c in outcome['criteria'] if c['id']=='result:analyze'), 'failed')

    def test_unknown_effect_is_not_assessed_as_success_or_resumed(self):
        ident = self.core.tasks.submit(task())
        self.core.tasks.state(ident, 'RUNNING')
        step = task()['steps'][0]; action = self.core.tasks.prepare(ident, step, step['arguments'])
        self.core.tasks.dispatch(ident, action['id']); self.core.tasks.uncertain(ident, action['id'])
        before = self.core.tasks.actions(ident)
        self.assertEqual(observe(self.core, ident)['state'], 'PENDING'); self.drain()
        self.assertEqual(self.core.tasks.actions(ident), before)
        self.assertEqual(self.core.tasks.get(ident)['status'], 'WAITING')

    def test_oversized_artifact_and_mismatched_path_fail_boundedly(self):
        ident = self.complete(); self.artifact(ident).write_bytes(b'x'*(MAX_FILE_BYTES+1))
        result = observe(self.core, ident)
        self.assertIn('inspection_budget', [c['reason'] for c in result['criteria']])
        action = self.core.tasks.actions(ident)[-1]; receipt = decode(action['result']); receipt['relative_path']='../outside.txt'
        self.core.db.connection.execute('UPDATE actions SET result=? WHERE id=?', (canonical(receipt), action['id']))
        with patch('modules.evaluation.outcomes.child', side_effect=AssertionError('Must reject before reading path')):
            result = observe(self.core, ident)
        self.assertEqual(result['state'], 'ISSUES')
        self.assertIn('artifact_binding_changed', [c['reason'] for c in result['criteria']])

    def test_redacted_result_invalidates_and_history_never_copies_user_text(self):
        ident = self.complete(); first = observe(self.core, ident)
        action = self.core.tasks.actions(ident)[0]
        self.core.db.connection.execute('UPDATE actions SET result=? WHERE id=?', (canonical({'redacted':True}), action['id']))
        result = observe(self.core, ident)
        self.assertEqual(result['state'], 'INVALIDATED'); self.assertEqual(result['supersedes'], first['id'])
        history = canonical(self.core.db.all('SELECT body FROM outcome_assessments'))
        self.assertNotIn('hello world', history)

    def test_strict_contract_rejects_invented_score_unknown_fields_and_boolean_revision(self):
        result = observe(self.core, self.complete())
        for change in ({'score':100}, {'task_revision':True}, {'extra':'bad'}, {'schema':'jarvis.outcome-assessment.v2'}):
            with self.assertRaises(CoreError): contract('outcome-assessment', {**result, **change})

    def test_concurrent_consumers_keep_one_projection(self):
        service(self.core).configure(False); ident = self.complete(); service(self.core).configure(True)
        def consume(_):
            core = Core(self.root)
            try:
                observer = service(core)
                for _ in range(3): observer.consume(64)
                return observer.refresh(ident)['id']
            finally: core.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(consume, range(2)))
        self.assertEqual(result[0], result[1]); self.assertEqual(self.count(ident), 1)

    def test_switch_persists_and_work_status_uses_same_original_task(self):
        ident = self.complete()
        item = next(i for i in snapshot(self.root, SimpleNamespace())['items'] if i['id']==ident)
        self.assertEqual(item['raw_status'], 'SUCCEEDED'); self.assertEqual(item['outcome'], observe(self.core, ident))
        command(self.root, {'action':'outcome_configure','enabled':False})
        self.assertEqual(observe(self.core, ident)['state'], 'DISABLED')
        with self.assertRaises(CoreError): command(self.root, {'action':'outcome_configure','enabled':1})
        self.core.close(); self.core = Core(self.root)
        self.assertFalse(service(self.core).enabled())

    def test_status_limits_fresh_checks_and_marks_remaining_results_stale(self):
        ids = [self.complete('status-'+str(i)) for i in range(5)]
        items = [i for i in snapshot(self.root, SimpleNamespace())['items'] if i['id'] in ids]
        self.assertEqual(sum(i['outcome']['state']=='PARTIAL' for i in items), 4)
        self.assertEqual(sum(i['outcome']['state']=='STALE' for i in items), 1)


if __name__=='__main__': unittest.main()
