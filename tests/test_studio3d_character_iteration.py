import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch as mock
from tools import studio3d_character_iterate as module
from modules.skills.studio3d.character_contract import parameters


class IterationSafety(unittest.TestCase):
    def driver(self,root):
        d=module.Iteration.__new__(module.Iteration)
        d.state={'calls':{},'route':{'provider':'example','model':'example'}}
        d.trial={'reference_ids':{'front':'r'}}
        d.check=lambda:None;d.persist=lambda:None
        return d

    def test_model_plan_only_applies_bounded_values(self):
        with tempfile.TemporaryDirectory() as tmp, mock.object(module,'ASSET',Path(tmp)):
            d=self.driver(tmp);(Path(tmp)/'r02').mkdir()
            d.call=lambda *args:json.dumps({'updates':{'head_scale':1.03},'reason':'head size'})
            item={'id':'r02','parameters':parameters(),'reviews':{'front':'test'}}
            self.assertEqual(d.plan(item)['head_scale'],1.03)
            d.call=lambda *args:json.dumps({'updates':{'head_scale':1.15},'reason':'too large'})
            with self.assertRaises(ValueError):d.plan(item)
            d.call=lambda *args:json.dumps({'updates':{'python':'dangerous'},'reason':'invalid'})
            with self.assertRaises(ValueError):d.plan(item)

    def test_unknown_prior_build_is_never_replayed(self):
        with tempfile.TemporaryDirectory() as tmp, mock.object(module,'ASSET',Path(tmp)):
            d=self.driver(tmp)
            with mock.object(module,'_process',side_effect=AssertionError('must not run')):
                with self.assertRaisesRegex(RuntimeError,'no replay'):
                    d.build({'id':'r02','status':'BUILDING','run_id':'old'})

    def test_call_budget_counts_unknown_without_zero_pricing(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=self.driver(tmp)
            d.state['calls']={str(i):{'known_usd':None} for i in range(10)}
            with mock.object(module.api,'post',side_effect=AssertionError('must not submit')):
                with self.assertRaisesRegex(RuntimeError,'budget'):
                    d.call('new','prompt',[])

    def test_next_iteration_loads_actual_preceding_review(self):
        with tempfile.TemporaryDirectory() as tmp, mock.object(module,'ASSET',Path(tmp)):
            root=Path(tmp);(root/'character-r02').mkdir();d=self.driver(tmp)
            reviews={'front':'recent opinion'}
            module.save(root/'character-r02/reviews.json',reviews)
            module.save(root/'character-r02/manifest.json',{'files':{}})
            d.state['iterations']=[{'id':'character-r02','status':'REVIEWED','reviews':reviews,
                                    'manifest_sha256':module.sha(root/'character-r02/manifest.json')}]
            text,src=d.prior_review({'source_iteration':'character-r02'},'front')
            self.assertEqual(text,'recent opinion');self.assertEqual(src['kind'],'preceding_iteration')
            module.save(root/'character-r02/reviews.json',{'front':'tampered'})
            with self.assertRaisesRegex(ValueError,'changed'):
                d.prior_review({'source_iteration':'character-r02'},'front')


if __name__=='__main__':unittest.main()
