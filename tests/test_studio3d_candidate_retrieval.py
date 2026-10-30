import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from modules.context_knowledge.studio3d_experience import Studio3DExperience

class AssetCandidates(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.asset=self.root/'3DModels/PaK38';self.meta=self.asset/'metadata';self.meta.mkdir(parents=True)
        patcher=patch('modules.context_knowledge.studio3d_experience.ROOT',self.root);patcher.start();self.addCleanup(patcher.stop)
        self.store=Studio3DExperience(self.root/'runtime');self.addCleanup(self.store.close)
        self.query={'asset_id':'PaK38','family':'towed_artillery','symptoms':['tone_split'],'facts':{'actual_channels':True},'tool_versions':{'inspection':'1.2.1'}}
        evidence=b'actual checked evidence';(self.meta/'evidence.json').write_bytes(evidence)
        self.card={'id':'tone-diagnosis','revision':1,'title':'Separate material and light','status':'CANDIDATE','promoted':False,'symptoms':['tone_split'],'requires':{'actual_channels':True},'tool_versions':{'inspection':'1.2.1'},'summary':'Inspect source channels before changing paint.','counterexamples':'Not proof all surfaces are correct.','evidence':[{'path':'metadata/evidence.json','bytes':len(evidence),'sha256':hashlib.sha256(evidence).hexdigest()}]}
        (self.meta/'learning-contract-intake.json').write_text(json.dumps({'asset_id':'PaK38','family':'towed_artillery'}))
        self.save([self.card])
    def save(self,cards):
        (self.meta/'local-methods.json').write_text(json.dumps({'schema':'jarvis.studio3d.local-methods.v1','asset_id':'PaK38','family':'towed_artillery','automatic_promotion':False,'cases':cards}))
    def get(self,query=None):return self.store.retrieve_candidates(self.asset,query or self.query)
    def test_matching_case_is_advisory_only(self):
        r=self.get();self.assertEqual(r['candidate_cases'][0]['id'],'tone-diagnosis');self.assertFalse(r['candidate_cases'][0]['executable']);self.assertFalse(r['execution_authorized']);self.assertFalse(r['automatic_promotion'])
    def test_wrong_asset_and_family_reject(self):
        for key,value in [('asset_id','leFH18'),('family','hard_surface')]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.get({**self.query,key:value})
    def test_unknown_precondition_cannot_match(self):
        r=self.get({**self.query,'facts':{}});self.assertFalse(r['candidate_cases']);self.assertEqual(r['rejected'][0]['reason'],'precondition_mismatch')
    def test_tool_version_and_unrelated_symptom_filter(self):
        for patch_,reason in [({'tool_versions':{'inspection':'0.0.1'}},'tool_version_mismatch'),({'symptoms':['floating_attachment']},'symptom_mismatch')]:
            r=self.get({**self.query,**patch_});self.assertFalse(r['candidate_cases']);self.assertEqual(r['rejected'][0]['reason'],reason)
    def test_changed_evidence_is_rejected(self):
        (self.meta/'evidence.json').write_text('Changed content');self.assertEqual(self.get()['rejected'][0]['reason'],'source_changed_missing_or_unsafe')
    def test_path_escape_cannot_read_other_asset(self):
        self.card['evidence'][0]['path']='../leFH18/private.json';self.save([self.card]);self.assertFalse(self.get()['candidate_cases'])
        with self.assertRaises(ValueError):self.store.retrieve_candidates(self.root,self.query)
    def test_quarantine_blocks_later_use(self):
        self.card['status']='QUARANTINED';self.save([self.card]);self.assertEqual(self.get()['rejected'][0]['reason'],'quarantined')
    def test_duplicate_identity_and_promotion_fail_closed(self):
        self.save([self.card,self.card])
        with self.assertRaises(ValueError):self.get()
        self.card['promoted']=True;self.save([self.card])
        with self.assertRaises(ValueError):self.get()
    def test_deterministic_ranking_and_limit(self):
        other=copy.deepcopy(self.card);other.update(id='other-case',symptoms=['tone_split','lighting_uncertain']);self.save([self.card,other]);q={**self.query,'symptoms':['tone_split','lighting_uncertain']}
        r=self.store.retrieve_candidates(self.asset,q,1);self.assertEqual([c['id'] for c in r['candidate_cases']],['other-case'])
    def test_untyped_query_and_extra_execution_fields_reject(self):
        for patch_ in ({'python':'bad'},{'facts':{'actual_channels':'yes'}},{'symptoms':[]},{'tool_versions':{'inspection':'latest'}}):
            with self.subTest(patch_=patch_),self.assertRaises(ValueError):self.get({**self.query,**patch_})

if __name__=='__main__':unittest.main()
