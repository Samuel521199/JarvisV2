import json
import unittest
from modules.skills.studio3d.hard_surface_review import parse,prompt,review_gate,VIEWS

def opinion(view='right',corrections=None,verdict='near_match'):
    return {'view':view,'verdict':verdict,'corrections':corrections or [],'user_approval':True,'lod_authorized':True}

class HardSurfaceReview(unittest.TestCase):
    def test_missing_view_blocks_gate_and_models_cannot_approve_lod(self):
        rows=[parse(json.dumps(opinion(v))) for v in VIEWS]
        self.assertFalse(review_gate(rows[:-1])['model_based_near_match'])
        self.assertTrue(review_gate(rows)['model_based_near_match'])
        self.assertFalse(review_gate(rows)['lod_authorized'])
        self.assertTrue(all(not r['user_approval'] and not r['lod_authorized'] for r in rows))

    def test_significant_correction_overrides_success_label(self):
        c={'feature':'tire','visible_evidence':'Visible block tread differs','action':'Use shallow grooves','severity':'high','confidence':'high','kind':'geometry'}
        parsed=parse(json.dumps(opinion(corrections=[c])))
        self.assertEqual(parsed['verdict'],'needs_revision')
        rows=[opinion(v) for v in VIEWS];rows[0]['corrections']=[c]
        self.assertFalse(review_gate(rows)['model_based_near_match'])

    def test_retained_real_response_repaired_without_paid_retry(self):
        c={'feature':'paint','visible_evidence':'Uniform gray','action':'Add localized wear','severity':'medium','confidence':'material'}
        r=parse('```json\n'+json.dumps(opinion('正面', [c]))+'\n```','front')
        self.assertEqual((r['view'],r['model_view_label']),('front','正面'))
        self.assertEqual((r['corrections'][0]['confidence'],r['corrections'][0]['kind']),('low','material'))

    def test_invalid_review_cannot_silently_pass(self):
        for v in ([],opinion(corrections=['instruction']),opinion(corrections=[{}]),opinion('invalid')):
            with self.subTest(v=v),self.assertRaises(ValueError):parse(json.dumps(v))

    def test_review_includes_occlusion_and_conflict_rules(self):
        text=prompt('front','r7',geometry_facts={'wheel_ribs':12})
        self.assertIn('Do not infer a hidden part is missing',text)
        self.assertIn('Do not assume every asset has them',text)
        self.assertIn('wheel_ribs',text)
        with self.assertRaises(ValueError):prompt('unknown','r7')

    def test_five_detail_crops_cannot_pass_whole_asset(self):
        rows=[dict(opinion(v),coverage='detail') for v in VIEWS]
        gate=review_gate(rows)
        self.assertFalse(gate['all_five_reviewed'])
        self.assertFalse(gate['model_based_near_match'])

    def test_latest_user_override_survives_large_inventory(self):
        facts={'long_old_inventory':'x'*5000,
               'latest_user_correction':'Remove both rejected outer pods; do not recreate them.',
               'barrel_breech_priority':'Use current top and rear references for this exterior assembly.'}
        text=prompt('rear','revision',geometry_facts=facts)
        self.assertIn(facts['latest_user_correction'],text)
        self.assertIn(facts['barrel_breech_priority'],text)
        self.assertLess(text.index(facts['latest_user_correction']),text.index('long_old_inventory'))

    def test_closeup_cannot_replace_failed_full_view(self):
        rows=[opinion(v) for v in VIEWS]
        rows[0]['verdict']='needs_revision'
        rows.append(dict(opinion(VIEWS[0]),coverage='detail'))
        self.assertFalse(review_gate(rows)['model_based_near_match'])
        self.assertIn('cropped-out parts',prompt('front','revision',focus='shield aperture'))

if __name__=='__main__':unittest.main()
