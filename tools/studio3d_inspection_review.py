"""Supplemental visual evidence used by the persistent production controller."""
import json,uuid,hashlib
from pathlib import Path
from modules.skills.studio3d.hard_surface_review import VIEWS,prompt,parse,review_gate
from modules.skills.studio3d.render_inspection import VERSION


def inspect(driver,iteration):
    from tools.studio3d_autopilot import load,save,sha,ROOT
    from host.studio3d_high_finish import native_asset_operation
    folder=driver.folder/iteration['id'];native=load(folder/'report.json');semantic=load(folder/'semantics.json')
    names={o['id'] for o in native['objects']}
    reference=load(driver.asset/'metadata/inspection/contract.json')
    config={k:reference[k] for k in ('bounds','views','resolution','samples')}
    config['regions']={g:[n for n,group in semantic['groups'].items() if group==g and n in names] for g in ('wheel-left','breech','controls','trail-left','shield')}
    row=iteration.get('inspection')
    if row is None:
        row={'id':uuid.uuid4().hex,'status':'CREATED','contract':config,'source_job':iteration['job_id'],'version':VERSION}
        iteration['inspection']=row;driver.persist()
    if row['contract']!=config:raise ValueError('Frozen inspection contract changed')
    if row['status']=='CREATED':
        row['status']='SUBMITTING';driver.persist()
        try:
            result=native_asset_operation(ROOT/'user-data',iteration['job_id'],config,ident=row['id'],operation='inspection')
        except BaseException as error:
            row.update(status='UNKNOWN',error=str(error));driver.persist();raise
        row.update(status=result['status'],elapsed_seconds=result.get('elapsed_seconds'),started_at=result.get('started_at'),finished_at=result.get('finished_at'))
        driver.persist()
    native_folder=ROOT/'user-data/artifacts/studio3d-inspection'/row['id']
    # Idempotent host lookup never repeats a SUBMITTING/UNKNOWN native call.
    result=load(native_folder/'status.json')
    if result['status']!='BUILT_AWAITING_VISUAL_COMPARISON':raise ValueError('Inspection incomplete; retain and inspect original job')
    for name,info in result['files'].items():
        if sha(native_folder/name)!=info['sha256']:raise ValueError('Inspection artifact changed')
    if row['status']=='REVIEWED':
        # Preserve historical review prompts/results across policy revisions.
        # A changed policy governs new observations, never paid replay of old ones.
        saved=load(folder/'inspection-reviews.json')
        if set(r['view'] for r in saved)!=set(VIEWS) or any(r.get('native_run')!=row['id'] for r in saved):raise ValueError('Frozen inspection review incomplete')
        if row.get('reviews_sha256') and sha(folder/'inspection-reviews.json')!=row['reviews_sha256']:raise ValueError('Frozen inspection review changed')
        return saved
    reviews=[]
    for view in VIEWS:
        ref=Path(driver.state['native_references'][view]['path'])
        if sha(ref)!=driver.state['native_references'][view]['sha256']:raise ValueError('Reference changed')
        actual=native_folder/('inspection-'+view+'.png')
        facts={'reference_priority':driver.policy['notes'],'candidate_wheel_ribs':iteration['parameters']['wheel_ribs'],'candidate_trail_pose':'deployed','camera_evidence':next(x for x in result['report']['views'] if x['view']==view),
               'constraints':'Supplemental slightly oblique orthographic inspection, not exact projection calibration. Source geometry unchanged. Do not infer absent parts from occlusion.'}
        # Full native projection tables stay in the receipt; prompt only needs direction and frame.
        facts['camera_evidence']={k:v for k,v in facts['camera_evidence'].items() if k!='regions'}
        request=prompt(view,iteration['id']+'-inspection',geometry_facts=facts,reference_policy=driver.policy,methods=driver.methods)
        ids=[driver.upload(ref,view+' target'),driver.upload(actual,iteration['id']+' supplemental '+view)]
        parsed=parse(driver.call(iteration['id']+'-inspection-review-'+VERSION+'-'+view,request,ids),view)
        parsed.update(coverage='full',evidence='supplemental_actual_render',native_run=row['id'])
        reviews.append(parsed);save(folder/'inspection-reviews.json',reviews)
    row.update(status='REVIEWED',gate=review_gate(reviews),reviews_sha256=sha(folder/'inspection-reviews.json'));driver.persist()
    return reviews
