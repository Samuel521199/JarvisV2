import unittest,copy
from modules.skills.studio3d.panel_corner import validate

class PanelCornerTests(unittest.TestCase):
 def setUp(self):
  self.names=['panel','fasteners'];self.c={'schema':'jarvis.studio3d.panel-corner.v1','author':'Codex','evidence':'Reference rounded outer corner, verified matching open source corner','targets':[{'object':'panel','corners':[{'index':13,'world_position':[.16,.89,.53]}]}],'anchors':['fasteners'],'offset':.04,'segments':8,'max_anchor_distance_increase':.0005,'inspection':{'views':[{'id':'front','direction':[1,0,0]}],'bounds':[[-3,-2,0],[3,2,2]],'resolution':[960,640],'samples':16,'regions':{'shield':['panel']},'focus_region':'shield'}}
 def test_accepts_explicit_bound_target(self):self.assertIs(validate(self.c,self.names),self.c)
 def test_parameters_cannot_expand_scope(self):
  for k,v in [('offset',.5),('offset',float('nan')),('segments',128),('max_anchor_distance_increase',.001),('author','other')]:
   c=copy.deepcopy(self.c);c[k]=v
   with self.assertRaises(ValueError):validate(c,self.names)
 def test_coordinate_binding_is_required(self):
  for corner in [{'index':-1,'world_position':[0,0,0]},{'index':13,'world_position':[0,0,float('inf')]},{'index':13}]:
   c=copy.deepcopy(self.c);c['targets'][0]['corners']=[corner]
   with self.assertRaises(ValueError):validate(c,self.names)
 def test_duplicate_targets_and_moving_anchors_rejected(self):
  c=copy.deepcopy(self.c);c['targets']*=2
  with self.assertRaises(ValueError):validate(c,self.names)
  c=copy.deepcopy(self.c);c['anchors']=['panel']
  with self.assertRaises(ValueError):validate(c,self.names)
 def test_unexpected_fields_and_unknown_names(self):
  c=copy.deepcopy(self.c);c['code']='print(1)'
  with self.assertRaises(ValueError):validate(c,self.names)
  with self.assertRaises(ValueError):validate(self.c,['panel'])
