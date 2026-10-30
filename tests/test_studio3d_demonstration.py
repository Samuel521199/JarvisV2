import copy
import math
import unittest
from modules.skills.studio3d.demonstration import SCHEMA, validate, displacement


def contract():
    return {'schema':SCHEMA,'author':'Codex','goal':'Test a visible radial plate relief','evidence':'Frozen reference and same-camera before/after',
            'actions':[{'tool':'radial_relief','target':'plate','center':[0,0,0],'axis':[0,1,0],'radial_u':[1,0,0],
                        'inner':.1,'outer':.45,'amplitude':.025,'lobes':8,'phase':0,'reason':'Compare actual profile, preserve annular boundary'}],
            'views':[{'id':'plate','center':[0,0,0],'direction':[.2,1,.1],'ortho_scale':1.2}],
            'resolution':[512,512],'samples':8}


class DemonstrationTests(unittest.TestCase):
    def test_valid_contract_is_independent_copy(self):
        c=contract();v=validate(c,['plate']);v['actions'][0]['center'][0]=1
        self.assertEqual(c['actions'][0]['center'][0],0)

    def test_rejects_undeclared_and_duplicate_targets(self):
        c=contract()
        with self.assertRaises(ValueError):validate(c,['different'])
        c['actions'].append(copy.deepcopy(c['actions'][0]))
        with self.assertRaises(ValueError):validate(c,['plate'])

    def test_rejects_code_and_unbounded_parameters(self):
        for key,value in [('amplitude',.1),('lobes',True),('outer',float('nan')),('tool','execute_python'),('axis',[0,2,0]),('radial_u',[0,1,0])]:
            with self.subTest(key=key):
                c=contract();c['actions'][0][key]=value
                with self.assertRaises(ValueError):validate(c,['plate'])
        c=contract();c['actions'][0]['code']='untrusted'
        with self.assertRaises(ValueError):validate(c,['plate'])

    def test_output_names_and_resource_limits(self):
        for name in ('../escaped','a/b','', 'X'):
            c=contract();c['views'][0]['id']=name
            with self.assertRaises(ValueError):validate(c,['plate'])
        for key,value in [('resolution',[4096,4096]),('samples',100),('author','unknown')]:
            c=contract();c[key]=value
            with self.assertRaises(ValueError):validate(c,['plate'])

    def test_preserves_annulus_boundary_and_center_plane(self):
        a=contract()['actions'][0]
        for point in ([.1,.04,0],[.45,.04,0],[.8,.04,0],[.25,0,0]):
            self.assertEqual(displacement(point,a),[0.,0.,0.])

    def test_only_normal_displacement_and_separation(self):
        a=contract()['actions'][0]
        upper=displacement([.275,.04,0],a);lower=displacement([.275,-.04,0],a)
        self.assertEqual(upper[0],0);self.assertEqual(upper[2],0)
        self.assertAlmostEqual(upper[1],.025);self.assertAlmostEqual(lower[1],-.025)

    def test_local_frame_translation_and_scale(self):
        a=contract()['actions'][0];p=[.275,.04,0];expected=displacement(p,a)
        shifted=copy.deepcopy(a);shifted['center']=[2,3,4]
        actual=displacement([p[i]+shifted['center'][i] for i in range(3)],shifted)
        for x,y in zip(expected,actual):self.assertAlmostEqual(x,y)
        scaled=copy.deepcopy(a)
        for key in ('inner','outer','amplitude'):scaled[key]*=2
        actual=displacement([v*2 for v in p],scaled)
        for x,y in zip(expected,actual):self.assertAlmostEqual(x*2,y)

    def test_troughs_keep_existing_seated_fasteners(self):
        a=contract()['actions'][0];t=math.pi/a['lobes'];r=.25
        self.assertEqual(displacement([r*math.cos(t),.04,-r*math.sin(t)],a),[0.,0.,0.])

    def test_positive_envelope_is_bounded(self):
        a=contract()['actions'][0]
        for i in range(40):
            r=.07+i*.012
            for j in range(48):
                t=math.tau*j/48
                delta=displacement([r*math.cos(t),.04,r*math.sin(t)],a)
                self.assertLessEqual(abs(delta[1]),a['amplitude']+1e-10)


if __name__=='__main__':unittest.main()
