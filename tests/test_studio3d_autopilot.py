import copy
import json
import tempfile
import unittest
from pathlib import Path
from modules.skills.studio3d.artillery_recipe import build, parameters, PARAMETERS, VARIANTS, shield_crest
from modules.skills.studio3d.production_loop import validate_patch, adoption, patch_prompt, candidate_lesson, digest
from modules.skills.studio3d.hard_surface_review import VIEWS
from modules.skills.studio3d.review_evidence import candidate_manifest, verify_manifest


def reviews(high=1):
    return [{'view':v,'verdict':'needs_revision','corrections':[{'feature':'wheel spacing','visible_evidence':'track too narrow','action':'increase track slightly','severity':'high' if high else 'low','confidence':'high','kind':'geometry'}],'reference_conflicts':[],'camera_caveat':''} for v in VIEWS]


def patch():
    return {'source_digest':'source','changes':[{'parameter':'track','value':2.05,'group':'wheels','evidence':[{'view':'front','correction':0}],'reason':'correct observed spacing'}],'unresolved':[]}


class BoundedProduction(unittest.TestCase):
    def test_local_patch_keeps_unrelated_source_data_identical(self):
        from modules.skills.studio3d.semantic_patch import merge
        source,sem=build();new,nsem=build({'shield_curve':.2,'wheel_form':2})
        result,meta=merge(source,sem,new,nsem,[{'group':'shield','parameter':'shield_curve'}])
        old={o['id']:o for o in source['objects']};after={o['id']:o for o in result['objects']}
        for name,group in sem['groups'].items():
            if group!='shield':self.assertEqual(old[name],after[name])
        self.assertEqual(result['materials'],source['materials']);self.assertEqual(meta['mutation_receipt']['declared_groups'],['shield'])

    def test_finish_does_not_replace_geometry_after_recipe_changes(self):
        from modules.skills.studio3d.semantic_patch import merge
        source,sem=build();new,nsem=build({'finish_detail':2,'wheel_form':2})
        result,meta=merge(source,sem,new,nsem,[{'group':'finish','parameter':'finish_detail'}])
        self.assertEqual(result['objects'],source['objects']);self.assertTrue(meta['mutation_receipt']['materials_changed'])
        self.assertEqual(result['render']['engine'],'CYCLES')

    def test_cradle_variant_replaces_its_declared_carriage_seat(self):
        from modules.skills.studio3d.semantic_patch import merge
        source,sem=build();new,nsem=build({'assembly_detail':1})
        result,meta=merge(source,sem,new,nsem,[{'group':'cradle','parameter':'assembly_detail'}])
        ids={o['id'] for o in result['objects']}
        self.assertNotIn('central-pedestal',ids);self.assertIn('layered-saddle',ids)
        self.assertEqual(meta['mutation_receipt']['declared_groups'],['carriage','cradle'])

    def test_surface_work_gets_a_turn_after_retained_geometry(self):
        from modules.skills.studio3d.production_loop import repair_focus
        rows=reviews()
        for row in rows:
            row['corrections']=[{'kind':'material','severity':'medium','confidence':'high'}]
        iterations=[{'adoption':{'accepted':True},'proposed_actions':[{'group':'shield'}]} for _ in range(3)]
        self.assertEqual(repair_focus(iterations,rows),'finish')
        iterations[-1]['adoption']['accepted']=False
        self.assertIsNone(repair_focus(iterations,rows))
        iterations[-1]['adoption']['accepted']=True
        rows[0]['corrections'].append({'kind':'geometry','severity':'high','confidence':'high'})
        self.assertIsNone(repair_focus(iterations,rows))

    def test_rigid_frame_preserves_attached_distances(self):
        import math
        from modules.skills.studio3d.assembly_frames import orient_z
        parts=[{'id':'a','position':[-2,1,.2]},{'id':'b','position':[-2.2,1,.4]}]
        def distance():return sum((a-b)**2 for a,b in zip(parts[0]['position'],parts[1]['position']))
        before=distance();orient_z(parts,[-2,1,.2],math.radians(23));self.assertAlmostEqual(before,distance())

    def test_comparison_sheet_keeps_original_render_pixels(self):
        from PIL import Image
        from modules.skills.studio3d.paired_review import make_sheet
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'a.png';b=root/'b.png';c=root/'c.png'
            Image.new('RGB',(48,30),(21,40,90)).save(a);Image.new('RGB',(48,30),(84,33,12)).save(b)
            report=make_sheet(a,b,c)
            with Image.open(c) as sheet,Image.open(a) as first,Image.open(b) as second:
                self.assertEqual(sheet.crop((0,32,48,62)).tobytes(),first.tobytes())
                self.assertEqual(sheet.crop((0,94,48,124)).tobytes(),second.tobytes())
            self.assertEqual(len(report['source_sha256']),2)

    def test_cost_ledger_retains_unknown_but_zero_for_no_call(self):
        from modules.skills.studio3d.production_receipt import model_stage,summary
        unknown=model_stage('pending',{'status':'UNKNOWN'})
        rejected=model_stage('invalid',{'status':'REJECTED_BEFORE_INVOCATION','model_calls':0})
        self.assertIsNone(unknown['estimated_usd']);self.assertEqual(rejected['estimated_usd'],0)
        self.assertIsNone(summary([unknown,rejected])['complete_total_usd'])

    def test_concave_extrusion_preserves_notch_area(self):
        from modules.skills.studio3d.assembly_geometry import triangulate
        outline=[[0,0],[3,0],[3,1],[1,1],[1,3],[0,3]]
        triangles=triangulate(outline);area=0
        for face in triangles:
            a,b,c=[outline[i] for i in face]
            area+=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
        self.assertAlmostEqual(area,5)

    def test_material_observation_survives_planning_truncation(self):
        r=reviews()
        for row in r:row['corrections']=row['corrections']*5+[{'feature':'paint layer','visible_evidence':'uniform coating','action':'improve finish','severity':'medium','confidence':'medium','kind':'material'}]
        out=patch_prompt(parameters(),r,'source',{})
        self.assertIn('paint layer',out);self.assertIn('"index":5',out)

    def test_direct_comparison_rejects_local_regression(self):
        from modules.skills.studio3d.paired_review import decide, parse
        rows=[{'view':v,'change':'better','confidence':'medium','improvements':['visible fitted cover'],'regressions':[],'remaining':['plain finish'],'caveat':''} for v in VIEWS]
        self.assertTrue(decide(rows)['accepted'])
        rows[3]['regressions']=['new floating handle']
        rows[3]=parse(json.dumps(rows[3]),'rear')
        self.assertFalse(decide(rows)['accepted']);self.assertEqual(rows[3]['change'],'worse')

    def test_direct_comparison_requires_complete_reliable_evidence(self):
        from modules.skills.studio3d.paired_review import decide
        rows=[{'view':v,'change':'same','confidence':'medium','improvements':[],'regressions':[],'remaining':[],'caveat':''} for v in VIEWS]
        self.assertFalse(decide(rows)['accepted'])
        rows[0].update(change='better',improvements=['visible crease closer to reference'])
        self.assertFalse(decide(rows[:4])['accepted'])
        rows[1]['confidence']='low';self.assertFalse(decide(rows)['accepted'])

    def test_default_recipe_and_semantic_inventory(self):
        scene,sem=build();ids={o['id'] for o in scene['objects']}
        self.assertEqual(ids,set(sem['groups']));self.assertEqual(ids,set(sem['motion_owners']))
        self.assertNotIn('asset_pipeline',scene);self.assertTrue(scene['render']['five_views'])
        self.assertEqual(sem['motion_owners']['handwheel-left'],'handwheel-left')
        self.assertEqual(sum(o['id']=='sight-cut' for o in scene['objects']),1)

    def test_largest_valid_recipe_still_fits_contract(self):
        build({'wheel_ribs':12,'track':2.3,'shield_width':2.15,'trail_spread':1.65,**{k:PARAMETERS[k][2] for k in VARIANTS}})

    def test_outer_shield_bolts_follow_shoulder_surface(self):
        p=parameters({'shield_profile':1});scene,_=build(p)
        bolts=next(o for o in scene['objects'] if o['id']=='fasteners-shield')
        for x,y,z in bolts['params']['vertices']:
            self.assertLess(z,shield_crest(p,y)+.001)

    def test_control_shaft_reaches_handwheel_hub(self):
        scene,sem=build({'control_detail':1})
        support=next(o for o in scene['objects'] if o['id']=='connected-control-housing')
        shaft=[v for v in support['params']['vertices'] if abs(v[0]+.4)<.035 and abs(v[2]-.9)<.035]
        self.assertGreaterEqual(max(v[1] for v in shaft),.5)
        self.assertEqual(sem['motion_owners']['handwheel-left'],'handwheel-left')

    def test_curved_double_policy_is_established(self):
        from modules.skills.studio3d.reference_policy import guidance
        text=guidance({'shield':'curved_double'})
        self.assertIn('established',text);self.assertNotIn('unestablished',text)

    def test_topology_variant_requires_same_evidence_as_scalar(self):
        p=patch();p['changes'][0].update(parameter='wheel_form',value=1)
        updated,_=validate_patch(p,parameters(),reviews(),'source');self.assertEqual(updated['wheel_form'],1)
        p['changes'][0]['value']=.5
        with self.assertRaises(ValueError):validate_patch(p,parameters(),reviews(),'source')

    def test_realistic_large_review_is_bounded_without_changing_indices(self):
        rows=reviews()
        for row in rows:
            row['corrections']=[{**row['corrections'][0],'visible_evidence':'细节'*150,'action':'修复'*150} for _ in range(7)]
            row['camera_caveat']='相机'*200
        failures=[{'iteration':'r3','changes':[['wheel_form',2]],'reason':'regression','comparisons':[{'view':v,'change':'worse','regressions':['缺陷'*300],'improvements':['改善'*300]} for v in VIEWS]}]*2
        out=patch_prompt(parameters(),rows,'source',{'notes':'policy'},failures)
        self.assertLessEqual(len(out),12000);self.assertIn('omitted_findings',out)

    def test_no_paths_code_or_nan_in_parameter_data(self):
        for invalid in ({'python':'print(1)'},{'track':float('nan')},{'track':True},{'track':100},{'wheel_ribs':6.1},{'shield_top':1.2,'barrel_height':1.38}):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):parameters(invalid)

    def test_edit_has_evidence_and_leaves_source_unchanged(self):
        source=parameters();before=copy.deepcopy(source);updated,actions=validate_patch(patch(),source,reviews(),'source')
        self.assertEqual(source,before);self.assertEqual(updated['track'],2.05);self.assertEqual(actions[0]['before'],1.95)

    def test_reject_stale_wrong_group_unobserved_or_too_large_edits(self):
        edits=[lambda p:p.update(source_digest='stale'),lambda p:p['changes'][0].update(group='barrel'),lambda p:p['changes'][0].update(value=2.3),
               lambda p:p['changes'][0]['evidence'][0].update(correction=5),lambda p:p['changes'][0].update(parameter='execute'),lambda p:p['changes'].append(copy.deepcopy(p['changes'][0]))]
        for edit in edits:
            value=patch();edit(value)
            with self.assertRaises(ValueError):validate_patch(value,parameters(),reviews(),'source')

    def test_camera_and_low_confidence_cannot_drive_geometry(self):
        for field,value in [('confidence','low'),('kind','camera')]:
            r=reviews();r[2]['corrections'][0][field]=value # VIEWS order front index2
            with self.assertRaises(ValueError):validate_patch(patch(),parameters(),r,'source')

    def test_material_and_lighting_need_matching_evidence(self):
        for name,group,value in [('roughness','finish',.55),('exposure','lighting',-.30)]:
            p=patch();p['changes'][0].update(parameter=name,group=group,value=value)
            with self.assertRaises(ValueError):validate_patch(p,parameters(),reviews(),'source')

    def test_regression_rejected_even_when_total_score_improves(self):
        before=reviews();after=reviews(0);before[0]['corrections']=[];after[0]['corrections'][0]['severity']='high'
        self.assertFalse(adoption(before,after)['accepted'])

    def test_unknown_or_missing_views_cannot_pass(self):
        self.assertFalse(adoption(reviews(),reviews()[:4])['accepted'])
        after=reviews(0);after[1]['verdict']='uncertain';self.assertFalse(adoption(reviews(),after)['accepted'])

    def test_improvement_is_not_user_approval_or_global_learning(self):
        outcome=adoption(reviews(),reviews(0));self.assertTrue(outcome['accepted']);self.assertFalse(outcome['user_approval'])
        lesson=candidate_lesson('a','b',[],outcome);self.assertEqual(lesson['lifecycle'],'CANDIDATE');self.assertFalse(lesson['eligible_for_global_retrieval'])

    def test_planner_context_contains_all_views_and_bounded_interface(self):
        out=patch_prompt(parameters(),reviews(),'source',{'notes':'one left slot'})
        self.assertLessEqual(len(out),12000)
        for view in VIEWS:self.assertIn(view,out)
        self.assertIn('source_digest',out)

    def test_render_hash_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);model=root/'model.glb';model.write_bytes(b'model')
            files={v:root/(v+'.png') for v in VIEWS}
            for v,p in files.items():p.write_bytes(v.encode())
            manifest=candidate_manifest(model,files,iteration='r0');verify_manifest(manifest)
            files['top'].write_bytes(b'replaced image')
            with self.assertRaises(ValueError):verify_manifest(manifest)


if __name__=='__main__':unittest.main()
