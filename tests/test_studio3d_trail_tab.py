import math,unittest,copy
from collections import Counter
from modules.skills.studio3d.trail_tab import shape,validate,SCHEMA

class TrailTab(unittest.TestCase):
    def test_closed_surface_with_one_visible_slot(self):
        for d in (.125,.135,.145):
            vs,fs=shape(d);edges=Counter(tuple(sorted((a,b))) for f in fs for a,b in zip(f,f[1:]+f[:1]))
            self.assertEqual(set(edges.values()),{2})
            self.assertEqual(len(vs)-len(edges)+len(fs),0)
            self.assertTrue(all(-d-1e-9<=p[1]<=-.012+1e-9 and abs(p[0])<=.020000001 and abs(p[2])==.006 for p in vs))
    def test_each_surface_has_area(self):
        for d in (.125,.14,.145):
            vs,fs=shape(d)
            for f in fs:
                a,b,c=[vs[i] for i in f[:3]];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)];cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
                self.assertGreater(sum(x*x for x in cross),1e-20)
    def test_limits(self):
        for x in (True,.12,.15,math.inf,math.nan,'0.14'):
            with self.assertRaises(ValueError):shape(x)
    def contract(self):
        c={'schema':SCHEMA,'author':'Codex','evidence':'Bound visible tab test','source_sha256':'a'*64,'extension':.14,'targets':[],'inspection':{'views':[{'id':'left','direction':[0,1,0]},{'id':'rear','direction':[-1,1,1]}],'bounds':[[-3,-2,0],[0,2,1]],'resolution':[960,640],'samples':12,'regions':{'tab':['trail-handle-left-2']}}};names=['trail-handle-left-2']
        for side,starts in (('left',(792,1888,2984)),('right',(944,2040,3136))):
            n='trail-strap-details-'+side;s='trail-tube-'+side;names.extend([n,s,'trail-collars-'+side]);c['targets'].append({'object':n,'support':s,'dependency_digest':'b'*64,'support_dependency_digest':'c'*64,'collar_dependency_digest':'d'*64,'components':[list(range(i,i+152)) for i in starts]})
        return c,names
    def test_full_component_binding_and_fixed_bounds(self):
        c,names=self.contract();self.assertEqual(validate(c,names),c)
        c['targets'][1]['components'][0][0]-=1
        with self.assertRaises(ValueError):validate(c,names)
        c,names=self.contract();c['inspection']['focus_region']='tab'
        with self.assertRaises(ValueError):validate(c,names)
    def test_dependency_and_unknown_rejected(self):
        c,names=self.contract();c['targets'][0]['dependency_digest']='bad'
        with self.assertRaises(ValueError):validate(c,names)
        c,names=self.contract();c['unbounded_override']=True
        with self.assertRaises(ValueError):validate(c,names)
        c,names=self.contract();c['targets'][1]=copy.deepcopy(c['targets'][0])
        with self.assertRaises(ValueError):validate(c,names)

if __name__=='__main__':unittest.main()
