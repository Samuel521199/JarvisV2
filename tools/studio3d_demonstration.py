"""Run one receipt-bound first-party Blender teaching example through Jarvis."""
import argparse
import hashlib
import json
import msvcrt
import shutil
from pathlib import Path
from host.studio3d_high_finish import native_asset_operation
from tools.studio3d_autopilot import ROOT, load, save, now


def record_episode(asset, episode_name, ident):
    """Archive actual tool outputs and costs; this never approves the candidate."""
    import re
    if not re.fullmatch('[a-z0-9-]{1,70}',episode_name) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Invalid episode identity')
    folder=asset/'metadata/demonstrations'/episode_name;native=ROOT/'user-data/artifacts/studio3d-demonstration'/ident
    receipt=load(native/'status.json');episode=load(folder/'episode.json')
    if episode['run_id']!=ident:raise ValueError('Episode run mismatch')
    registry=asset/'metadata/native-tool-runs.json';runs=load(registry) if registry.exists() else {'runs':[]}
    if not any(r['id']==ident for r in runs['runs']):
        runs['runs'].append({'id':ident,'kind':'demonstration','scope':episode_name+'; authored trial, no high-model approval'})
        save(registry,runs)
    episode.update(updated_at=now(),native_status=receipt['status'],status='BUILT_AWAITING_LOCAL_REVIEW' if receipt['status']=='BUILT_AWAITING_VISUAL_COMPARISON' else receipt['status'],
                   user_approval=False,lod_authorized=False,jarvis_independent_redo='NOT_RUN',cross_asset_transfer='NOT_RUN',files={})
    copies={'status.json':'native-receipt.json'}
    if receipt['status']=='BUILT_AWAITING_VISUAL_COMPARISON':
        copies.update({'source.blend':'before/model.blend','model.blend':'after/model.blend','model.glb':'after/model.glb','report.json':'checks.json','actions.jsonl':'actions.jsonl','format-validation.json':'format-validation.json'})
        for view in receipt['report']['views']:copies[view['file']]=view['stage']+'/'+view['view']+'.png'
    for source,target in copies.items():
        p=native/source;expected=receipt.get('files',{}).get(source,{}).get('sha256')
        if expected and hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('Native output changed')
        dest=folder/target;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        episode['files'][target]={'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size}
    episode['cost']={'native_seconds':receipt.get('elapsed_seconds'),'native_model_calls':0,'native_api_usd':0,'authoring_tokens':None,'authoring_usd':None,'local_compute_usd':None,'total_usd':None,'model_requests':'See autopilot/state.json and costs.json; UNKNOWN is not zero.'}
    save(folder/'episode.json',episode)
    return episode


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data-root',type=Path,default=Path('user-data'))
    p.add_argument('--source-job',required=True)
    p.add_argument('--contract',type=Path,required=True)
    p.add_argument('--id',required=True)
    p.add_argument('--asset-root',type=Path)
    p.add_argument('--episode')
    a=p.parse_args()
    contract=json.loads(a.contract.read_text(encoding='utf-8'))
    if a.asset_root:
        import re
        asset=a.asset_root.resolve()
        if not asset.is_relative_to(ROOT/'3DModels') or not a.episode or not re.fullmatch('[a-z0-9-]{1,70}',a.episode):raise ValueError('Bounded asset episode required')
        if a.data_root.resolve()!=ROOT/'user-data':raise ValueError('Episode must use the project data root')
        with (asset/'metadata/autopilot/run.lock').open('r+b') as lock:
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            current=load(asset/'metadata/current-model.json')
            if a.source_job!=current['job_id']:raise ValueError('Teacher trials must bind the retained source')
            folder=asset/'metadata/demonstrations'/a.episode
            folder.mkdir(parents=True,exist_ok=False)
            save(folder/'contract.json',contract)
            save(folder/'episode.json',{'run_id':a.id,'source_job':a.source_job,'source_blend_sha256':current['blend_sha256'],'author':contract['author'],'status':'RUNNING_LOCAL_DEMONSTRATION','created_at':now(),'user_approval':False})
            try:result=native_asset_operation(a.data_root,a.source_job,contract,ident=a.id,operation='demonstration')
            finally:
                if (ROOT/'user-data/artifacts/studio3d-demonstration'/a.id/'status.json').exists():
                    record_episode(asset,a.episode,a.id)
                    from tools.studio3d_trial_report import update
                    update(asset)
            current['working_candidate']={'id':a.episode,'status':'BUILT_AWAITING_LOCAL_REVIEW','episode':'metadata/demonstrations/'+a.episode+'/episode.json','preview':'metadata/demonstrations/'+a.episode+'/after/'+contract['views'][0]['id']+'.png','not_current_retained_model':True,'user_approval':False}
            save(asset/'metadata/current-model.json',current)
            update(asset)
    else:
        result=native_asset_operation(a.data_root,a.source_job,contract,ident=a.id,operation='demonstration')
    print(json.dumps({k:result.get(k) for k in ('id','status','elapsed_seconds','error','source_job')},ensure_ascii=False))


if __name__=='__main__':main()
