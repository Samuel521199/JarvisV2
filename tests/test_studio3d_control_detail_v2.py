"""Bounded game-art control assembly; not a mechanical validity test."""
import unittest
from unittest.mock import patch
from modules.skills.studio3d.artillery_recipe import PARAMETERS, build


class ControlDetailVariantTests(unittest.TestCase):
    def test_variant_adds_seated_fixed_casting_and_keeps_the_wheel_independent(self):
        spec=PARAMETERS['control_detail']
        with patch.dict(PARAMETERS,{'control_detail':(spec[0],spec[1],2,spec[3],spec[4])}):
            baseline,base_sem=build({'control_detail':1})
            candidate,sem=build({'control_detail':2})
        old={o['id']:o for o in baseline['objects']};new={o['id']:o for o in candidate['objects']}
        self.assertEqual(set(new)-set(old),{'control-seated-castings','control-seated-trim'})
        for name in ('control-seated-castings','control-seated-trim'):
            self.assertEqual(sem['groups'][name],'controls')
            self.assertEqual(sem['motion_owners'][name],'controls')
            self.assertGreater(len(new[name]['params']['faces']),0)
        self.assertEqual(old['handwheel-left'],new['handwheel-left'])
        self.assertEqual(sem['motion_owners']['handwheel-left'],'handwheel-left')
        # The casting reaches the existing handwheel shaft housing and base;
        # this bounds-only assertion does not prove real contact or clearances.
        vertices=new['control-seated-castings']['params']['vertices']
        self.assertLessEqual(min(v[2] for v in vertices),.7975)
        self.assertGreaterEqual(max(v[2] for v in vertices),.9)
        self.assertLessEqual(min(v[1] for v in vertices),.35)
        self.assertGreaterEqual(max(v[1] for v in vertices),.40)
        for name in set(old)-{'fasteners-controls'}:
            self.assertEqual(old[name],new[name],name)

    def test_rejects_unknown_larger_variant(self):
        spec=PARAMETERS['control_detail']
        with patch.dict(PARAMETERS,{'control_detail':(spec[0],spec[1],2,spec[3],spec[4])}):
            with self.assertRaises(ValueError):build({'control_detail':3})

if __name__=='__main__':unittest.main()
