import copy,json,struct,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from host.core import Core
from host import studio3d as s
from modules.skills.catalog import Skills
from modules.skills.studio3d.contract import validate
from modules.skills.studio3d.presets import PRESETS
from modules.skills.studio3d.assets import validate_glb,decode_upload
from sdk.protocol import CoreError,canonical

def glb(value=None):
    v=value or {'asset':{'version':'2.0'},'meshes':[{}],'buffers':[{'byteLength':4}]};j=json.dumps(v).encode();j+=b' '*((-len(j))%4);b=b'\x00'*4
    return struct.pack('<III',0x46546c67,2,12+8+len(j)+8+len(b))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(b),0x004e4942)+b
class Studio3D(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);Core.initialize(self.root).close();self.scene=s.wheel_example()
    def test_both_presets_real_data_and_no_code(self):
        for name,fn in PRESETS.items():
            with self.subTest(name=name):
                v=fn();self.assertEqual(v,validate(v));self.assertTrue(any(o['kind'] in ('loft','lathe') for o in v['objects']));self.assertTrue(v['unfulfilled'])
    def test_defaults_and_fence_normalization(self):
        v=validate(self.scene);self.assertEqual(v['objects'][0]['position'],[0,0,0]);self.assertEqual(s.model_candidate('```json\n'+json.dumps(self.scene)+'\n```'),v)
        duplicate=json.dumps(self.scene).replace('"schema":','"schema":"duplicate","schema":',1)
        with self.assertRaises(CoreError):s.model_candidate(duplicate)
    def test_injection_and_paths_rejected(self):
        for k,v in [('python','import os'),('script','evil'),('url','https://example.com'),('output','../outside')]:
            with self.subTest(key=k),self.assertRaises(CoreError):validate({**self.scene,k:v})
    def test_nonfinite_bool_duplicate_missing_material(self):
        mutations=[lambda v:v['objects'][0].update(position=[float('nan'),0,0]),lambda v:v['objects'][0]['params'].update(segments=True),lambda v:v['materials'].append(v['materials'][0]),lambda v:v['objects'][0].update(material=[]),lambda v:v['objects'][0]['modifiers'].update(subdivision=3),lambda v:v['objects'][0]['modifiers'].update(difference=['future'])]
        for change in mutations:
            v=copy.deepcopy(self.scene);change(v)
            with self.subTest(change=change),self.assertRaises(CoreError):validate(v)
    def test_mesh_and_loft_bad_indices(self):
        cases=[{'kind':'mesh','params':{'vertices':[[0,0,0],[1,0,0],[0,1,0]],'faces':[[0,1,3]]}},{'kind':'mesh','params':{'vertices':[[0,0,0],[1,0,0],[0,1,0]],'faces':[[0,1,[]]]}},{'kind':'loft','params':{'rings':[[[0,0,0]]*3,[[1,0,0]]*4]}}]
        for change in cases:
            v=copy.deepcopy(self.scene);v['objects'][0].update(change)
            with self.subTest(change=change['kind']),self.assertRaises(CoreError):validate(v)
    def test_glb_container_and_uri(self):
        self.assertFalse(validate_glb(glb())['external_uris'])
        cases=[b'not glb',glb()[:-2],glb({'asset':{'version':'2.0'},'meshes':[{}],'buffers':[{'uri':'file:///secret'}]}),glb({'asset':{'version':'2.0'},'meshes':[{}],'buffers':[{}],'images':[{'uri':'https://external'}]})]
        for raw in cases:
            with self.subTest(size=len(raw)),self.assertRaises(CoreError):validate_glb(raw)
    def test_large_upload_parser_is_separate_from_core_messages(self):
        from sdk.protocol import decode
        raw=json.dumps({'data':'a'*300000}).encode();self.assertEqual(len(decode_upload(raw)['data']),300000)
        with self.assertRaises(CoreError):decode(raw)
        for invalid in (b'{"data":1,"data":2}',b'{"x":NaN}',b'{"x":"\\ud800"}'):
            with self.assertRaises(CoreError):decode_upload(invalid)
    def test_high_poly_glb_budget_remains_bounded(self):
        from modules.skills.studio3d.assets import MAX_GLB_BYTES,MAX_GLB_UPLOAD_BYTES,MAX_GLB_BASE64_BYTES
        self.assertEqual(MAX_GLB_BYTES,96*1024**2)
        self.assertGreater(MAX_GLB_UPLOAD_BYTES,MAX_GLB_BASE64_BYTES)
        raw=glb();self.assertEqual(validate_glb(raw,max_bytes=len(raw))['bytes'],len(raw))
        with self.assertRaises(CoreError):validate_glb(raw,max_bytes=len(raw)-1)
        # A self-contained high mesh may exceed the old 20 MiB import cap.
        raw=bytearray(glb());js=struct.unpack_from('<I',raw,12)[0];binary_start=28+js
        raw.extend(b'\0'*(21*1024**2));struct.pack_into('<I',raw,8,len(raw));struct.pack_into('<I',raw,20+js,len(raw)-binary_start)
        self.assertGreater(validate_glb(bytes(raw))['bytes'],20*1024**2)
    def test_upload_envelope_route_budget_does_not_relax_json_validation(self):
        raw=b'{"data":"abcd"}'
        self.assertEqual(decode_upload(raw,max_bytes=len(raw)),{'data':'abcd'})
        with self.assertRaises(CoreError):decode_upload(raw,max_bytes=len(raw)-1)
        with self.assertRaises(CoreError):decode_upload(b'{"data":1,"data":2}',max_bytes=100)
    def test_imported_part_inventory_supports_complex_props_but_stays_bounded(self):
        from modules.skills.studio3d.assets import MAX_GLB_MESHES,MAX_GLB_NODES
        base={'asset':{'version':'2.0'},'meshes':[{}]*132,'nodes':[{}]*132,'buffers':[{'byteLength':4}]}
        self.assertEqual(validate_glb(glb(base))['mesh_definitions'],132)
        self.assertEqual(validate_glb(glb({**base,'meshes':[{}]*MAX_GLB_MESHES}))['mesh_definitions'],MAX_GLB_MESHES)
        for altered in ({**base,'meshes':[{}]*(MAX_GLB_MESHES+1)},{**base,'nodes':[{}]*(MAX_GLB_NODES+1)}):
            with self.assertRaises(CoreError):validate_glb(glb(altered))
    def test_approved_asset_and_tamper(self):
        import base64
        a=s.upload(self.root,{'name':'test.glb','source':'original','license':'author','data':base64.b64encode(glb()).decode()});self.assertEqual(a,s.asset_record(self.root,a['id']));self.assertFalse(a['provenance_verified'])
        (self.root/'artifacts/studio3d-assets'/(a['id']+'.glb')).write_bytes(b'changed')
        with self.assertRaises(CoreError):s.asset_record(self.root,a['id'])
    def test_model_cannot_pick_private_asset(self):
        v={**self.scene,'asset':'a'*32}
        with self.assertRaises(CoreError):s.model_candidate(json.dumps(v))
    def test_disabled_and_unprepared_fail_before_execution(self):
        sk=Skills(self.root)
        try:self.assertEqual(sk.select('auto','请帮我做3D建模')['id'],'studio3d')
        finally:sk.close()
        with self.assertRaises(CoreError) as e:s.start(self.root,{'id':uuid.uuid4().hex,'preset':'wheel-study'},None)
        self.assertEqual(e.exception.code,'studio3d_not_prepared');sk=Skills(self.root);sk.enable('studio3d',False);sk.close()
        with self.assertRaises(CoreError) as e:s.start(self.root,{'id':uuid.uuid4().hex,'preset':'wheel-study'},None)
        self.assertEqual(e.exception.code,'skill_unavailable')
    def test_interrupted_not_replayed_and_bad_paths(self):
        ident=uuid.uuid4().hex;d=s.db(self.root);d.execute('INSERT INTO jobs(id,signature,status,phase,created) VALUES(?,?,?,?,?)',(ident,'hash','BUILDING','model',0));d.close();self.assertEqual(s.state(self.root,ident)['status'],'UNKNOWN')
        for value in ('../evil','a'*31,None):
            with self.assertRaises(CoreError):s.state(self.root,value)
    def test_idempotency_and_signature_conflict(self):
        ident=uuid.uuid4().hex;body={'id':ident,'preset':'wheel-study'};d=s.db(self.root);d.execute('INSERT INTO jobs(id,signature,status,phase,created) VALUES(?,?,?,?,?)',(ident,s.digest(body),'DELIVERED','done',0));d.close()
        folder=self.root/'optional/studio3d';folder.mkdir(parents=True);exe=folder/'fake-blender.exe';exe.write_bytes(b'existing')
        import hashlib
        (folder/'prepared.json').write_text(json.dumps({'executable':str(exe),'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}))
        with patch('host.studio3d.readiness',return_value={'ready':True}):
            self.assertTrue(s.start(self.root,body,None)['existing'])
            with self.assertRaises(CoreError):s.start(self.root,{**body,'preset':'gt-study'},None)
        exe.write_bytes(b'changed')
        with patch('host.studio3d.readiness',return_value={'ready':True}),self.assertRaises(CoreError) as changed:s.start(self.root,{'id':uuid.uuid4().hex,'preset':'wheel-study'},None)
        self.assertEqual(changed.exception.code,'studio3d_changed')
    def test_file_hash_and_view_escaping(self):
        ident=uuid.uuid4().hex;r={'status':'DELIVERED','receipt':{'files':{'preview.png':{'sha256':'incorrect'}}}}
        p=self.root/'artifacts/studio3d'/ident;p.mkdir(parents=True);(p/'preview.png').write_bytes(b'data')
        with patch('host.studio3d.state',return_value=r),self.assertRaises(CoreError):s.file(self.root,ident,'preview.png')
        with patch('host.studio3d.state',return_value=r),self.assertRaises(CoreError):s.file(self.root,ident,'../secret')
    def test_cancel_durable(self):
        ident=uuid.uuid4().hex;d=s.db(self.root);d.execute('INSERT INTO jobs(id,signature,status,phase,created) VALUES(?,?,?,?,?)',(ident,'hash','BUILDING','work',0));d.close()
        with s.GUARD:s.ACTIVE[(str(self.root),ident)]=True
        try:
            self.assertEqual(s.cancel(self.root,ident)['status'],'CANCEL_REQUESTED')
            with self.assertRaises(CoreError):s.check(self.root,ident)
        finally:
            with s.GUARD:s.ACTIVE.pop((str(self.root),ident),None)
    def test_reuse_preserves_origin_without_model_submission(self):
        prior={'id':'a'*32,'status':'FAILED','candidate':validate(self.scene),'chat_id':'prior-chat','turn_id':'prior-turn'}
        body={'id':'b'*32,'reuse_candidate':'a'*32};receipt={}
        with patch('host.studio3d.state',return_value=prior),patch('host.studio3d.check'),patch('host.studio3d.update') as update,patch('host.studio3d.build',return_value=receipt) as build:
            s.LOCK.acquire()
            s.run(self.root,body,validate(self.scene),None)
            self.assertEqual(build.call_args.args[3]['source_job'],'a'*32);self.assertEqual(build.call_args.args[3]['new_model_calls'],0)
            self.assertTrue(any(x.kwargs.get('status')=='DELIVERED' for x in update.call_args_list))
        with patch('host.studio3d.state',side_effect=CoreError('studio3d_missing','missing')),patch('host.studio3d.update') as update:
            s.LOCK.acquire();s.run(self.root,body,validate(self.scene),None);self.assertFalse(s.LOCK.locked());self.assertTrue(any(x.kwargs.get('status')=='FAILED' for x in update.call_args_list))
if __name__=='__main__':unittest.main()
