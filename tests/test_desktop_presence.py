"""Optional shell integrity and role permissions; never launches a GUI."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from apps.desktop.prepare import prepare
from apps.desktop.launcher import prepared

ROOT=Path(__file__).resolve().parents[1]
class DesktopPresence(unittest.TestCase):
    def test_reviewed_registration_includes_all_native_boundary_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'data';root.mkdir();binary=Path(folder)/'fixture.exe';binary.write_bytes(b'not-executed-test-fixture'*5000)
            prepare(root,binary);self.assertEqual(hashlib.sha256(prepared(root).read_bytes()).hexdigest(),hashlib.sha256(binary.read_bytes()).hexdigest())
            record=json.loads((root/'optional/desktop-presence/prepared.json').read_text());self.assertEqual(record['protocol'],2)
            self.assertTrue({'apps/desktop/build.rs','apps/desktop/tauri.conf.json','apps/desktop/src/regions.rs'}<=record['source_sha256'].keys())
            prepared(root).write_bytes(b'changed')
            with self.assertRaises(ValueError):prepared(root)
    def test_escaped_executable_and_legacy_protocol_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);base=root/'optional/desktop-presence';base.mkdir(parents=True)
            path=base/'prepared.json';outside=root/'outside.exe';outside.write_bytes(b'synthetic')
            for record in [{'schema':1,'protocol':1,'file':'legacy.exe'},
                           {'schema':1,'protocol':2,'file':'../../outside.exe','sha256':hashlib.sha256(outside.read_bytes()).hexdigest()}]:
                path.write_text(json.dumps(record))
                with self.assertRaises(ValueError):prepared(root)
    def test_remote_capabilities_are_bound_to_own_window_and_page(self):
        cfg=json.loads((ROOT/'apps/desktop/tauri.conf.json').read_text());dock,robot=cfg['app']['security']['capabilities']
        self.assertEqual(dock['windows'],['presence']);self.assertEqual(robot['windows'],['robot'])
        self.assertEqual(dock['remote']['urls'],['http://127.0.0.1:*/companion/native'])
        self.assertEqual(robot['remote']['urls'],['http://127.0.0.1:*/companion/native-robot'])
        self.assertNotIn('allow-presence-drag',dock['permissions']);self.assertNotIn('allow-presence-workbench',robot['permissions'])
        self.assertTrue(all(p.startswith('allow-presence-') for c in (dock,robot) for p in c['permissions']))

if __name__=='__main__':unittest.main()
