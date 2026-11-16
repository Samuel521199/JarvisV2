"""Automatic completion is explicit review + immutable commit, not a quiet editor."""
import copy,json
from pathlib import Path
import tempfile,unittest
from unittest.mock import Mock,patch

from tools import workstation_completion as completion


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve()
        self.source=self.base/'dev';self.source.mkdir();self.dev=self.source/'user-data';self.root=self.base/'daily/user-data'
        self.folder=self.root/'deployment/automation';self.folder.mkdir(parents=True)
        self.config={'schema':1,'enabled':True,'source':str(self.source),'branch':'codex/test','baseline_head':'a'*40,
            'required_trailer':completion.TRAILER,'quiet_seconds':120,'max_checks_per_24h':4,'worker_wall_seconds':600}
        self.repo={'source':str(self.source),'branch':'codex/test','head':'b'*40,'clean':True,'reviewed':True}
        self.now=1000;self.operator=Mock()

    def engine(self):
        return completion.Completion(self.root,self.config,self.dev,self.operator,clock=lambda:self.now)

    def test_policy_cannot_weaken_fixed_gates(self):
        for key,value in [('quiet_seconds',0),('max_checks_per_24h',999),('worker_wall_seconds',99999),('required_trailer','anything')]:
            with self.assertRaises(ValueError):completion.validate({**self.config,key:value})

    def test_configured_source_must_be_development_parent(self):
        with self.assertRaises(ValueError):completion.Completion(self.root,self.config,self.base/'other/user-data',self.operator)

    def test_repository_requires_actual_review_trailer_not_body_text(self):
        def git(*args):
            command=args[1:]
            if command==('rev-parse','--show-toplevel'):return str(self.source).encode()
            if command==('rev-parse','HEAD'):return b'b'*40
            if command==('symbolic-ref','--quiet','--short','HEAD'):return b'codex/test'
            if command==('show','-s','--format=%B','b'*40):return b'finished\n\nJarvis-Reviewed: complete\n\nbody continues'
            if command==('show','-s','--format=%(trailers:only,unfold)','b'*40):return b''
            if command==('rev-parse','--git-path','index.lock'):return str(self.source/'index.lock').encode()
            if command[0]=='status':return b''
            raise AssertionError(command)
        with patch.object(completion,'git',side_effect=git):self.assertFalse(completion.repository(self.source)['reviewed'])

    def test_git_inspection_disables_fsmonitor_and_never_fetches(self):
        with patch.object(completion.subprocess,'run',return_value=Mock(returncode=0,stdout=b'clean')) as run:
            completion.git(self.source,'status','--porcelain')
        args=run.call_args.args[0];self.assertIn('core.fsmonitor=false',args);self.assertNotIn('fetch',args)
        self.assertEqual(run.call_args.kwargs['env']['GIT_NO_REPLACE_OBJECTS'],'1')

    def test_dirty_wrong_branch_unreviewed_and_wrong_head_rejected(self):
        for patch_value in [{'clean':False},{'branch':'other'},{'reviewed':False},{'head':'c'*40}]:
            with patch.object(completion,'repository',return_value={**self.repo,**patch_value}):
                with self.assertRaises(ValueError):completion.require_snapshot(self.config,'b'*40)

    def test_quiet_snapshot_does_not_mean_review(self):
        e=self.engine()
        with patch.object(completion,'repository',return_value={**self.repo,'reviewed':False}),patch.object(e,'spawn') as spawn:
            e.tick();self.now+=10000;e.tick();spawn.assert_not_called()
        self.assertEqual(e.state['status'],'waiting_for_reviewed_completion')

    def test_clean_new_completion_stabilizes_then_starts_checks(self):
        e=self.engine()
        with patch.object(completion,'repository',return_value=self.repo),patch.object(e,'resources_changed',return_value=True),patch.object(e,'spawn') as spawn:
            e.tick();spawn.assert_not_called();self.now+=119;e.tick();spawn.assert_not_called();self.now+=1;e.tick()
            spawn.assert_called_once_with('b'*40)

    def test_dirty_interval_resets_quiet_clock(self):
        e=self.engine()
        with patch.object(completion,'repository',return_value=self.repo) as repo,patch.object(e,'spawn') as spawn:
            e.tick();self.now+=121;repo.return_value={**self.repo,'clean':False};e.tick()
            repo.return_value=self.repo;e.tick();spawn.assert_not_called();self.assertEqual(e.state['stable_since'],self.now)

    def test_initial_baseline_and_already_attempted_commit_never_replayed(self):
        e=self.engine()
        for head,attempts in [('a'*40,[]),('b'*40,[{'head':'b'*40,'time':1,'checked':True}])]:
            e.state['attempts']=attempts
            with patch.object(completion,'repository',return_value={**self.repo,'head':head}),patch.object(e,'spawn') as spawn:
                e.tick();spawn.assert_not_called()

    def test_document_only_commit_consumes_no_test_budget(self):
        e=self.engine();e.state.update(seen_head='b'*40,stable_since=800)
        with patch.object(completion,'repository',return_value=self.repo),patch.object(e,'resources_changed',return_value=False),patch.object(e,'spawn') as spawn:
            e.tick();spawn.assert_not_called()
        self.assertEqual(e.state['status'],'no_runtime_change');self.assertFalse(e.state['attempts'][0]['checked'])

    def test_test_runs_are_bounded_per_day(self):
        e=self.engine();e.state.update(seen_head='b'*40,stable_since=800,
            attempts=[{'head':str(i)*40,'time':999,'checked':True} for i in range(4)])
        with patch.object(completion,'repository',return_value=self.repo),patch.object(e,'spawn') as spawn:
            e.tick();spawn.assert_not_called()
        self.assertEqual(e.state['status'],'daily_check_limit')

    def test_interrupted_check_does_not_reexecute_after_restart(self):
        (self.folder/'completion-state.json').write_text(json.dumps({'schema':1,'status':'checking','head':'b'*40,
            'attempts':[{'head':'b'*40,'time':999,'checked':True}]}))
        e=self.engine();self.assertEqual(e.state['status'],'interrupted')
        with patch.object(completion,'repository',return_value=self.repo),patch.object(e,'spawn') as spawn:e.tick();spawn.assert_not_called()

    def test_failed_worker_start_is_reserved_and_resource_limited(self):
        e=self.engine()
        with patch.object(completion,'OwnedProcess',side_effect=OSError('fixture')) as process:
            with self.assertRaises(OSError):e.spawn('b'*40)
        args=process.call_args.kwargs;self.assertEqual(args['processes'],64);self.assertEqual(args['cpu_seconds'],600)
        self.assertEqual(args['memory_bytes'],2*1024**3);self.assertEqual(e.state['status'],'failed')
        self.assertEqual(e.state['attempts'][0]['head'],'b'*40);self.assertEqual(e.handles,[])

    def test_background_check_does_not_block_health_loop(self):
        e=self.engine();process=Mock(closed=False);process.poll.return_value=None;e.process=process
        e.state.update(started=1000,head='b'*40,status='checking')
        with patch.object(completion,'require_snapshot'):e.poll()
        process.wait.assert_not_called();process.close.assert_not_called()

    def test_source_change_and_timeout_kill_only_owned_check_job(self):
        for timeout in (False,True):
            e=self.engine();process=Mock(closed=False);process.poll.return_value=None;e.process=process
            process.close.side_effect=lambda:setattr(process,'closed',True)
            e.state.update(started=0 if timeout else 1000,head='b'*40,status='checking')
            with patch.object(completion,'require_snapshot',side_effect=ValueError('changed')):e.poll()
            process.close.assert_called_once();self.assertIsNone(e.process)
            self.assertEqual(e.state['status'],'failed' if timeout else 'cancelled')

    def test_success_is_published_only_after_owned_tree_cleanup(self):
        e=self.engine();process=Mock(closed=False);process.poll.return_value=0;e.process=process
        process.close.side_effect=lambda:setattr(process,'closed',True)
        e.state.update(started=1000,head='b'*40,status='checking');e.poll()
        process.close.assert_called_once();self.assertIsNone(e.process);self.assertEqual(e.state['status'],'queued')

    def test_cleanup_failure_never_marks_candidate_checks_queued(self):
        e=self.engine();process=Mock(closed=False);process.poll.return_value=0;e.process=process
        process.close.side_effect=RuntimeError('cleanup unconfirmed')
        e.state.update(started=1000,head='b'*40,status='checking')
        with self.assertRaises(RuntimeError):e.poll()
        self.assertEqual(e.state['status'],'checking')

    def test_prepare_passes_reviewed_snapshot_and_rechecks_before_queue(self):
        queued=Mock(return_value={'queued':True})
        def prepare(root,dev,source,queue_callback):return queue_callback(root,dev,{'build':'c'*64})
        self.operator.prepare.side_effect=prepare
        with patch.object(completion,'require_snapshot') as require:
            result=completion.prepare_one(self.root,self.dev,self.operator,self.config,'b'*40,queued)
        self.assertEqual(require.call_count,2);self.assertTrue(result['preparation']['queued'])
        self.assertEqual(queued.call_args.args[2]['completion_commit'],'b'*40)

    def test_changed_source_after_independent_checks_never_queues(self):
        queued=Mock()
        self.operator.prepare.side_effect=lambda root,dev,source,queue_callback:queue_callback(root,dev,{'build':'c'*64})
        with patch.object(completion,'require_snapshot',side_effect=[self.repo,ValueError('changed')]):
            with self.assertRaises(ValueError):completion.prepare_one(self.root,self.dev,self.operator,self.config,'b'*40,queued)
        queued.assert_not_called()


if __name__=='__main__':unittest.main()
