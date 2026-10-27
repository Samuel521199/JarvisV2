import copy,json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from adapters.models.vision import encode_png,validate_encoded
from adapters.models.native_transport import request
from adapters.studio3d.organic import sweep
from modules.skills.studio3d.contract import validate
from modules.skills.studio3d.refinement import parse,prompt,AREAS
from host.studio3d import wheel_example,start
from sdk.protocol import CoreError

class Refinement(unittest.TestCase):
    def scene(self):
        s=wheel_example();s['objects']=[{'id':'stem','kind':'sweep','material':'metal','params':{'points':[[0,0,0],[.003,0,.01],[.01,.002,.02]],'radii':[.003,.002,.001]}}]
        return validate(s)
    def result(self,final=False):
        return {'verdict':'needs_revision','summary':'Still differs','observations':[{'area':a,'problem':'visible difference','change':'bounded correction'} for a in AREAS],'unverified':['hidden back'],'scene':None if final else self.scene()}
    def test_sweep_closed_tapered_with_real_bend(self):
        p=self.scene()['objects'][0]['params'];v,f=sweep(p);n=p['segments'];edges={}
        for face in f:
            for a,b in zip(face,face[1:]+face[:1]):
                edge=tuple(sorted((a,b)));edges[edge]=edges.get(edge,0)+1
        self.assertTrue(all(count==2 for count in edges.values()))
        for start,expected,radius in [(0,p['points'][0],.003),(len(v)-n,p['points'][-1],.001)]:
            center=[sum(v[start+i][j] for i in range(n))/n for j in range(3)]
            for a,b in zip(center,expected):self.assertAlmostEqual(a,b)
            self.assertAlmostEqual(sum((v[start][j]-center[j])**2 for j in range(3))**.5,radius)
    def test_invalid_sweep_and_resource_controls(self):
        for key,value in [('radii',[.001]),('radii',[.001,0,.001]),('steps',True),('segments',1000),('points',[[0,0,0]]*3),('oval',float('nan')),('end_irregularity',.21)]:
            s=self.scene();s['objects'][0]['params'][key]=value
            with self.assertRaises(CoreError):validate(s)
        s=self.scene();s['objects'][0]['cap_material']='missing'
        with self.assertRaises(CoreError):validate(s)
    def test_cut_material_alias_is_bounded_and_conflicts_rejected(self):
        s=self.scene();o=s['objects'][0];o['params']['cap_material']='metal'
        normalized=validate(s);self.assertEqual(normalized['objects'][0]['cap_material'],'metal')
        self.assertNotIn('cap_material',normalized['objects'][0]['params'])
        o['cap_material']='metal'
        with self.assertRaises(CoreError):validate(s)
        del o['cap_material'];o['params']['cap_material']='file:///secret'
        with self.assertRaises(CoreError):validate(s)
    def test_lighting_and_regions_reject_paths_and_unbounded_values(self):
        light={'position':[0,-1,1],'power':120,'size':.7,'color':'#ffffff'}
        region={'center':[.5,.5,.5],'radius':[.2,.2,.2],'color':'#ffeecc','opacity':.5,'roughness':.4}
        s=self.scene();s['render'].update(lights=[light],camera_direction=[0,-1,.3]);s['materials'][0]['regions']=[region];validate(s)
        for key,value in [('power',501),('size',0),('position',[0,0,0]),('color','file:///secret')]:
            bad=copy.deepcopy(s);bad['render']['lights'][0][key]=value
            with self.assertRaises(CoreError):validate(bad)
        s['materials'][0]['regions']=[region]*9
        with self.assertRaises(CoreError):validate(s)
    def test_review_does_not_allow_asset_selection_part_loss_or_final_mutation(self):
        for mutate in (lambda v:v['scene'].update(reference='a'*32),lambda v:v['scene']['objects'][0].update(id='other'),lambda v:v['observations'].pop()):
            v=self.result();mutate(v)
            with self.assertRaises(CoreError):parse(json.dumps(v),parts=['stem'])
        with self.assertRaises(CoreError):parse(json.dumps(self.result()),final=True)
        self.assertEqual(parse(json.dumps(self.result(True)),final=True)['verdict'],'needs_revision')
    def test_context_strips_private_ids_and_retains_text_limit(self):
        s=self.scene();s['reference']='a'*32
        text=prompt(s)
        self.assertNotIn('a'*32,text);self.assertIn('image 2',text)
        with self.assertRaises(CoreError):prompt(s,'x'*12000)
    def png(self,w,h):return b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',w,h)+bytes(9)
    def test_two_images_order_and_combined_pixel_budget(self):
        a,b=encode_png(self.png(100,200)),encode_png(self.png(200,100))
        cfg={'adapter':'gemini','model':'test','parameters':{},'max_output_tokens':100}
        _,_,body=request(cfg,{'api_key':'test'},[{'role':'user','content':'compare'}],False,validate_encoded([a,b]))
        self.assertEqual([part['inlineData'] for part in body['contents'][0]['parts'][1:]],[a,b])
        with self.assertRaises(CoreError):validate_encoded([encode_png(self.png(3000,3000))]*2)
        with self.assertRaises(CoreError):validate_encoded([encode_png(self.png(1,1)+bytes(7*1024**2))]*2)
    def test_refinement_requires_explicit_image_authorization_before_planning(self):
        prior={'status':'DELIVERED','receipt':{'configuration':self.scene()}}
        with patch('host.studio3d.enabled'),patch('host.studio3d.state',return_value=prior),patch('host.studio3d.readiness') as ready:
            with self.assertRaises(CoreError):start(Path('.'),{'id':'a'*32,'refine':'b'*32,'provider':'vertex','model':'test'},None)
            ready.assert_not_called()
    def test_review_reuse_rejects_changed_images_before_new_model_call(self):
        from host.studio3d_refinement import begin
        prior={'receipt':{'id':'b'*32,'configuration':self.scene(),'files':{'preview.png':{'sha256':'render'}}}}
        failed={'id':'c'*32,'status':'FAILED','turn_id':'studio3d-old-compare','chat_id':'old'}
        body={'id':'a'*32,'refine':'b'*32,'reuse_review':'c'*32,'reference':'d'*32,'provider':'vertex','model':'test'}
        turn={'status':'SUCCEEDED','request':json.dumps({'provider':'vertex','model':'test','reference_images':['e'*32,'f'*32]}),'reply':json.dumps(self.result())}
        with patch('host.studio3d.state',side_effect=[prior,failed]),patch('host.studio3d_refinement.Dialogues') as store,patch('host.studio3d_reference.record',side_effect=[({'sha256':'old-reference'},b''),({'sha256':'render'},b''),({'sha256':'changed'},b'')]),patch('host.studio3d_refinement.assess') as assess:
            store.return_value.turn.return_value=turn
            with self.assertRaises(CoreError):begin(Path('.'),body,object())
            assess.assert_not_called()
    def test_final_reviewer_cannot_promote_to_aaa(self):
        value=self.result(True);value['verdict']='AAA'
        with self.assertRaises(CoreError):parse(json.dumps(value),True)

if __name__=='__main__':unittest.main()
