import copy
import math
import unittest
from modules.skills.studio3d.radial_profile import crown,reprofile
from modules.skills.studio3d.artillery_recipe import pressed_wheel_plate
from modules.skills.studio3d.demonstration import validate
from test_studio3d_demonstration import contract


def action():
    a=contract()['actions'][0]
    a.update(tool='radial_reprofile',center=[0,.975,.5],inner=.20,outer=.44,amplitude=.026,crown_fraction=.16,shoulder_fraction=.28,end_blend=.045)
    return a


class RadialProfileTests(unittest.TestCase):
    def source(self):
        m,_=pressed_wheel_plate(.975,.145,.45,8)
        return m.vertices,m.faces

    def test_closed_manifold_consistent_winding_and_more_detail(self):
        v,f=self.source();out,faces,checks=reprofile(v,f,action());edges={}
        for face in faces:
            for i,j in zip(face,face[1:]+face[:1]):
                key=tuple(sorted((i,j)));edges.setdefault(key,[]).append((i,j))
        self.assertTrue(all(len(e)==2 and e[0]==e[1][::-1] for e in edges.values()))
        self.assertEqual(len(out)-len(edges)+len(faces),0)
        self.assertGreater(len(out),len(v));self.assertLessEqual(checks['max_axial_change'],.06)

    def test_preserves_source_samples_outside_action_and_face_separation(self):
        v,f=self.source();out,_,_=reprofile(v,f,action())
        indexed={tuple(round(x,5) for x in p):p for p in out}
        for p in v:
            r=math.hypot(p[0],p[2]-.5)
            if r<=.20 or r>=.44:
                key=tuple(round(x,5) for x in p)
                self.assertIn(key,indexed)
        self.assertTrue(all(abs(p[1]-.975)>.03 for p in out))

    def test_rejects_holes_irregular_rings_and_unrelated_mesh(self):
        v,f=self.source()
        with self.assertRaises(ValueError):reprofile(v,f[:-1],action())
        v=copy.deepcopy(v);v[0][0]+=.01
        with self.assertRaises(ValueError):reprofile(v,f,action())

    def test_crown_plateau_valley_and_symmetric_shoulders(self):
        a=action()
        self.assertAlmostEqual(crown(0,a),1)
        self.assertAlmostEqual(crown(.10*math.pi/8,a),1)
        self.assertAlmostEqual(crown(math.pi/8,a),0)
        self.assertAlmostEqual(crown(.30*math.pi/8,a),crown(-.30*math.pi/8,a))

    def test_rigid_translation_and_changed_amplitude(self):
        v,f=self.source();a=action();base,_,_=reprofile(v,f,a)
        shift=[1.,-2.,3.];a['center']=[x+y for x,y in zip(a['center'],shift)]
        moved=[[x+y for x,y in zip(p,shift)] for p in v];out,_,_=reprofile(moved,f,a)
        for p,q in zip(base,out):
            for x,y,d in zip(p,q,shift):self.assertAlmostEqual(x+d,y,places=5)
        a=action();a['amplitude']=.018;other,_,_=reprofile(v,f,a)
        self.assertNotEqual(base,other)

    def test_new_contract_bounds(self):
        c=contract();c['actions']=[action()];validate(c,['plate'])
        for key,value in [('crown_fraction',.6),('shoulder_fraction',.01),('end_blend',0),('end_blend',float('nan'))]:
            c=contract();c['actions']=[action()];c['actions'][0][key]=value
            with self.assertRaises(ValueError):validate(c,['plate'])


if __name__=='__main__':unittest.main()
