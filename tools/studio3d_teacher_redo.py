"""Execute an already recorded Jarvis plan once; never makes a model request."""
import argparse
import hashlib
import msvcrt
import re
import uuid
from pathlib import Path
from tools.studio3d_autopilot import ROOT,load,save,now
from tools.studio3d_demonstration import record_episode
from tools.studio3d_trial_report import update
from modules.skills.studio3d.teacher_redo import validate_plan
from host.studio3d_high_finish import native_asset_operation


def main():
    p=argparse.ArgumentParser();p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--case',required=True);p.add_argument('--episode',required=True)
    a=p.parse_args();asset=a.asset_root.resolve()
    if not asset.is_relative_to(ROOT/'3DModels') or any(not re.fullmatch('[a-z0-9-]{1,70}',x) for x in (a.case,a.episode)):raise ValueError('Invalid bounded episode')
    with (asset/'metadata/autopilot/run.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        teacher=asset/'metadata/demonstrations'/a.case;plan_path=teacher/'jarvis-profile-plan.json';plan=load(plan_path)
        state=load(asset/'metadata/autopilot/state.json');call=next(c for c in state['calls'].values() if c['request_id']==plan['request_id'])
        if call['status']!='SUCCEEDED' or plan['independent_blender_execution']:raise ValueError('Successful unexecuted model plan required')
        from modules.skills.studio3d.production_loop import decode
        if decode(call['reply'])!=plan['reply']:raise ValueError('Model output was edited')
        for prior in (asset/'metadata/demonstrations').glob('*/method-adoption.json'):
            if load(prior).get('plan_request')==plan['request_id']:
                raise ValueError('This plan already has an execution record; inspect it without replay')
        contract,adoption=validate_plan(plan['reply'],load(teacher/'contract.json'))
        folder=asset/'metadata/demonstrations'/a.episode;folder.mkdir(parents=True,exist_ok=False)
        adoption.update(at=now(),plan_request=plan['request_id'],plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                        method_sha256=hashlib.sha256((teacher/'jarvis-profile-review.json').read_bytes()).hexdigest(),source_case=a.case)
        save(folder/'method-adoption.json',adoption)
        if contract is None:
            save(folder/'episode.json',{'status':'DECLINED_TOOL_GAP','author':'Jarvis','adoption':adoption});print('DECLINED_TOOL_GAP');return
        current=load(asset/'metadata/current-model.json');source=load(teacher/'episode.json')
        if source['source_job']!=current['job_id'] or source['source_blend_sha256']!=current['blend_sha256']:raise ValueError('Frozen baseline changed')
        ident=uuid.uuid4().hex;contract['goal']='Jarvis redo from original source, using recorded conditional profile method; awaiting actual visual verification.'
        contract['evidence']='Bound method adoption in this episode; chosen parameters are the unedited Jarvis reply. Compare actual before/after renders.'
        save(folder/'contract.json',contract);save(folder/'episode.json',{'run_id':ident,'source_job':current['job_id'],'source_blend_sha256':current['blend_sha256'],
            'author':'Jarvis','status':'RUNNING_LOCAL_DEMONSTRATION','created_at':now(),'user_approval':False,'adoption':adoption})
        try:
            result=native_asset_operation(ROOT/'user-data',current['job_id'],contract,ident=ident,operation='demonstration')
        finally:
            if (ROOT/'user-data/artifacts/studio3d-demonstration'/ident/'status.json').exists():record_episode(asset,a.episode,ident)
            update(asset)
        episode=load(folder/'episode.json');episode['jarvis_independent_redo']='EXECUTED_AWAITING_VISUAL_REVIEW';save(folder/'episode.json',episode)
        current['working_candidate']={'id':a.episode,'status':episode['jarvis_independent_redo'],'episode':'metadata/demonstrations/'+a.episode+'/episode.json',
                                     'preview':'metadata/demonstrations/'+a.episode+'/after/wheel-left.png','not_current_retained_model':True,'user_approval':False}
        save(asset/'metadata/current-model.json',current);update(asset)
        print({'id':ident,'status':result['status'],'adoption':adoption['mode']},flush=True)


if __name__=='__main__':main()
