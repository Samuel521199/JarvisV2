import math,unittest
from collections import Counter
from modules.skills.studio3d.trail_pad import footprint,validate

class TrailPad(unittest.TestCase):
    def test_rounded_surface_and_closed_shell(self):
        for length,width,radius in ((.26,.086,.012),(.32,.086,.012),(.045,.064,.008)):
            ps,fs,loop=footprint(length,width,radius)
            self.assertEqual(len(loop),len(set(loop)))
            for x,y in ps:
                self.assertLessEqual(abs(x),length/2+1e-12);self.assertLessEqual(abs(y),width/2+1e-12)
                q=max(0,abs(x)-length/2+radius);r=max(0,abs(y)-width/2+radius)
                self.assertLessEqual(q*q+r*r,radius*radius+1e-12)
            count=len(ps);shell=[list(reversed(f)) for f in fs]+[[i+count for i in f] for f in fs]+[[a,b,b+count,a+count] for a,b in zip(loop,loop[1:]+loop[:1])]
            edges=Counter(tuple(sorted((a,b))) for f in shell for a,b in zip(f,f[1:]+f[:1]))
            self.assertEqual(set(edges.values()),{2})
            self.assertEqual(2*count-len(edges)+len(shell),2)
    def test_all_cells_have_positive_area(self):
        for n in (4,8,16):
            ps,fs,_=footprint(.28,.086,.012,n,12)
            for f in fs:
                area=sum(ps[a][0]*ps[b][1]-ps[a][1]*ps[b][0] for a,b in zip(f,f[1:]+f[:1]))/2
                self.assertGreater(area,1e-10)
    def test_invalid_shapes(self):
        for args in ((.01,.086,.012),(.4,.086,.012),(.28,.01,.012),(.28,.086,.08),(math.nan,.08,.01),(True,.08,.01)):
            with self.assertRaises(ValueError):footprint(*args)
    def test_sampling_budget(self):
        for nx,ny in ((3,12),(21,12),(16,17),(True,12)):
            with self.assertRaises(ValueError):footprint(.28,.086,.012,nx,ny)
    def test_fixed_frame_and_scalar_contract(self):
        c={'schema':'jarvis.studio3d.trail-pad.v1','author':'Codex','evidence':'Bound test','source_sha256':'a'*64,'pad_length':.28,'targets':[],'inspection':{'views':[{'id':'rear','direction':[-1,1,1]},{'id':'top','direction':[0,0,1]}],'bounds':[[-3,-2,0],[0,2,1]],'resolution':[960,640],'samples':12,'regions':{'pad':['trail-handle-left-2']}}}
        for side in ('left','right'):
            c['targets'].append({'object':'trail-strap-details-'+side,'dependency_digest':'b'*64,'support':'trail-tube-'+side,'support_dependency_digest':'c'*64,'grips':{'trail-handle-'+side+'-'+str(i):'d'*64 for i in range(3)}})
        names=[t['object'] for t in c['targets']]+[t['support'] for t in c['targets']]+[n for t in c['targets'] for n in t['grips']]
        self.assertEqual(validate(c,names)['pad_length'],.28)
        c['inspection']['focus_region']='pad'
        with self.assertRaises(ValueError):validate(c,names)
        c['inspection'].pop('focus_region');c['pad_length']=.4
        with self.assertRaises(ValueError):validate(c,names)
    def test_contract_rejects_unknown_or_missing_fields(self):
        for c in ({},{'schema':'jarvis.studio3d.trail-pad.v1'},None):
            with self.assertRaises(ValueError):validate(c,[])

if __name__=='__main__':unittest.main()
