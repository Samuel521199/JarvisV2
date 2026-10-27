import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from sdk.protocol import CoreError
from modules.skills.studio3d.contract import validate
from host.studio3d import model_candidate

class TextureContract(unittest.TestCase):
    def scene(self):
        return {'schema':'jarvis.studio3d.v1','units':'m','title':'texture coupon','materials':[{'id':'skin','color':'#aa1015','detail':'fruit_skin'}],'objects':[{'id':'body','kind':'sphere','material':'skin'}],'unfulfilled':[],'surface_texture':{'reference':'a'*32,'material':'skin','mapping':'cylindrical'}}

    def test_binding_is_local_data_and_cannot_inject_paths(self):
        s=self.scene();self.assertEqual(validate(s)['surface_texture'],s['surface_texture'])
        for key,value in [('reference','../private.png'),('reference',[]),('material','missing'),('mapping','python'),('rotation',float('nan')),('rotation',181),('url','https://example.com/a.png'),('path','C:/secret')]:
            candidate=copy.deepcopy(s);candidate['surface_texture'][key]=value
            with self.assertRaises(CoreError):validate(candidate)
        s['materials'][0]['detail']='bark'
        with self.assertRaises(CoreError):validate(s)

    def test_model_cannot_choose_texture_and_prompt_does_not_leak_id(self):
        from modules.skills.studio3d.refinement import prompt
        with self.assertRaises(CoreError):model_candidate(json.dumps(self.scene()))
        text=prompt(self.scene());self.assertNotIn('a'*32,text);self.assertIn('Preserve that material ID',text)

    def test_changed_texture_rejected_before_blender(self):
        import hashlib
        from host.studio3d import build
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);optional=root/'optional/studio3d';optional.mkdir(parents=True)
            exe=optional/'blender.exe';exe.write_bytes(b'fixed test identity')
            (optional/'prepared.json').write_text(json.dumps({'executable':str(exe),'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}))
            refs=root/'artifacts/studio3d-references';refs.mkdir(parents=True)
            (refs/('a'*32+'.png')).write_bytes(b'tampered')
            (refs/('a'*32+'.json')).write_text(json.dumps({'sha256':'0'*64}))
            with patch('host.studio3d.subprocess.Popen') as process:
                with self.assertRaises(CoreError):build(root,'b'*32,validate(self.scene()))
                process.assert_not_called()

    def test_curved_uv_keeps_flat_crown_area_and_wrap_seam(self):
        from adapters.studio3d.organic import lathe_uv,radial
        p={'profile':[[.01,0],[.04,.04],[.025,.06],[.01,.06]],'segments':16,'caps':True}
        _,faces=radial(p);uv=lathe_uv(p,faces)
        self.assertEqual(len(uv),len(faces))
        self.assertTrue(all(max(x[0] for x in row)-min(x[0] for x in row)<=.5 for row in uv))
        # The horizontal crown still gets positive V extent, unlike z mapping.
        crown=uv[2*16];self.assertGreater(max(x[1] for x in crown)-min(x[1] for x in crown),.01)
        s=self.scene();s['surface_texture']['mapping']='lathe'
        with self.assertRaises(CoreError):validate(s)
        s['objects'][0].update(kind='lathe',params=p);validate(s)

    def test_organic_ring_topology_is_closed_and_within_budget(self):
        from adapters.studio3d.organic import retopo_lathe
        p={'profile':[[.001,0],[.04,.04],[.03,.07],[.001,.055]],'caps':True,'lobes':5,'lobe_depth':.02}
        for budget in (128,200,400,836,10000):
            vertices,faces=retopo_lathe(p,budget);edges={}
            self.assertLessEqual(sum(len(f)-2 for f in faces),budget)
            for face in faces:
                for a,b in zip(face,face[1:]+face[:1]):
                    key=tuple(sorted((a,b)));edges[key]=edges.get(key,0)+1
            self.assertTrue(all(count==2 for count in edges.values()))

if __name__=='__main__':unittest.main()
