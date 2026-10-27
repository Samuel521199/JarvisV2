import unittest
from unittest.mock import patch
import test_knowledge as fixtures
from modules.context_knowledge.health import inspect
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.vectors import Vectors
from host import memory
from sdk.protocol import canonical,CoreError


class Health(unittest.TestCase):
    setUp=fixtures.Library.setUp
    tearDown=fixtures.Library.tearDown
    source=fixtures.Library.source

    def test_scope_counts_do_not_disclose_other_source_text_and_do_not_write(self):
        self.source('private canary alpha')
        Knowledge(self.core.db).save(dict(id='',scope='project-other',title='other',text='other scope secret',providers=[],paused=True),0)
        before=list(self.core.db.connection.iterdump())
        report=memory.command(self.root,{'action':'health','scope':'personal'})
        self.assertEqual(report['counts']['sources'],1);self.assertEqual(report['issues'],[])
        self.assertNotIn('canary',canonical(report));self.assertNotIn('other scope secret',canonical(report))
        self.assertEqual(before,list(self.core.db.connection.iterdump()))
        with self.assertRaises(CoreError):memory.command(self.root,{'action':'health','scope':'joint:personal,unknown'})

    def test_projection_hole_detected_then_existing_rebuild_repairs_it(self):
        self.source();library=Knowledge(self.core.db);library.rebuild();slot=library.slot()
        self.core.db.connection.execute(f'DELETE FROM {slot}')
        report=inspect(self.core.db,'personal');self.assertFalse(report['fts']['consistent'])
        self.assertEqual(report['issues'][0]['code'],'fts_coverage')
        library.rebuild();self.assertEqual(inspect(self.core.db,'personal')['issues'],[])

    def test_old_vector_recipe_is_visible_without_querying_model(self):
        self.source()
        with patch('modules.context_knowledge.vectors.RECIPE','legacy'):
            Vectors(self.core.db).build('A',2,lambda texts:[[1.,0.] for _ in texts])
        result=inspect(self.core.db,'personal')
        self.assertTrue(result['vectors']['stale']);self.assertFalse(result['vectors']['recipe_current'])

if __name__=='__main__':unittest.main()
