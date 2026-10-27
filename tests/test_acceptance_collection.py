"""Acceptance collection does not lose a case or allow a repeated pass to hide failure."""
import unittest
from io import StringIO
from tools.accept_completion import unique_suite, test_ids, RecordedResult


class AcceptanceCollection(unittest.TestCase):
    def test_repeated_imports_keep_every_distinct_id_exactly_once(self):
        class Example(unittest.TestCase):
            def test_one(self):pass
            def test_two(self):pass
        first=Example('test_one');second=Example('test_two')
        suite,duplicates=unique_suite(unittest.TestSuite([first,unittest.TestSuite([Example('test_one'),second])]))
        self.assertEqual(test_ids(suite),sorted([first.id(),second.id()]))
        self.assertEqual(duplicates,[first.id()])

    def test_failure_cannot_be_overwritten_by_a_second_run(self):
        calls=[]
        class Example(unittest.TestCase):
            def test_case(self):
                calls.append(1)
                self.assertGreater(len(calls),1)
        suite,_=unique_suite(unittest.TestSuite([Example('test_case'),Example('test_case')]))
        result=unittest.TextTestRunner(stream=StringIO(),resultclass=RecordedResult).run(suite)
        self.assertEqual(result.testsRun,1);self.assertFalse(result.wasSuccessful())
        self.assertEqual(next(iter(result.records.values()))['status'],'FAIL')

    def test_conflicting_classes_with_same_id_are_rejected(self):
        class First(unittest.TestCase):
            def runTest(self):pass
            def id(self):return 'collision'
        class Second(First):pass
        with self.assertRaises(ValueError):unique_suite(unittest.TestSuite([First(),Second()]))
