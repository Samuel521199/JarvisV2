import math,unittest
from modules.skills.studio3d.curve_grip import grip_path

class CurveGrip(unittest.TestCase):
    def test_bounds_endpoints_and_flat_crown(self):
        for r in (.014,.018,.022):
            for sign in (-1,1):
                a=[0,0,0];b=[sign*.1,0,-.006];path=grip_path(a,b,.1,r)
                self.assertEqual(path[0]['co'],a);self.assertEqual(path[-1]['co'],b)
                self.assertTrue(all(path[i]['co'][2]==.1 for i in (2,3)))
                for i in range(5):
                    cp=[path[i]['co'],path[i]['right'],path[i+1]['left'],path[i+1]['co']]
                    for k in range(101):
                        t=k/100;weights=[(1-t)**3,3*(1-t)**2*t,3*(1-t)*t*t,t**3]
                        p=[sum(w*v[j] for w,v in zip(weights,cp)) for j in range(3)]
                        self.assertGreaterEqual(sign*p[0],-1e-12);self.assertLessEqual(sign*p[0],.1+1e-12)
                        self.assertGreaterEqual(p[2],-.006-1e-12);self.assertLessEqual(p[2],.1+1e-12)
    def test_tangent_continuity(self):
        for p in grip_path([0,0,0],[.1,0,0],.1,.018)[1:-1]:
            a=[x-y for x,y in zip(p['co'],p['left'])];b=[x-y for x,y in zip(p['right'],p['co'])]
            self.assertGreater(sum(x*y for x,y in zip(a,b)),0)
            self.assertAlmostEqual(a[0]*b[2]-a[2]*b[0],0,places=12)
    def test_rejects_unbounded_or_nonfinite_radius(self):
        for r in (True,float('nan'),float('inf'),.013,.023):
            with self.assertRaises(ValueError):grip_path([0,0,0],[.1,0,0],.1,r)
    def test_rejects_incompatible_frame(self):
        for b in ([.1,.001,0],[.2,0,0],[.01,0,0]):
            with self.assertRaises(ValueError):grip_path([0,0,0],b,.1,.018)
    def test_rejects_insufficient_or_excessive_height(self):
        for h in (.03,.2,float('nan')):
            with self.assertRaises(ValueError):grip_path([0,0,0],[.1,0,0],h,.018)

if __name__=='__main__':unittest.main()
