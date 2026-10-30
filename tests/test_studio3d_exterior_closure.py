import unittest,math
from modules.skills.studio3d.exterior_closure import SCHEMA,validate,build,check_source,notch_from_surface
from modules.skills.studio3d.attachment_seat import validate as dispatch

def contract():
 n=['cradle-rails','cradle-trough','barrel'];c={'schema':SCHEMA,'author':'Codex','evidence':'Bound exterior reference and original mesh','target':'cradle-rails','source_digest':'a'*64,'support_digests':{'cradle-trough':'b'*64,'barrel':'c'*64},'cap_depth':.06,'saddle_span':.12,'inspection':{'views':[{'id':'left','direction':[0,1,0]}],'bounds':[[-1,-1,0],[3,1,2]],'resolution':[960,640],'samples':16,'regions':{'cradle':n},'focus_region':'cradle'}};return c,n

class ExteriorClosure(unittest.TestCase):
 def test_notch_uses_local_samples_not_global_bbox(self):
  self.assertAlmostEqual(notch_from_surface([.0517]*3),.0542)
  for radii in ([.0517,.0617,.0517],[.1]*3,[float('nan')]*3,[]):
   with self.assertRaises(ValueError):notch_from_surface(radii)
 def test_dispatch_and_contract_bounds(self):
  c,n=contract();self.assertEqual(dispatch(c,n),c)
  for k,v in [('source_digest','bad'),('target','barrel'),('cap_depth',.081),('saddle_span',float('nan')),('python','bad')]:
   with self.subTest(k=k),self.assertRaises(ValueError):validate({**c,k:v},n)
 def test_support_binding_required(self):
  c,n=contract();c['support_digests'].pop('barrel')
  with self.assertRaises(ValueError):validate(c,n)
 def test_source_bound_envelope(self):
  rows={'cradle-trough':[[-.65,-.115,.895],[.81,.115,1.025]],'barrel':[[-.57,-.07755,1.07245],[2.05,.07755,1.22755]]};self.assertTrue(check_source(rows));rows['barrel'][1][2]=1.3
  with self.assertRaises(ValueError):check_source(rows)
 def test_generated_parts_are_closed_and_non_degenerate(self):
  c,_=contract()
  for p in build(c):
   counts={};vs=p['vertices']
   for f in p['faces']:
    self.assertGreaterEqual(len(f),3);self.assertEqual(len(f),len(set(f)))
    for a,b in zip(f,f[1:]+f[:1]):k=tuple(sorted((a,b)));counts[k]=counts.get(k,0)+1
   self.assertTrue(counts);self.assertTrue(all(v==2 for v in counts.values()),p['role']);self.assertTrue(all(math.isfinite(v) for p in vs for v in p))
 def test_notch_is_not_filled_by_triangle_fan(self):
  c,_=contract();p=next(p for p in build(c) if p['role']=='open-upper-silhouette');vs=p['vertices']
  # Triangles on the end plane must not cover the circular notch centre.
  def cross(a,b,c):return (b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1])
  q=[.605,0,1.14]
  for f in p['faces']:
   if len(f)!=3:continue
   a,b,d=[vs[i] for i in f]
   turns=[cross(a,b,q),cross(b,d,q),cross(d,a,q)]
   self.assertFalse(all(t>1e-9 for t in turns) or all(t< -1e-9 for t in turns))
 def test_addition_is_local_and_new_parts_stay_above_ground(self):
  c,_=contract();vs=[v for p in build(c) for v in p['vertices']]
  self.assertLess(len(vs),5000);self.assertGreater(min(v[0] for v in vs),.58);self.assertLess(max(v[0] for v in vs),.89);self.assertGreater(min(v[2] for v in vs),.88);self.assertLess(max(abs(v[1]) for v in vs),.181)

if __name__=='__main__':unittest.main()
