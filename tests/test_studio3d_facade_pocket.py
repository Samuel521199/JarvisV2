import unittest
from modules.skills.studio3d.facade_pocket import placement,validate
class FacadePocket(unittest.TestCase):
 def test_blind_floor_and_badge_are_behind_face(self):
  floor,delta=placement(-.7405,.035,-.816,-.805,-.3855)
  self.assertAlmostEqual(floor,-.7055);self.assertAlmostEqual(-.805+delta,floor+.001)
  self.assertGreater(-.816+delta,-.7405+.01)
 def test_refuses_deep_cuts_and_thin_back_walls(self):
  for depth,front in [(.2,-.3855),(.035,-.6)]:
   with self.assertRaises(ValueError):placement(-.7405,depth,-.816,-.805,front)
 def test_no_arbitrary_model_or_boolean_radius(self):
  with self.assertRaises(ValueError):validate({'schema':'jarvis.studio3d.facade-pocket.v1','radius':4},[])
 def test_mirrored_support_requires_bound_front_heads(self):
  names=['rear-cover-body','shaped-rear-cover','breech-recess','rear-seated-cosmetic-fittings']
  c={'schema':'jarvis.studio3d.facade-pocket.v2','author':'Codex','evidence':'visible reference','depth':.035,'bindings':{n:'a'*64 for n in names},'inspection':{},'mirror_facade':True,'remove_front_trim':True}
  with self.assertRaisesRegex(ValueError,'Bound facade objects'):validate(c,names)
 def test_unused_slot_repair_is_not_an_arbitrary_material_command(self):
  c={'schema':'jarvis.studio3d.facade-slot-repair.v1','author':'Jarvis','source_digest':'a'*64,'evidence':'test','inspection':{}}
  with self.assertRaisesRegex(ValueError,'Bound author slot repair'):validate(c,['rear-cover-body'])
