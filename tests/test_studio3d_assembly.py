import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path
from modules.skills.studio3d.assembly_contract import validate
from host.studio3d_assembly import intake
from sdk.protocol import CoreError


def example():
    return {'schema':'jarvis.studio3d.assembly.v1','title':'Reference assembly','mode':'assemble','views':['hero','front'],
            'parts':[{'id':'hull','source':'hull','parent':None,'position':[0,0,0],'rotation':[0,0,180],'scale':[1,1,1]},
                     {'id':'left','source':'track','parent':'hull','position':[-1,0,0],'rotation':[0,0,0],'scale':[-1,1,1]}]}


class Assembly(unittest.TestCase):
    def test_named_linked_reflection_and_copy(self):
        e=example();r=validate(e);r['parts'][0]['position'][0]=1
        self.assertEqual(e['parts'][0]['position'][0],0)

    def test_unsafe_transforms_and_cycles(self):
        for key,value in [('position',[0,float('nan'),0]),('scale',[1,0,1]),('scale',[True,1,1]),('rotation',[0,0,361]),('parent','left'),('id','../bad')]:
            e=example();e['parts'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(e)

    def test_duplicate_ids_unknown_fields_views_and_budget(self):
        for change in (lambda e:e['parts'][1].update(id='hull'),lambda e:e.update(python='exec'),lambda e:e.update(views=['../../file']),lambda e:e.update(parts=e['parts']*5)):
            e=example();change(e)
            with self.assertRaises(ValueError):validate(e)

    def test_intake_rejects_external_resources(self):
        doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':4}],'nodes':[],'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}],'accessors':[{'count':3}],'images':[{'uri':'https://example.invalid/texture.png'}]}
        data=json.dumps(doc).encode();data+=b' '*((-len(data))%4);body=struct.pack('<II',len(data),0x4e4f534a)+data+struct.pack('<II',4,0x004e4942)+b'\0'*4
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'part.glb';p.write_bytes(struct.pack('<III',0x46546c67,2,len(body)+12)+body)
            with self.assertRaises(CoreError) as error:intake(p)
            self.assertEqual(error.exception.code,'studio3d_asset_invalid')

    def test_source_mesh_instances_are_counted(self):
        doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':36}],'bufferViews':[{'buffer':0,'byteLength':36}],
             'nodes':[{'mesh':0},{'mesh':0}],'scenes':[{'nodes':[0,1]}],'scene':0,
             'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}],
             'accessors':[{'bufferView':0,'count':3,'componentType':5126,'type':'VEC3','min':[0,0,0],'max':[0,0,0]}]}
        data=json.dumps(doc).encode();data+=b' '*((-len(data))%4);body=struct.pack('<II',len(data),0x4e4f534a)+data+struct.pack('<II',36,0x004e4942)+b'\0'*36
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'part.glb';p.write_bytes(struct.pack('<III',0x46546c67,2,len(body)+12)+body)
            self.assertEqual(intake(p)[1]['triangles'],2)


if __name__=='__main__':unittest.main()
