import copy
import math
import unittest
from modules.skills.studio3d.control_face_roll import validate, front_stations, SCHEMA, NAMES
from modules.skills.studio3d.attachment_seat import validate as route

def contract():
    return {'schema':SCHEMA,'author':'Jarvis','evidence':'Bound original comparison',
            'source_sha256':'0'*64,'dependencies':{n:'1'*64 for n in NAMES},
            'component_vertices':list(range(152)),'width':.011,
            'inspection':{'regions':{'controlcase':['control-seated-castings','connected-control-housing','handwheel-left']},
                          'focus_region':'controlcase','views':[{'id':'rear','direction':[-1,.05,.12],'lighting':'neutral'},
                          {'id':'left','direction':[-1,1,.3],'lighting':'neutral'}],
                          'bounds':[[-.8,.16,.62],[-.20,.65,1.35]],'resolution':[960,640],'samples':12}}

class FrontRollTests(unittest.TestCase):
    def test_dispatch_and_source_contract(self):
        c=contract();self.assertIs(route(c,sorted(NAMES)),c)
    def test_curve_stays_in_front_and_monotonic(self):
        for w in (.010,.011,.012):
            s=front_stations(w);self.assertEqual(len(s),16);self.assertEqual(s[0],(0,w))
            self.assertTrue(all(0<=x<w and 0<y<=w for x,y in s))
            self.assertTrue(all(a[0]<b[0] and a[1]>b[1] for a,b in zip(s,s[1:])))
    def test_reject_unbounded_width(self):
        for w in (.0099,.0121,True,float('nan'),float('inf'),'0.011'):
            with self.subTest(w=w),self.assertRaises(ValueError):front_stations(w)
    def test_reject_missing_dependency(self):
        c=contract();c['dependencies'].pop('handwheel-left')
        with self.assertRaises(ValueError):validate(c,sorted(NAMES))
    def test_reject_extra_controls(self):
        c=contract();c['relax_area_gate']=True
        with self.assertRaises(ValueError):validate(c,sorted(NAMES))
    def test_reject_incomplete_or_duplicated_component(self):
        for ids in (list(range(151)),[0]*152,list(range(151))+[2296]):
            c=contract();c['component_vertices']=ids
            with self.assertRaises(ValueError):validate(c,sorted(NAMES))
    def test_reject_changed_evidence_frame(self):
        c=contract();c['inspection']['bounds'][0][0]=-.9
        with self.assertRaises(ValueError):validate(c,sorted(NAMES))
    def test_reject_missing_inventory(self):
        with self.assertRaises(ValueError):validate(contract(),[])
    def test_reject_unbound_source(self):
        c=contract();c['source_sha256']=''
        with self.assertRaises(ValueError):validate(c,sorted(NAMES))

if __name__=='__main__':unittest.main()
