import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from host.core import Core
from host import studio3d_learning as service
from modules.context_knowledge.studio3d_experience import Studio3DExperience, catalog
from modules.skills.studio3d.learning_contract import validate, context, SCHEMA
from modules.skills.studio3d.hard_surface_review import prompt
from modules.skills.studio3d.reference_policy import from_recipe
from modules.skills.catalog import Skills
from sdk.protocol import CoreError


def contract():
    return {'schema':SCHEMA,'asset_id':'test-plate','family':'hard_surface',
        'parts':[{'id':'base','node':'plate','motion_owner':'base','motion':'fixed','closed_surface':True},
                 {'id':'knob','node':'knob','motion_owner':'base','motion':'coupled','closed_surface':True}],
        'attachments':[{'part':'knob','support':'base','max_gap':.003,'target_position':[0,0,.1]}],
        'rejected':['false-pod'],'symptoms':['rejected_parts','floating_attachment']}


class LearningContract(unittest.TestCase):
    def test_valid_and_copied(self):
        v=contract(); clean=validate(v); clean['parts'][0]['node']='other';self.assertEqual(v['parts'][0]['node'],'plate')

    def test_bad_contracts_are_rejected(self):
        cases=[lambda v:v.update(python='exec'),lambda v:v.update(asset_id='../escape'),lambda v:v.update(parts=[]),
               lambda v:v['parts'].append(copy.deepcopy(v['parts'][0])),lambda v:v['parts'][0].update(motion_owner='missing'),
               lambda v:v['parts'][0].update(motion_owner='knob'),lambda v:v['attachments'][0].update(target_position=[0,float('nan'),0]),
               lambda v:v['attachments'][0].update(max_gap=True),lambda v:v['attachments'][0].update(support='knob'),
               lambda v:v.update(rejected=['plate']),lambda v:v.update(reference_policy={'shield':'invented'}),
               lambda v:v.update(symptoms=['execute code']),lambda v:v['parts'][0].update(closed_surface='yes')]
        for change in cases:
            v=contract();change(v)
            with self.subTest(change=change),self.assertRaises(ValueError):validate(v)

    def test_asset_specific_shield_is_not_global(self):
        generic=prompt('front','test')
        self.assertNotIn('preserve those folds',generic)
        folded=prompt('front','test',reference_policy={'shield':'rearward_folded'})
        self.assertIn('preserve those folds',folded)
        flat=prompt('front','test',reference_policy={'shield':'flat'})
        self.assertIn('do not add folded side wings',flat)
        with self.assertRaises(ValueError):prompt('front','test',reference_policy={'shield':'invented'})

    def test_existing_asset_recipe_preserves_user_requirement(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);self.assertEqual(from_recipe(p),{'shield':'unspecified'})
            (p/'optimization-recipe.json').write_text(json.dumps({'reference_policy':{'folded_shield_authority':'User requires folds'}}))
            self.assertEqual(from_recipe(p)['shield'],'rearward_folded')

    def test_packaged_asset_recipe_takes_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'metadata').mkdir()
            (p/'optimization-recipe.json').write_text(json.dumps({'reference_policy':{'folded_shield_authority':'Legacy note'}}))
            (p/'metadata/optimization-recipe.json').write_text(json.dumps({'reference_policy':{'folded_shield_authority':'Current user requirement'}}))
            self.assertEqual(from_recipe(p),{'shield':'rearward_folded','notes':'Current user requirement'})

    def test_methods_fit_review_budget_without_losing_latest_correction(self):
        text=prompt('front','candidate',geometry_facts={'latest_user_correction':'REMOVE_REJECTED '+('x'*1800),'inventory':'y'*8000},
            reference_policy={'shield':'rearward_folded','notes':'a'*1200},methods=catalog()['methods'][:4],focus='z'*300)
        self.assertLessEqual(len(text),12000);self.assertIn('REMOVE_REJECTED',text)

    def test_policy_or_method_change_invalidates_cached_review_context(self):
        from modules.skills.studio3d.reference_policy import review_context_hash
        a=review_context_hash({'shield':'flat'},{'latest_user_correction':'keep'},catalog()['methods'][:1])
        b=review_context_hash({'shield':'rearward_folded'},{'latest_user_correction':'keep'},catalog()['methods'][:1])
        c=review_context_hash({'shield':'flat'},{'latest_user_correction':'remove'},catalog()['methods'][:1])
        self.assertEqual(len({a,b,c}),3)


class LearningExperience(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.store=Studio3DExperience(self.root);self.addCleanup(self.store.close)

    def test_catalog_sources_exist_and_scope_is_not_art_approval(self):
        from modules.context_knowledge.studio3d_experience import ROOT
        for card in catalog()['methods']:
            for source in card['sources']:self.assertTrue((ROOT/source['path']).is_file(),source)
            self.assertTrue(card['exclusions']);self.assertTrue(card['requires'] is not None)

    def test_conditions_and_versions_control_executable_tools(self):
        v=context(contract()); rows=self.store.retrieve(v)['methods']
        self.assertEqual({t for m in rows for t in m['tools']},{'remove_rejected','seat_attachment'})
        for key,value in [('tool_version','99'),('family','organic'),('symptoms',[])]:
            self.assertFalse(any(m['tools'] for m in self.store.retrieve({**v,key:value})['methods']))
        rows=self.store.retrieve({**v,'declared_target':False})['methods']
        self.assertFalse(any('seat_attachment' in m['tools'] for m in rows))

    def test_lefh_rule_cannot_leak_to_other_asset(self):
        v={**context(contract()),'family':'towed_artillery','shield':'rearward_folded','symptoms':['shield_mismatch']}
        self.assertFalse(self.store.retrieve(v)['methods'])
        self.assertEqual(self.store.retrieve({**v,'asset_id':'leFH18'})['methods'][0]['id'],'lefh18-folded-shield')

    def receipt(self,run='a',asset='asset1'):
        return {'schema':'jarvis.studio3d.learning.receipt.v1','id':run,'asset_id':asset,'status':'REPAIRED_DECLARED_CHECKS',
            'adoptions':[{'id':'remove-rejected-family','revision':1,'tool':'remove_rejected'}]}

    def test_idempotent_record_conflict_and_distinct_asset_count(self):
        r=self.receipt();self.assertFalse(self.store.record(r)['existing']);self.assertTrue(self.store.record(r)['existing'])
        with self.assertRaises(ValueError):self.store.record({**r,'status':'FAILED'})
        self.store.record(self.receipt('b'));self.assertEqual(self.store.summary()['distinct_assets'],1)
        self.store.record(self.receipt('c','asset2'));self.assertEqual(self.store.summary()['distinct_assets'],2)
        self.assertFalse(self.store.summary()['automatic_promotion'])
        self.assertFalse(self.store.summary()['cross_asset_art_gain_verified'])

    def test_late_counterexample_disables_future_use_and_preserves_history(self):
        self.store.record(self.receipt())
        self.store.feedback('event','a','remove-rejected-family','A supported decoration was incorrectly included')
        rows=self.store.retrieve(context(contract()))['methods']
        self.assertNotIn('remove-rejected-family',[r['id'] for r in rows])
        self.assertEqual(self.store.summary()['episodes'],1)
        self.assertTrue(self.store.feedback('event','a','remove-rejected-family','A supported decoration was incorrectly included')['existing'])
        with self.assertRaises(ValueError):self.store.feedback('event','a','remove-rejected-family','changed event')
        with self.assertRaises(ValueError):self.store.feedback('new','unknown','remove-rejected-family','not adopted')

    def test_record_unknown_tool_is_rejected(self):
        r=self.receipt();r['adoptions'][0]['tool']='python'
        with self.assertRaises(ValueError):self.store.record(r)
        self.assertEqual(self.store.summary()['episodes'],0)

    def test_changed_source_stops_adoption(self):
        altered=copy.deepcopy(catalog());altered['methods'][0]['sources'][0]['sha256']='0'*64
        with patch('modules.context_knowledge.studio3d_experience.catalog',return_value=altered):
            result=self.store.retrieve(context(contract()))
        self.assertNotIn('remove-rejected-family',[m['id'] for m in result['methods']])
        self.assertIn({'id':'remove-rejected-family','reason':'source_changed_or_missing'},result['rejected'])


class LearningHost(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);Core.initialize(self.root).close()

    def test_host_and_skill_share_disable_gate(self):
        self.assertEqual(len(service.plan(self.root,contract())['methods']),2)
        skills=Skills(self.root)
        try:skills.enable('studio3d',False)
        finally:skills.close()
        with self.assertRaises(CoreError):service.plan(self.root,contract())
        with self.assertRaises(CoreError):service.summary(self.root)

    def test_path_and_request_restrictions(self):
        for ident in ('../outside','a'*31,'Z'*32):
            with self.assertRaises(ValueError):service.folder_for(self.root,ident)
        with self.assertRaises(ValueError):service.start(self.root,{'path':'secret.glb'})
        with self.assertRaises(ValueError):service.start(self.root,{})
        with self.assertRaises(ValueError):service.feedback(self.root,{'python':'exec'})

    def test_restart_is_unknown_without_replay(self):
        folder=service.folder_for(self.root,'c'*32);folder.mkdir(parents=True)
        service.save(folder/'status.json',{'id':'c'*32,'status':'RUNNING','owner_pid':-1})
        self.assertEqual(service.state(self.root,'c'*32)['status'],'UNKNOWN')
        self.assertFalse((folder/'receipt.json').exists())

    def test_http_request_identity_retains_unknown_instead_of_replaying(self):
        import hashlib
        body={'id':'d'*32,'source_job':'e'*32,'contract':contract()}
        folder=service.folder_for(self.root,body['id']);folder.mkdir(parents=True)
        signature=hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest()
        service.save(folder/'accepted.json',{'signature':signature})
        service.save(folder/'status.json',{'id':body['id'],'status':'RUNNING','owner_pid':-1})
        result=service.start(self.root,body)
        self.assertTrue(result['existing']);self.assertEqual(result['status'],'UNKNOWN')
        with self.assertRaises(CoreError):service.start(self.root,{**body,'repair':True})

    def test_http_routes_use_host_policy_and_require_nonce(self):
        import http.client
        import threading
        from http.server import ThreadingHTTPServer
        from apps.workbench.server import Handler
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.data_root=self.root;server.nonce='local-test'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,body=None,nonce=True):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            headers={'Origin':f'http://127.0.0.1:{server.server_port}','Content-Type':'application/json'}
            if nonce:headers['X-Jarvis-Token']='local-test'
            conn.request(method,path,json.dumps(body) if body is not None else None,headers)
            r=conn.getresponse();raw=r.read();conn.close();return r.status,json.loads(raw)
        try:
            self.assertEqual(request('GET','/api/studio3d/learning')[1]['seed_methods'],10)
            self.assertEqual(request('POST','/api/studio3d/learning/plan',contract(),nonce=False)[0],403)
            status,body=request('POST','/api/studio3d/learning/plan',contract())
            self.assertEqual(status,200);self.assertEqual(len(body['methods']),2)
            self.assertEqual(request('POST','/api/studio3d/learning/run',{})[0],400)
            skills=Skills(self.root)
            try:skills.enable('studio3d',False)
            finally:skills.close()
            self.assertEqual(request('POST','/api/studio3d/learning/plan',contract())[0],400)
        finally:server.shutdown();server.server_close();thread.join(timeout=2)

    def test_formal_curriculum_does_not_count_diagnostics_as_practice(self):
        from modules.context_knowledge.studio3d_experience import ROOT
        v=json.loads((ROOT/'modules/skills/studio3d/learning-curriculum.json').read_text(encoding='utf-8'))
        self.assertEqual(len({r['id'] for r in v['cases']}),24)
        for split,count in v['splits'].items():self.assertEqual(sum(r['split']==split for r in v['cases']),count)
        self.assertEqual(v['formal_completed'],0)
        self.assertTrue(all(r['status']=='PENDING_REFERENCE' and not r['results'] for r in v['cases']))

    def test_failed_execution_retains_receipt_and_cost_unknowns(self):
        from test_studio3d import glb
        exe=self.root/'blender.exe';exe.write_bytes(b'fake')
        import hashlib
        prepared=self.root/'optional/studio3d/prepared.json';prepared.parent.mkdir(parents=True)
        prepared.write_text(json.dumps({'executable':str(exe),'executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}))
        ident='b'*32
        with patch('host.studio3d.readiness',return_value={'ready':True}),patch.object(service,'_process',side_effect=ValueError('native error')):
            with self.assertRaises(ValueError):service.run(self.root,glb(),contract(),ident=ident,repair=True,render=False)
        receipt=service.state(self.root,ident)
        self.assertEqual(receipt['status'],'FAILED');self.assertIsNone(receipt['cost']['total_usd'])
        self.assertFalse(receipt['candidate_usable']);self.assertEqual(receipt['adoptions'],[])
        self.assertEqual(service.summary(self.root)['episodes'],1)


if __name__=='__main__':unittest.main()

