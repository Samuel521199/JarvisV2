import json,sqlite3,tempfile,unittest
from pathlib import Path
from control.recovery.gate import RunLock
from sdk.protocol import CoreError
from tools.recovery_snapshot import snapshot,restore


class RecoverySnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve()
        self.root=self.base/'data';(self.root/'state').mkdir(parents=True)
        db=sqlite3.connect(self.root/'state/test.sqlite3')
        try:db.execute('CREATE TABLE facts(value)');db.execute("INSERT INTO facts VALUES('current correction')");db.commit()
        finally:db.close()
        (self.root/'state/STOP').write_text('generation-preserved')
        self.assets=self.base/'assets';self.assets.mkdir();(self.assets/'part.bin').write_bytes(b'original model bytes')

    def capture(self):return snapshot({'daily':self.root,'assets':self.assets},self.base/'backup',managed_root=self.root,missing_projects=['missing-old-project'])

    def test_round_trip_preserves_data_assets_and_stop_without_starting(self):
        result=self.capture();out=restore(self.base/'backup',self.base/'restored')
        self.assertEqual(result['files'],3);self.assertTrue(out['byte_exact']);self.assertFalse(out['work_started'])
        self.assertEqual((self.base/'restored/daily/state/STOP').read_text(),'generation-preserved')
        self.assertEqual((self.base/'restored/assets/part.bin').read_bytes(),b'original model bytes')
        self.assertEqual(out['missing_projects'],['missing-old-project'])

    def test_live_managed_writer_blocks_capture(self):
        with RunLock(self.root,'workbench-host'):
            with self.assertRaises(CoreError) as error:self.capture()
        self.assertEqual(error.exception.code,'busy')
        self.assertFalse((self.base/'backup').exists())

    def test_tampered_file_rejected_before_creating_restore(self):
        self.capture();(self.base/'backup/assets/part.bin').write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'content changed'):restore(self.base/'backup',self.base/'restored')
        self.assertFalse((self.base/'restored').exists())

    def test_path_traversal_rejected_and_existing_destination_untouched(self):
        self.capture();manifest=self.base/'backup/snapshot.json';d=json.loads(manifest.read_text());d['files'][0]['path']='../../escape'
        manifest.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'Unsafe'):restore(self.base/'backup',self.base/'restored')
        self.assertFalse((self.base/'escape').exists())

    def test_snapshot_inside_source_and_restore_over_existing_tree_refused(self):
        with self.assertRaises(ValueError):snapshot({'daily':self.root},self.root/'backup',managed_root=self.root)
        self.capture()
        with self.assertRaises(FileExistsError):restore(self.base/'backup',self.assets)
        self.assertEqual((self.assets/'part.bin').read_bytes(),b'original model bytes')

    def test_wal_database_integrity_read_adds_no_restore_sidecars(self):
        db=sqlite3.connect(self.root/'state/test.sqlite3')
        try:db.execute('PRAGMA journal_mode=WAL');db.execute("INSERT INTO facts VALUES('new fact')");db.commit()
        finally:db.close()
        self.capture();restore(self.base/'backup',self.base/'restored')
        self.assertEqual(list((self.base/'restored').rglob('*-wal')),[])
        self.assertEqual(list((self.base/'restored').rglob('*-shm')),[])
