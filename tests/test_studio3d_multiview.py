import base64,copy,json,struct,tempfile,unittest
from pathlib import Path
from host.core import Core
from host import studio3d
from host.studio3d_reference import upload,record
from modules.skills.studio3d.tracked_vehicle import panzer2
from modules.skills.studio3d.contract import validate
from sdk.protocol import CoreError

class Multiview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);Core.initialize(self.root).close()
    def body(self):
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg==')
        return {'name':'reference.png','source':'original test','license':'author test','data':base64.b64encode(png).decode()}
    def test_reference_preserves_sha_and_no_vision_claim(self):
        row=upload(self.root,self.body());saved,raw=record(self.root,row['id']);self.assertEqual(row,saved);self.assertEqual(saved['resolution'],[1,1]);self.assertFalse(saved['provenance_verified']);self.assertIn('no automatic',saved['mode']);self.assertTrue(raw.startswith(b'\x89PNG'))
    def test_reference_rejects_tamper_and_traversal(self):
        row=upload(self.root,self.body());(self.root/'artifacts/studio3d-references'/(row['id']+'.png')).write_bytes(b'changed')
        for ident in (row['id'],'../secret','x'*32,None):
            with self.assertRaises(CoreError):record(self.root,ident)
    def test_reference_type_dimension_and_provenance_bounds(self):
        for change in ({'data':'not base64'},{'data':base64.b64encode(b'not PNG').decode()},{'license':''},{'source':'x'*501},{'path':'../secret'}):
            with self.subTest(change=list(change)),self.assertRaises(CoreError):upload(self.root,{**self.body(),**change})
        raw=bytearray(base64.b64decode(self.body()['data']));struct.pack_into('>II',raw,16,8192,8192)
        with self.assertRaises(CoreError):upload(self.root,{**self.body(),'data':base64.b64encode(raw).decode()})
    def test_five_views_strict_boolean(self):
        s=panzer2();self.assertTrue(validate(s)['render']['five_views'])
        for v in (1,'yes',[],None):
            t=copy.deepcopy(s);t['render']['five_views']=v
            with self.assertRaises(CoreError):validate(t)
    def test_exposure_and_shading_limits(self):
        s=panzer2()
        for v in (-3,0,1):
            t=copy.deepcopy(s);t['render']['exposure']=v;self.assertEqual(validate(t)['render']['exposure'],v)
        for v in (-3.1,1.1,True,float('nan')):
            t=copy.deepcopy(s);t['render']['exposure']=v
            with self.assertRaises(CoreError):validate(t)
        s['objects'][0]['shading']='execute'
        with self.assertRaises(CoreError):validate(s)
    def test_registered_semantic_parts_and_track_links(self):
        s=panzer2();self.assertEqual(s,validate(s));self.assertEqual(len(s['objects']),108);ids=[o['id'] for o in s['objects']]
        self.assertEqual(len([x for x in ids if x.startswith('road-tire-')]),10);self.assertEqual(len([x for x in ids if x.startswith('return-')]),8)
        for side in ('left','right'):
            track=next(o for o in s['objects'] if o['id']=='track-shoes-'+side);self.assertEqual(len(track['params']['vertices']),116*8)
    def test_model_cannot_select_reference_or_bake(self):
        s=panzer2();s['reference']='a'*32
        with self.assertRaises(CoreError):studio3d.model_candidate(json.dumps(s))
    def test_new_exports_whitelist(self):
        for v in ('front','rear','left','right','top'):self.assertEqual(studio3d.FILES['view-'+v+'.png'],'image/png')
        self.assertEqual(studio3d.FILES['reference.png'],'image/png');self.assertNotIn('../reference.png',studio3d.FILES)
