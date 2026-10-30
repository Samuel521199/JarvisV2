import math,unittest
from modules.skills.studio3d.collar_profile import SCHEMA,TARGETS,validate,fit,profile,build,face_uv
from modules.skills.studio3d.annular_detail import validate as dispatch
from modules.skills.studio3d.assembly_geometry import Mesh

class CollarProfile(unittest.TestCase):
 def config(self):return {'schema':SCHEMA,'author':'Codex','evidence':'Actual source and visible outer shoulders','source_digests':{n:'a'*64 for n in TARGETS},'neck_radius':.101,'shoulder_width':.024,'inspection':{'views':[{'id':'front','direction':[1,0,0]}],'bounds':[[-1,-1,0],[1,1,1]],'resolution':[960,640],'samples':12,'regions':{'band':list(TARGETS)}}}
 def test_envelope_and_source_scope(self):
  c=self.config();names=list(TARGETS)+['axle'];self.assertEqual(dispatch(c,names),c)
  for k,v in [('neck_radius',.09),('shoulder_width',.04),('neck_radius',float('nan')),('source_digests',{})]:
   with self.assertRaises(ValueError):validate({**c,k:v},names)
 def test_original_fit_and_changed_source_rejection(self):
  for side in (-1,1):
   m=Mesh();m.tube([0,side*.64,.5],[0,side*.855,.5],.12,48);fit(m.vertices,m.faces,side)
   v,f=build(self.config(),side)
   with self.assertRaises(ValueError):fit(v,f,side)
 def test_closed_connected_finite_surface_and_ends(self):
  for side in (-1,1):
   v,f=build(self.config(),side);edges={};volume=0
   for face in f:
    for a,b in zip(face,face[1:]+face[:1]):k=tuple(sorted((a,b)));edges[k]=edges.get(k,0)+1
    for j in range(1,len(face)-1):
     a,b,c=(v[i] for i in (face[0],face[j],face[j+1]));volume+=sum(a[k]*(b[(k+1)%3]*c[(k+2)%3]-b[(k+2)%3]*c[(k+1)%3]) for k in range(3))/6
   self.assertTrue(all(n==2 for n in edges.values()));self.assertGreater(volume,0);self.assertEqual(len(v),2178)
   self.assertAlmostEqual(min(abs(p[1]) for p in v),.64);self.assertAlmostEqual(max(abs(p[1]) for p in v),.855)
 def test_profiles_preserve_end_caps_and_maximum_radius(self):
  for neck in (.098,.108):
   for width in (.018,.028):
    c=self.config()|{'neck_radius':neck,'shoulder_width':width};p=profile(c)
    self.assertEqual(p[0],(0.,.1104));self.assertEqual(p[-1],(.215,.1104));self.assertTrue(all(b[0]>a[0] for a,b in zip(p,p[1:])));self.assertEqual(max(r for _,r in p),.12);self.assertGreater(min(r for _,r in p),.087)
 def test_caps_and_strip_have_positive_uv_face_area(self):
  for side in (-1,1):
   v,fs=build(self.config(),side)
   for face in fs:
    points=[v[i] for i in face];uv=face_uv(points);area=abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(uv,uv[1:]+uv[:1])))/2
    self.assertGreater(area,1e-10)
    self.assertTrue(all(-1e-7<=x<=1+1e-7 for p in uv for x in p))
if __name__=='__main__':unittest.main()
