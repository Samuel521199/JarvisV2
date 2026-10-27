import json,struct,unittest,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
from sdk.protocol import CoreError
from modules.skills.studio3d.inspection import inspect,image_size
from modules.skills.studio3d.contract import validate
from host import studio3d
from host.studio3d_viewer import vendor,IMPORT_MAP,IMPORT_HASH,CSP

def container(doc,binary=b'\0'*4):
    text=json.dumps(doc).encode();text+=b' '*((-len(text))%4);binary+=b'\0'*((-len(binary))%4)
    return struct.pack('<III',0x46546c67,2,28+len(text)+len(binary))+struct.pack('<II',len(text),0x4e4f534a)+text+struct.pack('<II',len(binary),0x004e4942)+binary
def document():return {'asset':{'version':'2.0'},'buffers':[{'byteLength':4}],'accessors':[{'count':3}],'meshes':[{'primitives':[{'attributes':{'POSITION':0,'TEXCOORD_0':0}}]}],'materials':[{'name':'metal','pbrMetallicRoughness':{'metallicFactor':.8,'roughnessFactor':.25}}]}
class Viewer(unittest.TestCase):
    def test_material_is_not_an_image_texture(self):
        r=inspect(container(document()));self.assertEqual(r['triangles'],1);self.assertEqual(r['textures'],0);self.assertEqual(r['images'],[]);self.assertEqual(r['materials'][0]['metallic'],.8);self.assertIn('normal',r['materials'][0]['missing_for_profile']);self.assertFalse(r['AAA_certified'])
    def test_embedded_png_and_channels(self):
        png=b'\x89PNG\r\n\x1a\n'+b'\0'*8+struct.pack('>II',512,256);d=document();d.update(bufferViews=[{'byteOffset':0,'byteLength':len(png)}],images=[{'bufferView':0,'mimeType':'image/png'}],textures=[{'source':0}]);m=d['materials'][0];m.update(normalTexture={'index':0},occlusionTexture={'index':0});m['pbrMetallicRoughness'].update(baseColorTexture={'index':0},metallicRoughnessTexture={'index':0});r=inspect(container(d,png));self.assertEqual(r['images'][0]['dimensions'],[512,256]);self.assertEqual(r['materials'][0]['missing_for_profile'],[]);self.assertGreater(r['texture_memory_estimate_bytes'],512*256*4)
    def test_missing_uv_is_not_pass(self):
        d=document();d['meshes'][0]['primitives'][0]['attributes'].pop('TEXCOORD_0');r=inspect(container(d));self.assertEqual(next(c for c in r['checks'] if c['id']=='uv-presence')['status'],'fail')
    def test_png_and_jpeg_bounds(self):
        self.assertIsNone(image_size(b'wrong','image/png'));self.assertEqual(image_size(b'\xff\xd8\xff\xc0\x00\x11\x08\x00\x20\x00\x40'+b'\0'*8,'image/jpeg'),[64,32])
    def test_unknown_vendor_and_tamper(self):
        for path in ['/vendor/three/../../secret','/vendor/three/missing.js']:
            with self.assertRaises(CoreError):vendor(path)
        raw,mime=vendor('/vendor/three/build/three.module.js');self.assertEqual(mime,'text/javascript');self.assertIn(b'three.core.js',raw)
        self.assertIn(IMPORT_HASH,CSP);self.assertNotIn("'unsafe-inline'",CSP);self.assertIn('/vendor/three',IMPORT_MAP)
    def test_pipeline_is_explicit_and_bounded(self):
        for size in [512,1024,2048]:self.assertEqual(validate({**studio3d.wheel_example(),'asset_pipeline':{'texture_size':size}})['asset_pipeline']['texture_size'],size)
        for params in [{'texture_size':4096},{'texture_size':True},{'texture_size':512,'python':'evil'}]:
            with self.assertRaises(CoreError):validate({**studio3d.wheel_example(),'asset_pipeline':params})
        with self.assertRaises(CoreError):studio3d.model_candidate(json.dumps({**studio3d.wheel_example(),'asset_pipeline':{'texture_size':512}}))
    def test_optional_outputs_are_whitelisted(self):
        self.assertIn('model-lod1.glb',studio3d.FILES);self.assertNotIn('model-lod1.glb',studio3d.REQUIRED_FILES);self.assertNotIn('arbitrary.py',studio3d.FILES)
if __name__=='__main__':unittest.main()
