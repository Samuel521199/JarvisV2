import unittest,copy
from modules.skills.studio3d.evaluated_shading import retained_plane,validate,front_faces,PLANAR_DEPENDENCIES
class EvaluatedShading(unittest.TestCase):
 def test_original_planes_stay_flat_including_slanted_planes(self):
  s=2**-.5;n=(s,0,s);plane=(n,s)
  self.assertTrue(retained_plane([[1,0,0],[0,1,1],[0,0,1]],n,[plane]))
  self.assertFalse(retained_plane([[.9,0,0],[0,1,.9],[0,0,.9]],n,[plane]))
  self.assertFalse(retained_plane([[1,0,0]],[-s,0,-s],[plane]))
 def test_rejects_arbitrary_objects_and_duplicate_targets(self):
  c={'schema':'jarvis.studio3d.evaluated-shading.v1','author':'Codex','evidence':'actual flat bevel diagnosis','targets':[{'object':'other','source_digest':'a'*64}],'inspection':{}}
  with self.assertRaises(ValueError):validate(c,['other'])
  c['targets']=[{'object':'rear-cover-body','source_digest':'a'*64}]*2
  with self.assertRaises(ValueError):validate(c,['rear-cover-body'])
 def planar(self):
  return {'schema':'jarvis.studio3d.evaluated-shading.v2','author':'Jarvis','evidence':'Actual planar surface and modifier-stage audit','source_sha256':'a'*64,'dependencies':{n:'b'*64 for n in PLANAR_DEPENDENCIES},'front_face_indices':list(range(96)),'inspection':{'regions':{'muzzle':['muzzle-brake']},'focus_region':'muzzle','views':[{'id':'left','direction':[0,1,0],'lighting':'neutral'},{'id':'front','direction':[1,.2,.12],'lighting':'neutral'}],'bounds':[[1.5,-.12,1],[3,.12,1.4]],'resolution':[960,640],'samples':12}}
 def test_planar_binding_required(self):
  c=self.planar();self.assertEqual(validate(c,PLANAR_DEPENDENCIES),c)
  for key in ('source_sha256','dependencies','front_face_indices'):
   bad=copy.deepcopy(c);bad.pop(key)
   with self.assertRaises(ValueError):validate(bad,PLANAR_DEPENDENCIES)
 def test_operand_and_repeated_face_rejected(self):
  c=self.planar();c['dependencies'].pop('brake-port-1')
  with self.assertRaises(ValueError):validate(c,PLANAR_DEPENDENCIES)
  for v in (-1,4900,True,0):
   c=self.planar();c['front_face_indices'][1]=v
   with self.assertRaises(ValueError):validate(c,PLANAR_DEPENDENCIES)
 def test_cannot_raise_resources_or_choose_arbitrary_region(self):
  for k,v in [('samples',64),('resolution',[2048,2048]),('focus_region','barrel')]:
   c=self.planar();c['inspection'][k]=v
   with self.assertRaises(ValueError):validate(c,PLANAR_DEPENDENCIES)
 def test_only_existing_extreme_planar_surface_selected(self):
  points=[[2,0,0],[2,1,0],[2,0,1],[1,0,0],[1,1,0]];faces=[[0,1,2],[0,3,4],[1,4,3]]
  self.assertEqual(front_faces(points,faces),[0]);points[2][0]=1.999
  self.assertEqual(front_faces(points,faces),[])
 def test_invalid_geometry_rejected(self):
  for points,faces in [([],[]),([[float('nan'),0,0]],[[0,0,0]]),([[1,0,0]],[[0,1,2]])]:
   with self.assertRaises(ValueError):front_faces(points,faces)
