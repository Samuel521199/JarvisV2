import unittest,copy
from modules.skills.studio3d.microface_cleanup import validate,coplanar,DEPENDENCIES,SCHEMA
class MicrofaceCleanup(unittest.TestCase):
 def valid(self):
  return {'schema':SCHEMA,'author':'Jarvis','evidence':'Actual frozen geometry diagnosis','source_sha256':'a'*64,'dependencies':{n:'b'*64 for n in DEPENDENCIES},'small_faces':list(range(94)),'affected_vertices':list(range(260)),'strategy':'merge_then_dissolve','inspection':{'regions':{'muzzle':['muzzle-brake']},'focus_region':'muzzle','views':[{'id':'left','direction':[0,1,0],'lighting':'neutral'},{'id':'front','direction':[1,.2,.12],'lighting':'neutral'}],'bounds':[[1.5,-.12,1],[3,.12,1.4]],'resolution':[960,640],'samples':12}}
 def test_complete_diagnosed_input_and_finite_strategy(self):
  c=self.valid();self.assertEqual(validate(c,DEPENDENCIES),c)
  for strategy in ('dissolve_only','merge_only'):c['strategy']=strategy;self.assertEqual(validate(c,DEPENDENCIES),c)
 def test_source_and_neighbors_required(self):
  for key in ('source_sha256','dependencies'):
   c=self.valid();c.pop(key)
   with self.assertRaises(ValueError):validate(c,DEPENDENCIES)
  c=self.valid();c['dependencies'].pop('barrel-band-2')
  with self.assertRaises(ValueError):validate(c,DEPENDENCIES)
 def test_incomplete_repeated_boolean_or_out_of_range_binding_rejected(self):
  for key,limit in [('small_faces',4900),('affected_vertices',5312)]:
   for value in ([-1],list(range(2)),[0]*94,[True]*260,[limit]*260):
    c=self.valid();c[key]=value
    with self.assertRaises(ValueError):validate(c,DEPENDENCIES)
 def test_no_arbitrary_merge_or_gate_controls(self):
  for key,value in [('merge_distance',.1),('area_threshold',.001),('allow_open',True)]:
   c=self.valid();c[key]=value
   with self.assertRaises(ValueError):validate(c,DEPENDENCIES)
  c=self.valid();c['strategy']='global_decimate'
  with self.assertRaises(ValueError):validate(c,DEPENDENCIES)
 def test_plane_classification_and_strict_distance(self):
  self.assertTrue(coplanar([[0,0,0],[0,1,1],[0,-1,3]],[1,0,0],[0,0,0]));self.assertFalse(coplanar([[2e-7,0,0]],[1,0,0],[0,0,0]))
  self.assertFalse(coplanar([[.1,0,0]],[0,0,0],[0,0,0]));self.assertFalse(coplanar([[float('nan'),0,0]],[1,0,0],[0,0,0]));self.assertFalse(coplanar([[0,0]],[1,0,0],[0,0,0]))
