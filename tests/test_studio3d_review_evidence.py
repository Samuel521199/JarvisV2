import tempfile,unittest
from pathlib import Path
from modules.skills.studio3d.review_evidence import candidate_manifest,verify_manifest
from modules.skills.studio3d.hard_surface_review import VIEWS


class ReviewEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.model=self.root/'model.glb';self.model.write_bytes(b'model A')
        self.images={view:self.root/(view+'.png') for view in VIEWS}
        for view,path in self.images.items():path.write_bytes(view.encode())
        self.manifest=candidate_manifest(self.model,self.images,iteration='candidate-A')

    def test_unchanged_candidate_stays_unapproved(self):
        result=verify_manifest(self.manifest,self.images)
        self.assertTrue(result['all_five_render_hashes_verified'])
        self.assertFalse(result['user_approval']);self.assertFalse(result['lod_authorized'])

    def test_replaced_model_invalidates_review(self):
        self.model.write_bytes(b'model B')
        with self.assertRaisesRegex(ValueError,'changed'):verify_manifest(self.manifest)

    def test_overwritten_render_invalidates_review(self):
        self.images['front'].write_bytes(b'different front')
        with self.assertRaisesRegex(ValueError,'changed'):verify_manifest(self.manifest)

    def test_render_from_another_iteration_is_rejected(self):
        other=self.root/'other.png';other.write_bytes(b'different')
        with self.assertRaisesRegex(ValueError,'different candidate'):verify_manifest(self.manifest,{'front':other})

    def test_incomplete_five_view_set_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'five'):candidate_manifest(self.model,{'front':self.images['front']},iteration='B')
