import copy,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from sdk.protocol import CoreError
from adapters.models.vision import encode_png,validate_encoded
from adapters.models.native import NativeModel
from adapters.models.native_transport import request
from adapters.studio3d.organic import radial
from modules.skills.studio3d.contract import validate
from host.studio3d import wheel_example

class ImagePlanning(unittest.TestCase):
    def png(self,w=100,h=100):return b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',w,h)+bytes(9)
    def config(self):return {'id':'gemini','adapter':'gemini','model':'test-model','parameters':{},'max_output_tokens':512,'timeout_seconds':5,'max_prompt_bytes':1000}
    def test_image_goes_only_to_current_user_message(self):
        image=encode_png(self.png());messages=[{'role':'user','content':'old'},{'role':'assistant','content':'reply'},{'role':'user','content':'inspect'}]
        _,_,body=request(self.config(),{'api_key':'test'},messages,False,[image])
        self.assertEqual(body['contents'][-1]['parts'][-1],{'inlineData':image})
        self.assertEqual(len(body['contents'][0]['parts']),1)
        self.assertNotIn('inlineData',str(messages))
    def test_plaintext_wire_shape_is_unchanged(self):
        _,_,body=request(self.config(),{'api_key':'test'},[{'role':'user','content':'hello'}],False)
        self.assertEqual(body['contents'],[{'role':'user','parts':[{'text':'hello'}]}])
    def test_image_budget_and_envelope_reject_url_and_paths(self):
        for raw in (b'bad',self.png(8193,1),self.png(5000,5000),self.png()+bytes(12*1024**2)):
            with self.assertRaises(CoreError):encode_png(raw)
        image=encode_png(self.png())
        for v in ([image,image,image],{'url':'file:///private'},[{'mimeType':'image/png','data':'https://x'}],[{**image,'path':'secret'}]):
            with self.assertRaises(CoreError):validate_encoded(v)
    def test_unsupported_image_route_never_reads_credentials(self):
        cfg={**self.config(),'adapter':'openai'}
        with patch('adapters.models.native.subprocess.Popen') as process:
            loader=unittest.mock.Mock()
            with self.assertRaises(CoreError):NativeModel(cfg,loader).complete([{'role':'user','content':'x'}],reference_png=self.png())
            loader.assert_not_called();process.assert_not_called()
    def test_text_budget_not_raised_for_images(self):
        with self.assertRaises(CoreError):NativeModel(self.config(),lambda *_:None).complete([{'role':'user','content':'x'*1001}],reference_png=self.png())
    def test_radial_caps_are_closed_and_original_shape_unchanged(self):
        import math
        p={'segments':16,'profile':[[.001,.01],[.04,0],[.05,.04],[.03,.08],[.001,.065]]}
        v,f=radial(p)
        self.assertEqual(v[16],(.04,0.,0))
        v,f=radial({**p,'caps':True,'lobes':5,'lobe_depth':.04,'asymmetry':.02})
        edges={}
        for face in f:
            for a,b in zip(face,face[1:]+face[:1]):
                edge=tuple(sorted((a,b)));edges[edge]=edges.get(edge,0)+1
        self.assertTrue(all(n==2 for n in edges.values()))
        self.assertTrue(all(math.isfinite(n) for xyz in v for n in xyz))
    def test_organic_contract_and_strict_small_budget(self):
        s=wheel_example();s['materials'][0].update(detail='fruit_skin',secondary_color='#bc8a31',streak_strength=.6,speckle_density=100)
        s['objects'][0]['params'].update(caps=True,lobes=5,lobe_depth=.05,asymmetry=.025)
        s['asset_pipeline']={'texture_size':2048,'method':'project','category':'organic','triangle_budget':1000,'ray_distance':.001}
        validate(s)
        for key,value in [('lobes',True),('lobes',9),('lobe_depth',float('nan')),('asymmetry',.5),('caps',1)]:
            bad=copy.deepcopy(s);bad['objects'][0]['params'][key]=value
            with self.assertRaises(CoreError):validate(bad)
        for key,value in [('secondary_color','url'),('streak_strength',2),('speckle_density',0)]:
            bad=copy.deepcopy(s);bad['materials'][0][key]=value
            with self.assertRaises(CoreError):validate(bad)
        s['asset_pipeline']['triangle_budget']=999
        with self.assertRaises(CoreError):validate(s)
    def test_small_fruit_stem_radius_and_zero_rejection(self):
        s=wheel_example();s['objects'][0]['params']['profile']=[[.0001,0],[.0006,.002]]
        validate(s)
        for bad in (0,-.001,.00001,float('inf')):
            s['objects'][0]['params']['profile'][0][0]=bad
            with self.assertRaises(CoreError):validate(s)
    def test_camera_fit_keeps_small_and_large_objects_in_frame(self):
        from adapters.studio3d.framing import distance
        for size in (.08,4,20):
            points=[(x*size,y*size,z*size) for x in (-.5,.5) for y in (-.5,.5) for z in (-.5,.5)]
            d=distance(points,36,50,1.5)
            for x,y,z in points:
                self.assertLess(abs(x)/((d-z)*.36),1)
                self.assertLess(abs(y)/((d-z)*.24),1)

if __name__=='__main__':unittest.main()
