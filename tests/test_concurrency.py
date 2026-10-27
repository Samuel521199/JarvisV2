import copy
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from adapters.models.native import NativeModel
from control.recovery.gate import RunLock
from host.core import Core
from host.dialogue import DialogueHost
from host.task_scheduler import TaskRunner
from host.work_status import snapshot, category
from modules.dialogue.store import Dialogues
from modules.preferences.store import Preferences
from modules.registry_composer.registry import Registry
from modules.task_resource.scheduling import Scheduling, resources
from sdk.protocol import CoreError


def memory_ok():
    return {'cpu_percent': 10, 'memory_total': 16*1024**3, 'memory_used': 4*1024**3}


def task(key):
    return {'schema': 'jarvis.task.v1', 'request_id': key, 'principal_id': 'owner.local', 'scope_id': 'personal',
            'grant_id': 'local-default', 'goal': 'Measure '+key,
            'steps': [{'step_id': 'analyze', 'capability': 'text.analyze.v1', 'arguments': {'text': key}},
                      {'step_id': 'deliver', 'capability': 'artifact.write.v1', 'arguments': {'name': 'report.json'}, 'input_from': 'analyze'}],
            'limits': {'max_steps': 2, 'max_attempts': 1, 'max_seconds': 3600, 'max_cost_units': 2}}


def configure(root):
    prefs = Preferences(root)
    try:
        prefs.install({'schema_version': 1, 'default_provider': 'openai', 'automatic_fallback': False,
                       'fallback_order': ['openai'], 'max_output_tokens': 512, 'max_prompt_bytes': 50000,
                       'providers': {'openai': {'adapter': 'openai', 'label': 'Fixture', 'model': 'fixture',
                                                'models': {'fixture': {'parameters': {}, 'reasoning_levels': []}}}}},
                      {'model': 'fixture', 'reasoning': 'medium', 'enabled': False, 'revision': 1})
    finally: prefs.close()


def message(chat, key, text='hello'):
    return {'chat_id': chat, 'request_id': key, 'text': text, 'provider': 'openai', 'model': 'fixture',
            'reasoning': 'default', 'memory_enabled': False, 'skill': 'none'}


def until(check, seconds=5):
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        if check(): return
        time.sleep(.01)
    raise AssertionError('Condition did not become true before deadline')


class ConcurrencyCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-concurrency-')
        self.root = Path(self.temp.name); Core.initialize(self.root).close(); configure(self.root)

    def tearDown(self): self.temp.cleanup()

    def submit(self, *names):
        core = Core(self.root)
        try: return [core.tasks.submit(task(n)) for n in names]
        finally: core.close()

    def read(self, ident):
        core = Core(self.root)
        try: return core.tasks.get(ident)
        finally: core.close()

    def chat(self):
        store = Dialogues(self.root)
        try: return store.create()
        finally: store.close()

    def turn(self, ident):
        store = Dialogues(self.root)
        try: return store.turn(ident)
        finally: store.close()

    def test_two_actual_executions_overlap_and_receipts_are_unique(self):
        first, second = self.submit('first', 'second'); barrier = threading.Barrier(2); seen = []
        original = Registry.execute
        def execute(reg, root, tid, aid, cap, args, impl, checkpoint=lambda: None):
            if cap == 'text.analyze.v1':
                seen.append(tid); barrier.wait(3)
            return original(reg, root, tid, aid, cap, args, impl, checkpoint)
        with patch.object(Registry, 'execute', execute):
            runner = TaskRunner(self.root, resource_sample=memory_ok)
            try:
                runner.start({'max_tasks': 2}); until(lambda: all(self.read(i)['status'] == 'SUCCEEDED' for i in (first, second)))
                self.assertCountEqual(seen, [first, second])
            finally: runner.close()
        core = Core(self.root)
        try:
            self.assertEqual(core.db.one("SELECT COUNT(*) n FROM actions WHERE status='CONFIRMED'")['n'], 4)
            self.assertTrue(all(a['attempts'] == 1 for i in (first, second) for a in core.tasks.actions(i)))
        finally: core.close()

    def test_busy_cohort_blocks_recovery_but_cancel_is_independent(self):
        first, second = self.submit('cancel-one', 'keep-other'); ready = threading.Event(); release = threading.Event()
        original = Registry.execute
        def execute(reg, root, tid, aid, cap, args, impl, checkpoint=lambda: None):
            if tid == first and cap == 'text.analyze.v1':
                ready.set(); release.wait(3); checkpoint()
            return original(reg, root, tid, aid, cap, args, impl, checkpoint)
        with patch.object(Registry, 'execute', execute):
            runner = TaskRunner(self.root, resource_sample=memory_ok)
            try:
                runner.start({'max_tasks': 2}); self.assertTrue(ready.wait(2))
                with self.assertRaises(CoreError):
                    with RunLock(self.root): pass
                core = Core(self.root)
                try: core.tasks.cancel(first)
                finally: core.close()
                release.set(); until(lambda: self.read(second)['status'] == 'SUCCEEDED')
            finally: release.set(); runner.close()
        self.assertEqual(self.read(first)['status'], 'CANCELLED')

    def test_priority_revision_orders_queued_tasks(self):
        low, high = self.submit('low', 'high'); pressure = threading.Event(); order = []
        def samples(): return {**memory_ok(), 'memory_used': 15*1024**3} if not pressure.is_set() else memory_ok()
        runner = TaskRunner(self.root, resource_sample=samples)
        original = Registry.execute
        def execute(reg, root, tid, aid, cap, args, impl, checkpoint=lambda: None):
            if cap == 'text.analyze.v1': order.append(tid)
            return original(reg, root, tid, aid, cap, args, impl, checkpoint)
        try:
            runner.configure({**runner.policy(), 'max_workers': 1})
            runner.start({'max_tasks': 2}); time.sleep(.1)
            value = {'id': high, 'revision': 1, 'priority': 3, 'importance': 3, 'due_at': time.time()+60, 'reason': '主人要求先做'}
            runner.prioritize(value)
            with self.assertRaises(CoreError): runner.prioritize(value)
            with patch.object(Registry, 'execute', execute):
                pressure.set(); runner.wake.set(); until(lambda: self.read(low)['status'] == 'SUCCEEDED')
            self.assertEqual(order, [high, low])
        finally: pressure.set(); runner.close()

    def test_scheduler_session_crash_is_logged_restarted_and_keeps_dispatching(self):
        ident, = self.submit('after-crash'); calls = []
        import host.outcomes as outcomes
        original = outcomes.observe
        def flaky(core, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1: raise RuntimeError('synthetic loop failure')
            return original(core, *args, **kwargs)
        with patch.object(outcomes, 'observe', flaky), self.assertLogs('jarvis.scheduler', 'ERROR') as logged:
            runner = TaskRunner(self.root, resource_sample=memory_ok)
            try:
                runner.start({'max_tasks': 1})
                until(lambda: self.read(ident)['status'] == 'SUCCEEDED', 10)
                until(lambda: runner.state()['error'] is None, 5)
                self.assertTrue(runner.thread.is_alive())
            finally: runner.close()
        self.assertIn('restart 1/', logged.output[0])

    def test_resource_pressure_keeps_queue_durable_across_restart(self):
        ident, = self.submit('recover-queue')
        runner = TaskRunner(self.root, resource_sample=lambda: {**memory_ok(), 'memory_used': 15*1024**3})
        runner.start({'max_tasks': 1}); time.sleep(.15); runner.close(drain=False)
        self.assertEqual(self.read(ident)['status'], 'READY')
        other = TaskRunner(self.root, resource_sample=memory_ok)
        try: until(lambda: self.read(ident)['status'] == 'SUCCEEDED')
        finally: other.close()

    def test_crashed_dispatched_effect_is_not_replayed(self):
        ident, = self.submit('unknown'); core = Core(self.root)
        try:
            s = Scheduling(core.db); s.enqueue([ident]); core.tasks.state(ident, 'RUNNING')
            step = task('unknown')['steps'][0]; action = core.tasks.prepare(ident, step, step['arguments']); core.tasks.dispatch(ident, action['id'])
        finally: core.close()
        runner = TaskRunner(self.root, resource_sample=memory_ok)
        try: until(lambda: self.read(ident)['status'] == 'WAITING')
        finally: runner.close()
        core = Core(self.root)
        try:
            self.assertEqual(core.tasks.actions(ident)[0]['status'], 'UNKNOWN')
            self.assertEqual(core.tasks.actions(ident)[0]['attempts'], 1)
        finally: core.close()

    def test_conflict_classes_do_not_trust_remote_annotations(self):
        a = task('one'); a['steps'][0]['capability'] = 'mcp.one.read'
        b = task('two'); b['steps'][0]['capability'] = 'mcp.two.write'
        self.assertTrue(resources(a)['conflicts'] & resources(b)['conflicts'])
        a['steps'][0]['capability'] = 'plugin.one.v1'; b['steps'][0]['capability'] = 'plugin.two.v1'
        self.assertTrue(resources(a)['conflicts'] & resources(b)['conflicts'])

    def test_background_does_not_take_two_foreground_slots(self):
        gate = threading.Event(); started = threading.Event(); foreground = threading.Barrier(2)
        def complete(model, messages, checkpoint, **kwargs):
            if messages[-1]['content'].startswith('background'):
                started.set(); gate.wait(4)
            else: foreground.wait(3)
            checkpoint(); return {'status': 'SUCCEEDED', 'text': 'actual fixture answer', 'usage': {}}
        with patch.object(NativeModel, 'available', return_value=True), patch.object(NativeModel, 'complete', complete):
            host = DialogueHost(self.root)
            try:
                host.submit_background(message(self.chat(), 'back', 'background'))
                self.assertTrue(started.wait(2))
                host.submit(message(self.chat(), 'front-one')); host.submit(message(self.chat(), 'front-two'))
                until(lambda: all(self.turn(i)['status'] == 'SUCCEEDED' for i in ('front-one', 'front-two')))
                self.assertEqual(self.turn('back')['status'], 'RUNNING')
            finally: gate.set(); host.close()

    def test_same_chat_followup_is_persisted_ordered_and_queued_cancel_is_local(self):
        gate = threading.Event(); started = threading.Event(); texts = []
        def complete(model, messages, checkpoint, **kwargs):
            texts.append(messages[-1]['content'])
            if len(texts) == 1: started.set(); gate.wait(3)
            checkpoint(); return {'status': 'SUCCEEDED', 'text': 'answer', 'usage': {}}
        with patch.object(NativeModel, 'available', return_value=True), patch.object(NativeModel, 'complete', complete):
            host = DialogueHost(self.root); chat = self.chat()
            try:
                host.submit(message(chat, 'one', 'first')); self.assertTrue(started.wait(2))
                result = host.submit(message(chat, 'two', 'important followup')); self.assertEqual(result['status'], 'queued')
                host.submit(message(chat, 'three', 'cancel only this'))
                self.assertTrue(host.cancel('three')); self.assertEqual(self.turn('three')['status'], 'CANCELLED')
                self.assertEqual(self.turn('one')['status'], 'RUNNING')
                gate.set(); until(lambda: self.turn('two')['status'] == 'SUCCEEDED')
                self.assertEqual(texts, ['first', 'important followup'])
            finally: gate.set(); host.close()

    def test_ready_input_survives_restart_without_replaying_running(self):
        store = Dialogues(self.root)
        from modules.preferences.store import resolve
        prefs = Preferences(self.root)
        try:
            route = resolve(prefs.read()['catalog']); chat = store.create()
            store.begin(message(chat, 'ready'), [route], allow_queue=True)
            other = store.create(); store.begin(message(other, 'running'), [route]); store.context('running')
        finally: store.close(); prefs.close()
        with patch.object(NativeModel, 'available', return_value=True), patch.object(NativeModel, 'complete', return_value={'status': 'SUCCEEDED', 'text': 'answer', 'usage': {}}) as call:
            host = DialogueHost(self.root)
            try: until(lambda: self.turn('ready')['status'] == 'SUCCEEDED')
            finally: host.close()
            self.assertEqual(call.call_count, 1); self.assertEqual(self.turn('running')['status'], 'UNKNOWN')

    def test_projection_uses_original_task_and_distinguishes_not_started(self):
        ident, = self.submit('visible'); runner = TaskRunner(self.root, resource_sample=memory_ok)
        try:
            value = snapshot(self.root, SimpleNamespace(task_runner=runner))
            row = next(i for i in value['items'] if i['id'] == ident)
            self.assertEqual(row['state'], 'waiting')
            self.assertEqual(category('NEW'), 'waiting')
            self.assertEqual(sum(i['id'] == ident for i in value['items']), 1)
            self.assertTrue(any(s['status'] == 'not_connected' for s in value['sources']))
        finally: runner.close()

    def test_duplicate_enqueue_does_not_duplicate_effects_and_owner_is_unique(self):
        ident, = self.submit('duplicate'); runner = TaskRunner(self.root, resource_sample=memory_ok)
        try:
            with self.assertRaises(CoreError): TaskRunner(self.root, resource_sample=memory_ok)
            runner.start({'max_tasks': 1}); runner.start({'max_tasks': 1})
            until(lambda: self.read(ident)['status'] == 'SUCCEEDED')
        finally: runner.close()
        core = Core(self.root)
        try: self.assertEqual(len(core.tasks.actions(ident)), 2)
        finally: core.close()

    def test_budget_settings_are_bounded_and_revision_checked(self):
        runner = TaskRunner(self.root, resource_sample=memory_ok)
        try:
            p = runner.policy(); runner.configure({**p, 'max_workers': 3})
            for value in ({**p, 'max_workers': 4}, {**runner.policy(), 'max_workers': 100}, {**runner.policy(), 'memory_reserve_mib': 0}):
                with self.assertRaises(CoreError): runner.configure(value)
        finally: runner.close()


    def test_waiting_foreground_defers_background_without_losing_it(self):
        ident, = self.submit('foreground-reserved'); queued = threading.Event(); queued.set()
        runner = TaskRunner(self.root, resource_sample=memory_ok, foreground_pending=queued.is_set)
        try:
            runner.start({'max_tasks': 1}); time.sleep(.2)
            self.assertEqual(self.read(ident)['status'], 'READY')
            core = Core(self.root)
            try: self.assertIn('聊天', Scheduling(core.db).rows()[0]['wait_reason'])
            finally: core.close()
            queued.clear(); runner.wake.set(); until(lambda: self.read(ident)['status'] == 'SUCCEEDED')
        finally: queued.clear(); runner.close()

    def test_queue_capacity_is_atomic_and_aging_prevents_starvation(self):
        ids = self.submit('old', 'new-high', 'third', 'fourth', 'fifth'); core = Core(self.root)
        try:
            s = Scheduling(core.db); s.configure({**s.policy(), 'queue_limit': 4})
            with self.assertRaises(CoreError): s.enqueue(ids)
            self.assertEqual(s.pending(), [])
            s.enqueue(ids[:4]); s.enqueue([ids[0]])
            s.prioritize({'id': ids[1], 'revision': 1, 'priority': 3, 'importance': 3, 'due_at': None, 'reason': 'urgent'})
            with core.db.transaction() as tx: tx.execute('UPDATE task_dispatch SET queued_at=? WHERE task_id=?', (time.time()-1800, ids[0]))
            self.assertEqual(s.pending()[0]['task_id'], ids[0])
            with self.assertRaises(CoreError): s.enqueue([ids[4]])
            self.assertEqual(core.tasks.get(ids[4])['status'], 'READY')
        finally: core.close()

    def test_conflicting_effect_classes_are_really_serialized(self):
        ids = self.submit('serialized-one', 'serialized-two'); active = 0; peak = 0; lock = threading.Lock()
        original = Registry.execute
        def execute(reg, root, tid, aid, cap, args, impl, checkpoint=lambda: None):
            nonlocal active, peak
            if cap == 'text.analyze.v1':
                with lock: active += 1; peak = max(peak, active)
                time.sleep(.1)
                with lock: active -= 1
            return original(reg, root, tid, aid, cap, args, impl, checkpoint)
        with patch('host.task_scheduler.resources', return_value={'memory_mib': 32, 'conflicts': {'same-resource'}}), patch.object(Registry, 'execute', execute):
            runner = TaskRunner(self.root, resource_sample=memory_ok)
            try:
                runner.start({'max_tasks': 2}); until(lambda: all(self.read(i)['status'] == 'SUCCEEDED' for i in ids))
                self.assertEqual(peak, 1)
            finally: runner.close()


    def test_old_active_work_is_not_hidden_by_newer_history(self):
        core = Core(self.root)
        try:
            old = core.tasks.submit(task('old-active')); s = Scheduling(core.db); s.enqueue([old])
            s.prioritize({'id': old, 'revision': 1, 'priority': 3, 'importance': 3, 'due_at': None, 'reason': 'long job'})
            core.tasks.state(old, 'RUNNING')
            for n in range(110): core.tasks.submit(task('new-history-'+str(n)))
        finally: core.close()
        value = snapshot(self.root, SimpleNamespace())
        row = next(i for i in value['items'] if i['id'] == old)
        self.assertEqual(row['state'], 'running'); self.assertEqual(row['priority'], 3)


    def test_checkpoint_reader_does_not_wait_for_unrelated_dialogue_writer(self):
        # A migrated WAL reader must not acquire a write lock just to check identity.
        store = Dialogues(self.root); chat = store.create()
        try:
            store.db.execute('BEGIN IMMEDIATE')
            store.db.execute('UPDATE chats SET title=? WHERE id=?', ('uncommitted', chat))
            result = []; done = threading.Event()
            def read_header():
                reader = None
                try:
                    reader = Dialogues(self.root); result.append(reader.header(chat)['title'])
                finally:
                    if reader: reader.close()
                    done.set()
            thread = threading.Thread(target=read_header); thread.start()
            try: self.assertTrue(done.wait(1), 'Read-only checkpoint waited for the writer')
            finally: store.db.execute('ROLLBACK'); thread.join(6)
            self.assertEqual(result, ['新对话'])
        finally: store.close()


if __name__ == '__main__': unittest.main()
