"""Exterior candidate checks, not historical or mechanical certification."""
import unittest
from unittest.mock import patch
from modules.skills.studio3d.artillery_recipe import PARAMETERS, VARIANTS, build


class RearDetailThreeTests(unittest.TestCase):
    def test_rear_variant_preserves_original_and_declares_ownership(self):
        spec=PARAMETERS['rear_detail']
        with patch.dict(PARAMETERS,{'rear_detail':(*spec[:2],3,*spec[3:])}):
            source,old_sem=build({'rear_detail':2,'control_detail':2})
            result,sem=build({'rear_detail':3,'control_detail':2})
        old={o['id']:o for o in source['objects']};new={o['id']:o for o in result['objects']}
        self.assertEqual(set(new)-set(old),{'rear-seated-cosmetic-fittings'})
        self.assertEqual(sem['groups']['rear-seated-cosmetic-fittings'],'breech')
        self.assertEqual(sem['motion_owners']['rear-seated-cosmetic-fittings'],'breech')
        for name in set(old)-{'fasteners-breech'}:self.assertEqual(old[name],new[name],name)
        # A geometric bounding check only; inspect visible contact with renders.
        points=new['rear-seated-cosmetic-fittings']['params']['vertices']
        face=-.59-.4/2
        self.assertLess(min(v[0] for v in points),face)
        self.assertGreater(max(v[0] for v in points),face)
        self.assertGreater(max(v[1] for v in points),.125)
        self.assertLess(min(v[1] for v in points),-.125)

    def test_bounded_variants_and_contract_budget(self):
        spec=PARAMETERS['rear_detail']
        with patch.dict(PARAMETERS,{'rear_detail':(*spec[:2],3,*spec[3:])}):
            with self.assertRaises(ValueError):build({'rear_detail':4})
            build({'wheel_ribs':12,'track':2.3,'shield_width':2.15,'trail_spread':1.65,
                   **{k:PARAMETERS[k][2] for k in VARIANTS}})

if __name__=='__main__':unittest.main()
