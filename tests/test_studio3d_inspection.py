import copy,unittest
from modules.skills.studio3d.render_inspection import validate


class InspectionContract(unittest.TestCase):
    def sample(self):return {'bounds':[[-1,-1,0],[1,1,1]],'resolution':[1536,1024],'samples':16,'views':[{'id':'left','direction':[.1,1,.12]}],'regions':{'wheel':['wheel']}}

    def test_declared_camera_and_group(self):validate(self.sample(),['wheel'])

    def test_degenerate_frame_or_camera_rejected(self):
        for change in ({'bounds':[[0,0,0],[0,1,1]]},{'views':[{'id':'left','direction':[0,0,0]}]},{'bounds':[[0,0,0],[1,float('nan'),1]]}):
            v=self.sample();v.update(change)
            with self.assertRaises(ValueError):validate(v,['wheel'])

    def test_code_paths_and_unbounded_renders_rejected(self):
        for change in ({'script':'anything'},{'resolution':[16384,16384]},{'samples':10000},{'regions':{'../escape':['wheel']}},{'regions':{'wheel':['absent']}}):
            v=self.sample();v.update(change)
            with self.assertRaises(ValueError):validate(v,['wheel'])

    def test_duplicate_views_rejected(self):
        v=self.sample();v['views']*=2
        with self.assertRaises(ValueError):validate(v,['wheel'])

    def test_fixed_lighting_and_declared_focus(self):
        for preset in ('source','neutral','grazing-left','grazing-right'):
            v=self.sample();v['views'][0]['lighting']=preset;v['focus_region']='wheel';validate(v,['wheel'])

    def test_probe_does_not_admit_arbitrary_lights_or_targets(self):
        for change in ({'lighting':'custom'},{'energy':100000},{'lighting':{'script':'x'}}):
            v=self.sample();v['views'][0].update(change)
            with self.assertRaises(ValueError):validate(v,['wheel'])

    def test_channel_probe_is_bounded_and_not_lighting(self):
        for channel in ('base_color','roughness','metallic','bevel_delta','edge_mask','damage_mask'):
            v=self.sample();v['focus_region']='wheel';v['views'][0]['surface_probe']=channel;validate(v,['wheel'])
        for change in ({'surface_probe':'arbitrary-node'},{'surface_probe':'edge_mask','lighting':'neutral'}):
            v=self.sample();v['focus_region']='wheel';v['views'][0].update(change)
            with self.assertRaises(ValueError):validate(v,['wheel'])
        v=self.sample();v['views'][0]['surface_probe']='edge_mask'
        with self.assertRaises(ValueError):validate(v,['wheel'])
        for focus in ('absent','../wheel',[],None):
            v=self.sample();v['focus_region']=focus
            with self.assertRaises(ValueError):validate(v,['wheel'])


if __name__=='__main__':unittest.main()
