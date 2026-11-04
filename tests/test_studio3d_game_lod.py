import unittest
from modules.skills.studio3d.game_lod import validate

class GameLODContract(unittest.TestCase):
    def test_structured_middle_level_has_its_own_bounds(self):
        cfg={'level':2,'triangle_budget':3000,'texture_size':512,'ray_distance':.03,'geometry_mode':'structured'}
        self.assertEqual(validate(cfg),cfg)
        for patch in [{'level':0},{'level':3},{'triangle_budget':999},{'triangle_budget':4001}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):validate({**cfg,**patch})
    def test_deliberate_lod3_silhouette_is_separate_from_projection_reduction(self):
        cfg={'level':3,'triangle_budget':900,'texture_size':512,'ray_distance':.03,'geometry_mode':'silhouette'}
        self.assertEqual(validate(cfg),cfg)
        for patch in [{'level':0},{'level':2},{'triangle_budget':99},{'triangle_budget':2001},{'geometry_mode':'arbitrary'}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):validate({**cfg,**patch})

    def test_all_four_levels_accept_independent_budgets(self):
        for level,budget,size in [(0,60000,2048),(1,30000,2048),(2,12000,1024),(3,5000,512)]:
            cfg={'level':level,'triangle_budget':budget,'texture_size':size,'ray_distance':.03}
            self.assertEqual(validate(cfg),cfg)

    def test_unbounded_or_ambiguous_controls_are_rejected(self):
        cfg={'level':0,'triangle_budget':60000,'texture_size':2048,'ray_distance':.03}
        for patch in [{'level':4},{'level':True},{'triangle_budget':999},{'triangle_budget':100001},{'triangle_budget':False},{'texture_size':8192},{'ray_distance':float('nan')},{'ray_distance':float('inf')},{'ray_distance':True},{'code':'arbitrary'},{'source':'another-file.blend'}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):validate({**cfg,**patch})

if __name__=='__main__':unittest.main()
