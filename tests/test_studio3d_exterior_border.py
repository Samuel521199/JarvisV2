import unittest,math
from collections import Counter
from modules.skills.studio3d.exterior_border import geometry
class ExteriorBorder(unittest.TestCase):
 def test_closed_bounded_surface_preserves_hole_corridor(self):
  for radius in (.005,.0065,.008):
   vs,fs,uv,path=geometry(radius);edges=Counter(tuple(sorted((a,b))) for f in fs for a,b in zip(f,f[1:]+f[:1]));self.assertEqual(set(edges.values()),{2})
   self.assertEqual(len(fs),len(uv));self.assertTrue(all(1.0574<p[2]<1.1626 for p in vs));self.assertTrue(all(-1.0126<p[0]<-.5299 for p in vs))
   self.assertTrue(all(math.hypot(x+.765,z-1.11)-radius>.034 for x,z in path))
 def test_rejects_unbounded_or_nonfinite_controls(self):
  for radius in (True,float('nan'),float('inf'),-.01,0,.0049,.0081):
   with self.assertRaises(ValueError):geometry(radius)
if __name__=='__main__':unittest.main()
