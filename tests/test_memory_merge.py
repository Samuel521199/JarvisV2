import unittest
from unittest.mock import patch
import test_memory_domains as fixtures
from modules.context_knowledge import Facts
from modules.context_knowledge.merge import Merge
from sdk.protocol import CoreError,canonical


class MergeTests(unittest.TestCase):
    setUp=fixtures.DomainTests.setUp
    tearDown=fixtures.DomainTests.tearDown
    save=fixtures.DomainTests.save
    branch=fixtures.DomainTests.branch

    def apply(self,branch,choice='branch'):
        manager=Merge(self.core.db);plan=manager.preview(branch)
        choices={r['id']:choice for r in plan['items'] if r['state'] not in {'forgotten','unchanged'}}
        return manager.apply(branch,plan['token'],choices)

    def test_three_way_conflict_preserves_parent_until_explicit_review(self):
        self.save('base');branch=self.branch();self.save('branch',scope=branch);self.save('parent',1)
        p=Merge(self.core.db).preview(branch);self.assertEqual(p['items'][0]['state'],'conflict')
        self.assertEqual(self.memory.list(self.project)[0]['value'],'parent')
        r=self.apply(branch);self.assertEqual(r['changed'],1)
        row=self.memory.list(self.project)[0];self.assertEqual(row['value'],'branch')
        self.assertEqual(row['providers'],[]);self.assertEqual(row['state'],'paused')
        self.assertTrue(row['source'].startswith('owner:branch-merge:'))
        self.assertEqual(self.memory.list(branch)[0]['value'],'branch')

    def test_stale_preview_and_missing_decisions_rejected_atomically(self):
        self.save('base');branch=self.branch();self.save('branch',scope=branch)
        m=Merge(self.core.db);p=m.preview(branch)
        with self.assertRaises(CoreError):m.apply(branch,p['token'],{})
        self.save('new parent',1)
        with self.assertRaises(CoreError):m.apply(branch,p['token'],{p['items'][0]['id']:'branch'})
        self.assertEqual(self.memory.list(self.project)[0]['value'],'new parent')

    def test_forgotten_parent_never_resurrected_and_merge_receipt_idempotent(self):
        self.save('base');branch=self.branch();self.save('branch',scope=branch)
        m=Merge(self.core.db);p=m.preview(branch);choices={p['items'][0]['id']:'branch'}
        first=m.apply(branch,p['token'],choices);self.assertEqual(first['changed'],1)
        self.memory.forget(self.project,'接口版本',2)
        self.assertTrue(m.apply(branch,p['token'],choices)['replayed'])
        self.assertEqual(m.preview(branch)['items'][0]['state'],'forgotten');self.assertEqual(self.apply(branch)['changed'],0)
        self.assertEqual(self.memory.list(self.project),[])

    def test_delete_only_selected_and_user_correction_is_independent(self):
        self.save('base');branch=self.branch();self.save('branch',scope=branch);self.apply(branch)
        self.memory.forget(branch,'接口版本',1)
        # The merge is an explicit owner confirmation, not an unreviewed dependency.
        self.assertEqual(self.memory.list(self.project)[0]['value'],'branch')
        self.assertEqual(self.apply(branch,'parent')['changed'],0)
        self.assertEqual(self.apply(branch)['changed'],1);self.assertEqual(self.memory.list(self.project),[])
        self.assertNotIn('branch',canonical(self.core.db.all("SELECT body FROM memory_history WHERE scope=?",(self.project,))))

    def test_mid_merge_failure_rolls_back_all_edits(self):
        branch=self.branch();self.save('one',scope=branch,key='one');self.save('two',scope=branch,key='two')
        original=Facts.write;calls=[]
        def fail(*args):
            calls.append(1)
            if len(calls)==2:raise RuntimeError('injected')
            return original(*args)
        with patch.object(Facts,'write',side_effect=fail):
            with self.assertRaises(RuntimeError):self.apply(branch)
        self.assertEqual(self.memory.list(self.project),[])
        self.assertEqual(self.core.db.all("SELECT * FROM memory_imports WHERE id LIKE 'merge-%'"),[])


if __name__=='__main__':unittest.main()
