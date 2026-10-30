import unittest
from modules.skills.studio3d.character_contract import parameters
from modules.skills.studio3d.character_head import head_objects
from modules.skills.studio3d.character_recipe import scene
from modules.skills.studio3d.contract import validate


class CharacterHead(unittest.TestCase):
    def test_detail_is_bounded_unique_and_consumable_as_scene_data(self):
        p=parameters();old=scene(p);obj=head_objects(p)
        ids=[o['id'] for o in obj]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(any(n.startswith('back-hair-refined') for n in ids))
        self.assertTrue(any(n.startswith('eye-almond') for n in ids))
        old['objects']=[o for o in old['objects'] if o['id']=='body-continuous']+obj
        validated=validate(old)
        self.assertLessEqual(len(validated['objects']),128)

    def test_head_scale_stays_in_contract_for_supported_extremes(self):
        for scale in (.9,1.15):
            p=parameters();p.update(height=1.8,hair_volume=scale)
            base=scene(p);base['objects']=head_objects(p)
            validate(base)

if __name__=='__main__':unittest.main()
