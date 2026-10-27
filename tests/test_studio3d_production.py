import copy,unittest
from sdk.protocol import CoreError
from modules.skills.studio3d.production import master_study,PROFILES
from modules.skills.studio3d.contract import validate
from host.studio3d import model_candidate
import json

class ProductionContract(unittest.TestCase):
    def scene(self):
        return {'schema':'jarvis.studio3d.v1','units':'m','title':'bounded high master','materials':[{'id':'paint','color':'#334455'}],'objects':[{'id':'part','kind':'cylinder','material':'paint','params':{'radius':.1,'depth':.4,'segments':12}}],'unfulfilled':[]}
    def test_round_primitives_have_explicit_low_segment_control(self):
        s=self.scene();self.assertEqual(validate(s)['objects'][0]['params']['segments'],12)
        for value in (0,7,129,12.5,True,'16'):
            s['objects'][0]['params']['segments']=value
            with self.assertRaises(CoreError):validate(s)
    def test_projection_controls_reject_unbounded_and_ambiguous_input(self):
        s=self.scene();base={'texture_size':1024,'method':'project','category':'vehicle','triangle_budget':30000,'ray_distance':.04}
        for key,value in [('method','python'),('category','all'),('triangle_budget',False),('triangle_budget',100001),('ray_distance',float('nan')),('ray_distance',0),('path','C:/secret'),('cage','../private')]:
            s['asset_pipeline']={**base,key:value}
            with self.assertRaises(CoreError):validate(s)
        for category in PROFILES:s['asset_pipeline']={**base,'category':category};validate(s)
    def test_model_cannot_select_private_assets_or_initiate_baking(self):
        s=self.scene();s['asset_pipeline']={'texture_size':512,'method':'project'}
        with self.assertRaises(CoreError):model_candidate(json.dumps(s))
    def test_old_surface_mode_cannot_silently_ignore_production_budget(self):
        s=self.scene();s['asset_pipeline']={'texture_size':512,'triangle_budget':30000}
        with self.assertRaises(CoreError):validate(s)
    def test_master_is_separate_and_keeps_unverified_photo_regions(self):
        s=master_study();self.assertNotIn('asset_pipeline',s);self.assertLessEqual(len(s['objects']),128)
        self.assertIn('顶部',s['unfulfilled'][0]);self.assertEqual(next(m for m in s['materials'] if m['id']=='paint')['metallic'],0)
        self.assertEqual(len([o for o in s['objects'] if o['id'].startswith('cupola-window-')]),8)
    def test_detail_pairing_rejects_missing_chain_and_hidden_targets(self):
        from modules.skills.studio3d.production import projection_coupon
        for target in ('missing','rivet',[],None):
            s=projection_coupon();s['objects'][1]['bake_target']=target
            with self.assertRaises(CoreError):validate(s)
        s=projection_coupon();s['objects'][0]['visible']=False
        with self.assertRaises(CoreError):validate(s)
        s=projection_coupon();s['objects'][2]['bake_target']='rivet'
        with self.assertRaises(CoreError):validate(s)
    def test_frozen_master_requires_explicit_bounded_projection(self):
        for master,pipeline in [('a'*32,None),('a'*32,[]),('a'*32,{'texture_size':512}),('../source.blend',{'texture_size':512,'method':'project'}),(False,{'texture_size':512,'method':'project'})]:
            s={**self.scene(),'master':master,'asset_pipeline':pipeline}
            with self.assertRaises(CoreError):validate(s)
        s={**self.scene(),'master':'a'*32,'asset_pipeline':{'texture_size':512,'method':'project'}}
        self.assertEqual(validate(s)['master'],'a'*32)
        with self.assertRaises(CoreError):model_candidate(json.dumps(s))
    def test_frozen_blend_tamper_rejected_before_worker(self):
        import tempfile,hashlib
        from pathlib import Path
        from unittest.mock import patch
        from host import studio3d as host
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);optional=root/'optional/studio3d';optional.mkdir(parents=True)
            exe=optional/'blender.exe';exe.write_bytes(b'fixed test identity')
            (optional/'prepared.json').write_text(json.dumps({'executable':str(exe),'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}))
            prior=root/'artifacts/studio3d'/('a'*32);prior.mkdir(parents=True);(prior/'model.blend').write_bytes(b'tampered')
            receipt={'status':'DELIVERED','receipt':{'configuration':{},'quality':{'status':'visual_asset_export_checked'},'files':{'model.blend':{'sha256':'0'*64}}}}
            s={**self.scene(),'master':'a'*32,'asset_pipeline':{'texture_size':512,'method':'project'}}
            with patch('host.studio3d.state',return_value=receipt),patch('host.studio3d.subprocess.Popen') as process:
                with self.assertRaises(CoreError):host.build(root,'b'*32,s)
                process.assert_not_called()
