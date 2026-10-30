import copy
import json
import tempfile
import unittest
from pathlib import Path
from modules.skills.studio3d.character_priorities import DEFAULT,load,validate
from tools.studio3d_character_priority_review import RENDER_FOR_REFERENCE


class PriorityScope(unittest.TestCase):
    def test_fbx_camera_sides_match_reference_orientation(self):
        self.assertEqual(RENDER_FOR_REFERENCE,{'front':'front','rear':'rear','right':'left','left':'right'})
    def test_other_asset_and_promotion_are_rejected(self):
        with self.assertRaises(ValueError):validate(DEFAULT,'character-other')
        with self.assertRaises(ValueError):validate({**DEFAULT,'automatic_promotion':True},DEFAULT['asset_id'])
        with self.assertRaises(ValueError):validate({**DEFAULT,'python':'dangerous'},DEFAULT['asset_id'])

    def test_source_hash_changes_with_priority_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'priority.json';p.write_text(json.dumps(DEFAULT),encoding='utf8')
            _,first=load(p,DEFAULT['asset_id'])
            value=copy.deepcopy(DEFAULT);value['priorities'].append('侧面轮廓')
            p.write_text(json.dumps(value),encoding='utf8');_,second=load(p,DEFAULT['asset_id'])
            self.assertNotEqual(first,second)

if __name__=='__main__':unittest.main()
