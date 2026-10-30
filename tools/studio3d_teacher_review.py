"""Evidence-bound Jarvis analysis of a recorded teaching trial, without promotion.

This explicit CLI uses the existing Jarvis dialogue/usage/idempotence path. It
does not pretend that a model reply executed Blender or approved an asset.
"""
import argparse
import hashlib
import json
import msvcrt
import re
from pathlib import Path
from tools.studio3d_autopilot import Driver, ROOT, load, save, now
from modules.skills.studio3d.production_loop import decode


def evidence(asset, episode_name):
    if not re.fullmatch('[a-z0-9-]{1,70}',episode_name):raise ValueError('Invalid episode identity')
    folder=asset/'metadata/demonstrations'/episode_name;e=load(folder/'episode.json')
    if not re.fullmatch('[a-f0-9]{32}',e['run_id']):raise ValueError('Invalid native run identity')
    native=ROOT/'user-data/artifacts/studio3d-demonstration'/e['run_id'];receipt=load(native/'status.json')
    if receipt['status']!='BUILT_AWAITING_VISUAL_COMPARISON':raise ValueError('Actual completed demonstration required')
    for name in ('source.blend','model.blend','before-wheel-left.png','after-wheel-left.png'):
        if hashlib.sha256((native/name).read_bytes()).hexdigest()!=receipt['files'][name]['sha256']:raise ValueError('Demonstration evidence changed')
    return folder,e,native,receipt


def main():
    p=argparse.ArgumentParser();p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--episode',required=True)
    p.add_argument('--stage',choices=('consolidate','reference','redo-plan','profile-review','profile-plan'),required=True);a=p.parse_args()
    asset=a.asset_root.resolve()
    if not asset.is_relative_to(ROOT/'3DModels'):raise ValueError('Local asset required')
    folder,e,native,receipt=evidence(asset,a.episode)
    with (asset/'metadata/autopilot/run.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        driver=Driver(asset,'http://127.0.0.1:18282',0)
        request_key='teaching-'+a.episode+'-'+a.stage+'-v1'
        existing_path=folder/('jarvis-'+a.stage+'.json')
        if existing_path.exists():
            prior=load(existing_path)
            calls=[c for c in driver.state['calls'].values() if c['request_id']==prior['request_id']]
            if (len(calls)!=1 or calls[0]['status']!='SUCCEEDED' or decode(calls[0]['reply'])!=prior['reply']
                or prior['source_run']!=e['run_id']):raise ValueError('Saved review identity changed')
            print(json.dumps({'stage':a.stage,'status':'REUSED_RECORDED_RESULT','new_model_calls':0},ensure_ascii=False));return
        common='You are Jarvis assessing an exterior game-art Blender teaching case. Output strict JSON only. Separate observed pixels, verified action facts, and uncertain explanations. Do not invent measurements or historical rib counts. Never declare user approval, weight learning, independent reconstruction, or a generalized skill. '
        report=load(native/'report.json');contract=load(folder/'contract.json')
        action_facts={'actions':contract['actions'],'checks':report['checks'],'same_camera_before_after':True,'source_job':e['source_job']}
        if a.stage in ('profile-review','profile-plan'):
            if any(x['tool']!='radial_reprofile' for x in contract['actions']):raise ValueError('Profile demonstration required')
            if a.stage=='profile-review':
                from modules.skills.studio3d.paired_review import make_sheet
                sheet=folder/'wheel-profile-before-after.png'
                composition=make_sheet(native/'before-wheel-left.png',native/'after-wheel-left.png',sheet)
                save(folder/'comparison-sheet.json',composition)
                images=[asset/'reference-left.png',sheet]
                prompt=common+'CURRENT image1 is the full target reference. CURRENT image2 is an unchanged-pixel evidence sheet: TOP=original r25 BEFORE, BOTTOM=actual reprofile AFTER, same Blender camera/light. Judge only whether the visible profile shape moved toward the reference, keeping rib count unchanged as a controlled variable. Identify remaining count/tyre/hub/material differences separately. A new visible local defect cannot be hidden by detail. Do not approve the entire wheel. First observe pixels without an author verdict, then infer a limited candidate method. Return {"change":"better|same|worse|uncertain","observations":[],"regressions":[],"remaining":[],"method":{"when":[],"steps":[],"reject_when":[],"checks":[]},"local_lesson_ready":false,"limits":[]}. Set local_lesson_ready true only if a defensible narrow shape improvement has no visible local regression; never claim independent execution.\nVERIFIED_TOOL_FACTS='+json.dumps(action_facts,ensure_ascii=False)
            else:
                prior=load(folder/'jarvis-profile-review.json')
                images=[asset/'reference-left.png',native/'before-wheel-left.png']
                template=[]
                for action in contract['actions']:
                    action=dict(action)
                    for parameter_name in ('amplitude','crown_fraction','shoulder_fraction','end_blend','reason'):action.pop(parameter_name)
                    template.append(action)
                method={'method':prior['reply']['method'],'limits':prior['reply']['limits']}
                prompt=common+'CURRENT image1 is the target reference. CURRENT image2 is the original r25 BEFORE model, not the teacher result. Read the conditional method and independently choose an action with the same bounded radial_reprofile tool. You may also refuse with tool_gap. Original source and geometry facts are frozen. You cannot access the answer BLEND or supply code. Choose exactly both declared targets and preserve all template values. Choose amplitude in [0.008,0.034], crown_fraction [0.05,0.35], shoulder_fraction [0.10,0.40] with their sum <=0.75, end_blend [0.015,0.09], and a concise reason. These bounds are an art editing envelope, not engineering dimensions. Exact author-parameter reuse is recorded as replay, not independent success. Do not fabricate improvements or user approval. Reference rib count remains unresolved; this exercise preserves the source count and never teaches a historical count. The actual Blender source uses procedural painted material; appearance alone cannot establish that material channels are absent. Return {"decision":"execute|tool_gap","actions":[],"lesson_used":[],"checks":[],"limits":[]}.\nTEMPLATES='+json.dumps(template,ensure_ascii=False)+'\nCANDIDATE_METHOD='+json.dumps(method,ensure_ascii=False)
        elif a.stage=='consolidate':
            _,previous,old,_=evidence(asset,e['preceding_rejected_episode'])
            images=[old/'after-wheel-left.png',native/'after-wheel-left.png']
            prompt=common+'Image1 is a rejected .030 relief trial; image2 is a .010 trial. BOTH start from the SAME original r25; this is not a sequential subtraction. Original rib count and all other geometry/materials unchanged. Author observed excessive swelling in trial1. Infer only a CANDIDATE conditional lesson, retain limits and counterexamples. Return {"observations":[],"hypotheses":[],"method":{"when":[],"steps":[],"reject_when":[],"checks":[]},"unverified":[]}.\nFACTS='+json.dumps(action_facts,ensure_ascii=False)
        else:
            prior=load(folder/'jarvis-consolidate.json')
            if prior['status']!='CANDIDATE_NOT_PROMOTED':raise ValueError('Prior candidate lesson required')
            images=[asset/'reference-left.png',native/('after-wheel-left.png' if a.stage=='reference' else 'before-wheel-left.png')]
            prompt=common+'CURRENT Image1 is the full source reference; CURRENT Image2 is a real wheel close-up with different framing. Compare visible wheel construction only. HISTORICAL teacher trials used two different render images at the same camera. Their historical labels never refer to the CURRENT attached images.\nHISTORICAL_ACTION_FACTS='+json.dumps(action_facts,ensure_ascii=False)+'\nHISTORICAL_CANDIDATE_METHOD='+json.dumps(prior['reply']['method'],ensure_ascii=False)
            if a.stage=='reference':
                prompt+='\nReturn {"local_relief":"improved|not_improved|uncertain","remaining_defects":[],"ready_as_positive_lesson":false,"reasons":[],"unverified":[]}. The boolean may be true only for this narrow local lesson with stated limits; it does not approve the complete wheel.'
            else:
                review=load(folder/'jarvis-reference.json')
                prompt+='\nPRIOR_REVIEW='+json.dumps(review['reply'],ensure_ascii=False)
                correction=folder/'review-context-correction.json'
                if correction.exists():prompt+='\nHOST_EVIDENCE_CORRECTION='+json.dumps(load(correction),ensure_ascii=False)
                prompt+='\nFrom the original r25 input, propose either a bounded radial_relief action for disc-left/disc-right or an empty action list if the existing tool cannot fix the observed problem. Available fields exactly as FACTS.actions; amplitude must be >0 and <=0.0345, all other geometry parameters unchanged. You may select amplitude independently based on the lesson, but exact reuse counts only as replay. No code, no arbitrary objects or paths. Return {"decision":"execute|tool_gap","actions":[],"lesson_used":[],"checks":[],"limitations":[]}. Do not generate a cosmetic patch just to appear productive.'
        ids=[driver.upload(path,'PaK38 teaching '+a.stage) for path in images]
        reply=driver.call(request_key,prompt,ids);parsed=decode(reply)
        if not isinstance(parsed,dict):raise ValueError('Structured lesson object required')
        output={'schema':'jarvis.studio3d.teacher-review.v1','stage':a.stage,'status':'CANDIDATE_NOT_PROMOTED','at':now(),'request_id':driver.state['calls'][request_key]['request_id'],'source_run':e['run_id'],
                'inputs':[{'path':str(path.relative_to(asset)) if path.is_relative_to(asset) else str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in images],
                'reply':parsed,'independent_blender_execution':False,'cross_asset_transfer_verified':False,'user_approval':False}
        save(folder/('jarvis-'+a.stage+'.json'),output)
        from tools.studio3d_trial_report import update
        totals=update(asset)
        print(json.dumps({'stage':a.stage,'status':output['status'],'reply':parsed,'known_api_estimate':totals['costs']['known_api_estimated_usd']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
