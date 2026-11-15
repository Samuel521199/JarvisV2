import json,sqlite3,tempfile,unittest
from pathlib import Path
from tools.observe_task_trial import observe,token_summary,connection


class TaskTrialObserverTests(unittest.TestCase):
    def test_provider_total_includes_reasoning_without_adding_it_again(self):
        value=token_summary([{'ledger':'core','id':'a','usage':{'prompt_tokens':10,'completion_tokens':5,'reasoning_tokens':7,'total_tokens':22}}])
        self.assertEqual(value['total_tokens'],22);self.assertFalse(value['reasoning_added_to_total'])

    def test_missing_total_is_unknown_even_when_other_metrics_exist(self):
        value=token_summary([{'ledger':'core','id':'a','usage':{'prompt_tokens':10,'completion_tokens':5}}])
        self.assertIsNone(value['total_tokens']);self.assertFalse(value['total_tokens_complete'])

    def test_duplicate_receipts_fail_and_negative_bool_counts_are_not_valid(self):
        row={'ledger':'core','id':'a','usage':{'total_tokens':True}}
        self.assertIsNone(token_summary([row])['total_tokens'])
        with self.assertRaises(ValueError):token_summary([row,row])

    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);(root/'state').mkdir()
        db=sqlite3.connect(root/'state/core.sqlite3')
        db.executescript('''CREATE TABLE goal_plans(id,status,task_id,error);CREATE TABLE work_revisions(goal_id,parent_goal);
          CREATE TABLE events(seq INTEGER PRIMARY KEY,kind,data);CREATE TABLE goal_growth(goal_id,development_id);
          CREATE TABLE development_runs(id);CREATE TABLE model_calls(id,run_id,phase,status,error,usage,created);
          CREATE TABLE task_completion(task_id,body,checked);''')
        db.executemany('INSERT INTO goal_plans VALUES(?,?,?,NULL)',[('goal-a','ACCEPTED','task-a'),('goal-b','ACCEPTED','task-b')])
        db.execute("INSERT INTO work_revisions VALUES('goal-b','goal-a')")
        db.execute('INSERT INTO events(kind,data) VALUES(?,?)',('learning.repair_return',json.dumps({'source_task':'task-a','development_id':'repair','child_goal':'goal-b'})))
        db.execute("INSERT INTO goal_growth VALUES('goal-a','growth')")
        db.execute("INSERT INTO development_runs VALUES('setup')")
        for i,run in enumerate(['goal-a','goal-a-g1','goal-a-return-g2','goal-a-draft','goal-b','growth','repair','setup','goal-a-unrelated']):
            db.execute('INSERT INTO model_calls VALUES(?,?,?, ?,NULL,?,?)',(str(i),run,'plan','FAILED' if i==1 else 'SUCCEEDED',json.dumps({'total_tokens':10}),i))
        db.commit();db.close()
        return root

    def test_linked_repairs_all_generations_failed_calls_and_separate_setup(self):
        root=self.fixture();value=observe(root,{'schema':1,'goal_ids':['goal-a'],'setup_run_ids':['setup']})
        self.assertEqual(value['goal_ids'],['goal-a','goal-b']);self.assertEqual(value['work_tokens']['total_tokens'],70)
        self.assertEqual(value['shared_setup_tokens']['total_tokens'],10)
        self.assertTrue(any(c['status']=='FAILED' for c in value['work_calls']))
        self.assertTrue(all(r['condition_score'] is None for r in value['scores']))
        self.assertIsNone(value['interventions'])

    def test_unknown_goal_and_setup_rejected_and_database_read_only(self):
        root=self.fixture()
        with self.assertRaises(ValueError):observe(root,{'schema':1,'goal_ids':['missing']})
        with self.assertRaises(ValueError):observe(root,{'schema':1,'setup_run_ids':['missing']})
        db=connection(root/'state/core.sqlite3')
        try:
            with self.assertRaises(sqlite3.OperationalError):db.execute('DELETE FROM goal_plans')
        finally:db.close()

    def test_dialogue_attempts_include_failure_without_double_counting_turn_total(self):
        root=self.fixture();db=sqlite3.connect(root/'state/dialogue.sqlite3')
        db.executescript('CREATE TABLE turns(id,usage);CREATE TABLE attempts(id,turn_id,status,error,usage);')
        db.execute('INSERT INTO turns VALUES(?,?)',('turn-a',json.dumps({'total_tokens':9999})))
        db.executemany('INSERT INTO attempts VALUES(?,?,?,?,?)',[(1,'turn-a','SUCCEEDED',None,json.dumps({'total_tokens':12})),(2,'turn-a','UNKNOWN','timeout',None)])
        db.commit();db.close();value=observe(root,{'schema':1,'turn_ids':['turn-a']})
        self.assertEqual(value['work_tokens']['calls'],2);self.assertEqual(value['work_tokens']['reported_tokens']['total_tokens'],12)
        self.assertIsNone(value['work_tokens']['total_tokens'])


if __name__=='__main__':unittest.main()
