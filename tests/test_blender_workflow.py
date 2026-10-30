import copy
import hashlib
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from host import studio3d
from host.core import Core
from modules.dialogue.store import Dialogues
from modules.skills.catalog import Skills
from modules.skills.studio3d.blender_workflow import apply_changes
from modules.skills.studio3d.contract import validate
from sdk.protocol import CoreError, canonical, digest


class BlenderWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        Core.initialize(self.root).close()
        self.scene = validate(studio3d.wheel_example())
        self.obj = self.scene['objects'][0]['id']

    def source(self):
        ident = uuid.uuid4().hex
        folder = self.root / 'artifacts/studio3d' / ident
        folder.mkdir(parents=True)
        raw = canonical(self.scene).encode()
        (folder / 'scene.json').write_bytes(raw)
        sha = hashlib.sha256(raw).hexdigest()
        receipt = {'configuration': self.scene, 'files': {'scene.json': {'sha256': sha}}}
        db = studio3d.db(self.root)
        try: db.execute('INSERT INTO jobs(id,signature,status,phase,created,receipt) VALUES(?,?,?,?,?,?)', (ident,'source','DELIVERED','done',0,canonical(receipt)))
        finally: db.close()
        return {'id': uuid.uuid4().hex, 'edit': ident, 'source_sha256': sha,
                'changes': {'objects': [{'id': self.obj, 'set': {'scale': [1.2, 1, 1]}}]}}

    def test_edit_preserves_source_and_untouched_geometry(self):
        original = copy.deepcopy(self.scene)
        out, audit = apply_changes(self.scene, {'objects': [{'id': self.obj, 'set': {'scale': [1.2,1,1], 'modifiers': {'bevel': .01}}}]})
        self.assertEqual(self.scene, original)
        self.assertEqual(out['objects'][0]['scale'], [1.2,1,1])
        self.assertEqual(out['objects'][0]['params'], original['objects'][0]['params'])
        self.assertEqual(out['objects'][1:], original['objects'][1:])
        self.assertEqual(audit['new_model_calls'], 0)
        self.assertEqual(audit['visual_acceptance'], 'pending')

    def test_shared_material_lists_every_affected_part(self):
        self.scene['objects'].append({**copy.deepcopy(self.scene['objects'][0]), 'id': 'shared-copy'})
        mat = self.scene['objects'][0]['material']
        out, audit = apply_changes(self.scene, {'materials': [{'id': mat, 'set': {'color': '#aa2233'}}]})
        self.assertIn('shared-copy', audit['affected_objects'])
        self.assertIn(self.obj, audit['affected_objects'])
        self.assertEqual(out['objects'], self.scene['objects'])

    def test_bad_edits_and_imported_or_baked_sources_rejected(self):
        cases = [{}, {'objects': []}, {'python': 'x'}, {'objects': [{'id': 'missing', 'set': {'visible': False}}]},
                 {'objects': [{'id': self.obj, 'set': {'id': 'rename'}}]},
                 {'objects': [{'id': self.obj, 'set': {'scale': [float('nan'),1,1]}}]},
                 {'objects': [{'id': self.obj, 'set': {'modifiers': {'subdivision': 20}}}]},
                 {'objects': [{'id': self.obj, 'set': {'params': {'script': 'x'}}}]},
                 {'objects': [{'id': self.obj, 'set': {'visible': False}}] * 2}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(CoreError): apply_changes(self.scene, changes)
        for extra in ({'asset': 'a'*32}, {'asset_pipeline': {'texture_size': 512}}):
            with self.subTest(extra=extra), self.assertRaises(CoreError):
                apply_changes({**self.scene, **extra}, {'objects': [{'id': self.obj, 'set': {'scale': [2,1,1]}}]})

    def test_hash_checked_against_actual_source_and_receipt(self):
        body = self.source()
        scene, audit = studio3d.edit_candidate(self.root, body)
        self.assertEqual(scene['objects'][0]['scale'], [1.2,1,1])
        self.assertEqual(audit['source_job'], body['edit'])
        with self.assertRaises(CoreError) as stale: studio3d.edit_candidate(self.root, {**body, 'source_sha256': '0'*64})
        self.assertEqual(stale.exception.code, 'conflict')
        path = self.root/'artifacts/studio3d'/body['edit']/'scene.json'
        path.write_text(canonical({**self.scene,'title':'tampered'}),encoding='utf-8')
        with self.assertRaises(CoreError) as corrupt: studio3d.edit_candidate(self.root, body)
        self.assertEqual(corrupt.exception.code, 'studio3d_changed')

    def test_edit_does_not_accept_model_calls_or_new_reference(self):
        body = self.source()
        for field in ({'provider':'x','model':'y'}, {'reference':'a'*32}, {'prompt':'run code'}, {'preset':'wheel-study'}):
            with self.subTest(field=field), self.assertRaises(CoreError): studio3d.start(self.root,{**body,**field},None)

    def test_skill_discovery_routing_disable_and_frozen_guidance(self):
        skills = Skills(self.root)
        self.addCleanup(skills.close)
        item = next(x for x in skills.list() if x['id']=='studio3d')
        self.assertNotIn('guidance_loaded',item)
        self.assertEqual(item['workflow']['stages'][-1]['status'],'external_only')
        for text in ('Blender建模：制作轮毂','修改3D模型：缩小部件','please edit a blender model','请帮我做3D建模','用 Blender 制作一个轮毂'):
            self.assertEqual(skills.select('auto',text)['id'],'studio3d')
        for text in ('不要用 Blender 制作模型','有人说“Blender建模”，什么意思','如果要修改3D模型呢','你好'):
            self.assertIsNone(skills.select('auto',text))
        selected = skills.select('studio3d','讨论参考')
        self.assertTrue(selected['guidance_loaded'])
        store = Dialogues(self.root)
        self.addCleanup(store.close)
        chat=store.create()
        cmd={'chat_id':chat,'request_id':'workflow-freeze','text':'做个模型','provider':'none','model':'none','reasoning':'default','skill':'studio3d'}
        store.begin(cmd,[],selected)
        skills.enable('studio3d',False)
        self.assertIn('source_sha256',store.context('workflow-freeze')[-1]['content'])
        with self.assertRaises(CoreError): skills.select('studio3d','做个模型')

    def test_execution_preserves_edit_receipt_and_zero_model_calls(self):
        body=self.source()
        folder=self.root/'artifacts/studio3d'/body['id'];folder.mkdir()
        with patch('host.studio3d.build',return_value={'configuration':self.scene}) as build, patch('host.studio3d.check'), patch('host.studio3d.update') as update:
            studio3d.LOCK.acquire()
            studio3d.run(self.root,body,None,None)
        self.assertIsNone(build.call_args.args[3])
        record=json.loads((folder/'receipt.json').read_text())
        self.assertEqual(record['derived_from'],body['edit'])
        self.assertEqual(record['edit']['new_model_calls'],0)
        self.assertTrue(any(c.kwargs.get('status')=='DELIVERED' for c in update.call_args_list))
        self.assertFalse(studio3d.LOCK.locked())

    def test_model_planning_loads_the_skill_in_actual_dialogue_context(self):
        root=self.root
        scene=self.scene
        captured={}
        class FakeDialogue:
            def submit_background(self, command):
                captured.update(command)
                skills=Skills(root);store=Dialogues(root)
                try:
                    guidance=skills.select(command['skill'],command['text'])
                    store.begin(command,[],guidance,lane='background')
                    captured['context']=store.context(command['request_id'])
                    store.finish(command['request_id'],{'status':'SUCCEEDED','text':canonical(scene)})
                finally:skills.close();store.close()
        body={'id':uuid.uuid4().hex,'prompt':'制作金属壳体','provider':'test','model':'test'}
        with patch('host.studio3d.build',return_value={}),patch('host.studio3d.check'),patch('host.studio3d.update') as update:
            studio3d.LOCK.acquire()
            studio3d.run(root,body,None,FakeDialogue())
        self.assertEqual(captured['skill'],'studio3d')
        self.assertIn('Blender 3D 制作与修改',captured['context'][-1]['content'])
        self.assertLessEqual(len(captured['text']),12000)
        self.assertTrue(any(c.kwargs.get('status')=='DELIVERED' for c in update.call_args_list))


if __name__ == '__main__': unittest.main()
