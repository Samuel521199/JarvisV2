import copy
import unittest
from modules.skills.studio3d.spade_frame import TARGETS, ANCHORS, validate
from modules.skills.studio3d.attachment_seat import validate as dispatch

class SpadeFrame(unittest.TestCase):
    def contract(self):
        return {'schema':'jarvis.studio3d.spade-frame.v1','author':'Jarvis','evidence':'Bound actual exterior comparison',
                'source_sha256':'a'*64,'bindings':{n:{'base':'b'*64,'dependency':'c'*64} for n in TARGETS+ANCHORS},
                'components':{s:{'seat':list(range(8)),'pivot_plate':list(range(194,202)), 'pivot_cylinder':list(range(194))} for s in ('left','right')},
                'corner_offset':.035,'inspection':{'resolution':[960,640],'samples':12,'bounds':[[-3.5,1.2,0],[-2.5,2,.7]],
                  'views':[{'id':'rear','direction':[-.8,.8,.5],'lighting':'neutral'},{'id':'top','direction':[0,0,1],'lighting':'neutral'}],
                  'regions':{'spade':[n for n in TARGETS+ANCHORS if n.endswith('left')]}}}
    def test_existing_operation_dispatch(self):
        c=self.contract();self.assertIs(dispatch(c,TARGETS+ANCHORS),c)
    def test_missing_dependency_or_anchor_rejected(self):
        for key in ('spade-blade-left','spade-lever-right'):
            c=self.contract();del c['bindings'][key]
            with self.assertRaises(ValueError):validate(c,TARGETS+ANCHORS)
    def test_incomplete_duplicate_or_overlapping_components(self):
        for ids in ([194]*8,list(range(194,201)),list(range(8))):
            c=self.contract();c['components']['left']['pivot_plate']=ids
            with self.assertRaises(ValueError):validate(c,TARGETS+ANCHORS)
    def test_controls_and_resource_envelope(self):
        for value in (True,float('nan'),.029,.041):
            c=self.contract();c['corner_offset']=value
            with self.assertRaises(ValueError):validate(c,TARGETS+ANCHORS)
        c=self.contract();c['inspection']['samples']=32
        with self.assertRaises(ValueError):validate(c,TARGETS+ANCHORS)
    def test_no_threshold_override_or_extra_target(self):
        for key,value in (('support_threshold',.1),('targets',['other-asset'])):
            c=self.contract();c[key]=value
            with self.assertRaises(ValueError):validate(c,TARGETS+ANCHORS)

if __name__=='__main__':unittest.main()
