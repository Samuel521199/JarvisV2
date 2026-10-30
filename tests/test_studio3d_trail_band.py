import math,unittest
from collections import Counter
from modules.skills.studio3d.trail_band import fit,geometry,frame,add,mul,validate,SCHEMA

def fixture(kind,axis):
    a,u,v=frame(axis);center=[-1.3,.7,.3];profile=[[.003*math.sin(i*math.tau/20),.089+.003*math.cos(i*math.tau/20)] for i in range(20)] if kind=='bead' else [[-.018,.081],[-.0162,.088],[.0162,.088],[.018,.081]];n=16 if kind=='bead' else 32;points=[]
    for h,r in profile:
        for i in range(n):points.append(add(center,add(mul(a,h),add(mul(u,r*math.cos(i*math.tau/n)),mul(v,r*math.sin(i*math.tau/n))))))
    if kind=='collar':points.extend([add(center,mul(a,h)) for h in (-.018,.018)])
    return points

class TrailBand(unittest.TestCase):
    def test_measured_profile_preserves_radius_and_center_under_axes(self):
        for kind in ('bead','collar'):
            for axis in ([-2.6,1.2,-.29],[-2.6,-1.2,-.29]):
                p=fit(fixture(kind,axis),axis,kind);self.assertLess(p['fit_error'],1e-12)
                self.assertAlmostEqual(p['center'][0],-1.3,places=12);self.assertAlmostEqual(max(x[1] for x in p['profile']),.092 if kind=='bead' else .088,places=12)
    def test_closed_topology_and_positive_uv(self):
        for kind in ('bead','collar'):
            p=fit(fixture(kind,[-2.6,1.2,-.29]),[-2.6,1.2,-.29],kind)
            for n in (64,96,128):
                vs,fs,uv,sm=geometry(p,n);edges=Counter(tuple(sorted((a,b))) for f in fs for a,b in zip(f,f[1:]+f[:1]));self.assertEqual(set(edges.values()),{2});self.assertEqual(len(vs)-len(edges)+len(fs),0 if kind=='bead' else 2)
                for ps in uv:self.assertGreater(abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(ps,ps[1:]+ps[:1])))/2,1e-10)
    def test_nonuniform_original_rejected(self):
        ps=fixture('bead',[-2.6,1.2,-.29]);ps[0][0]+=.001
        with self.assertRaises(ValueError):fit(ps,[-2.6,1.2,-.29],'bead')
    def test_missing_and_deformed_sleeve_rejected(self):
        ps=fixture('collar',[-2.6,1.2,-.29])
        with self.assertRaises(ValueError):fit(ps[:-1],[-2.6,1.2,-.29],'collar')
        ps[2][1]+=.01
        with self.assertRaises(ValueError):fit(ps,[-2.6,1.2,-.29],'collar')
    def test_sampling_budget(self):
        p=fit(fixture('bead',[-2.6,1.2,-.29]),[-2.6,1.2,-.29],'bead')
        for n in (True,16,48,256,96.0):
            with self.assertRaises(ValueError):geometry(p,n)
    def contract(self):
        c={'schema':SCHEMA,'author':'Codex','evidence':'Original profile diagnostic','source_sha256':'a'*64,'segments':96,'targets':[],'inspection':{'views':[{'id':'left','direction':[0,1,0]},{'id':'rear','direction':[-1,1,1]}],'bounds':[[-3,1,0],[-2,2,1]],'resolution':[960,640],'samples':12,'regions':{'band':['trail-handle-left-2']}}};names=['trail-handle-left-2']
        for s in ('left','right'):
            c['targets'].append({'side':s,'strap_digest':'b'*64,'collar_digest':'c'*64,'tube_digest':'d'*64,'bead_components':[list(range(i,i+320)) for i in (0,320,1096,1416,2192,2512)]});names.extend([n+'-'+s for n in ('trail-strap-details','trail-collars','trail-tube')])
        return c,names
    def test_bound_whole_components(self):
        c,names=self.contract();self.assertEqual(validate(c,names),c);c['targets'][0]['bead_components'][0].pop()
        with self.assertRaises(ValueError):validate(c,names)
    def test_unknown_fields_and_implicit_frame_rejected(self):
        c,names=self.contract();c['inspection']['focus_region']='band'
        with self.assertRaises(ValueError):validate(c,names)
        c,names=self.contract();c['radius_override']=.15
        with self.assertRaises(ValueError):validate(c,names)

if __name__=='__main__':unittest.main()
