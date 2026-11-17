"""Only exact model digests and unambiguous lineage may merge model feedback."""
import json,sqlite3,tempfile,unittest
from pathlib import Path
from host.work_artifact_context import model_links


class ModelWorkContext(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'model-library').mkdir();(self.root/'state').mkdir()
        self.db=sqlite3.connect(self.root/'model-library/catalog.sqlite3');self.addCleanup(self.db.close)
        self.db.executescript('CREATE TABLE assets(id TEXT,body TEXT);CREATE TABLE files(asset_id TEXT,sha256 TEXT,ext TEXT);')
        self.db.execute('INSERT INTO assets VALUES(?,?)',('pak38',json.dumps({'name':'PaK38'})));self.db.execute('INSERT INTO files VALUES(?,?,?)',('pak38','a'*64,'.glb'));self.db.commit()
        self.jobs=sqlite3.connect(self.root/'state/studio3d.sqlite3');self.addCleanup(self.jobs.close);self.jobs.execute('CREATE TABLE jobs(id TEXT,receipt TEXT,created REAL)')

    def job(self,name,source,outputs):
        body={'skill':'studio3d','title':'Same display name','input_asset':{'sha256':source},'files':{str(i)+'.blend':{'sha256':sha} for i,sha in enumerate(outputs)}}
        self.jobs.execute('INSERT INTO jobs VALUES(?,?,?)',(name,json.dumps(body),10));self.jobs.commit()

    def test_exact_lineage_connects_saved_asset_steps_and_read_only_inspection(self):
        self.job('first','a'*64,['b'*64]);self.job('second','b'*64,['c'*64]);self.job('inspect','c'*64,[])
        found=model_links(self.root)
        self.assertEqual(set(found),{'first','second','inspect'});self.assertTrue(all(v==('pak38','PaK38') for v in found.values()))

    def test_same_title_without_shared_digest_is_not_a_model_identity(self):
        self.job('unrelated','f'*64,['e'*64]);self.assertEqual(model_links(self.root),{})

    def test_lineage_shared_by_two_library_assets_is_left_unassigned(self):
        self.job('first','a'*64,['b'*64]);self.db.execute('INSERT INTO assets VALUES(?,?)',('other',json.dumps({'name':'Other'})));self.db.execute('INSERT INTO files VALUES(?,?,?)',('other','b'*64,'.blend'));self.db.commit()
        self.assertEqual(model_links(self.root),{})
