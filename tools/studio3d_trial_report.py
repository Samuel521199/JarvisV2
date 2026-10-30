"""Refresh an asset's production ledger and current package manifest in place."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
from modules.skills.studio3d.production_receipt import stages,summary,native_stage


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,obj):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');temp.replace(path)


def update(asset):
    asset=Path(asset).resolve();meta=asset/'metadata';state=read(meta/'autopilot/state.json');handoff=read(meta/'jarvis-handoff.json')
    rows=stages(state,handoff)
    registry=meta/'native-tool-runs.json'
    if registry.exists():
        import re
        project=Path(__file__).resolve().parents[1]
        registered=set()
        for entry in read(registry)['runs']:
            ident=entry['id'];kind=entry['kind']
            if kind not in ('inspection','high-finish','demonstration','roundtrip','surface-material','tyre-surface','attachment-seat','annular-detail','panel-corner','preview') or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Invalid native cost registration')
            if ident in registered:raise ValueError('Duplicate native cost registration')
            registered.add(ident)
            if any(r.get('job_id')==ident for r in rows):continue
            if kind=='preview':
                from host.studio3d import state as preview_state
                job=preview_state(project/'user-data',ident)
                receipt={'id':ident,'status':job['status'],'elapsed_seconds':(job.get('receipt') or {}).get('resources',{}).get('elapsed_seconds')}
            else:receipt=read(project/'user-data/artifacts'/('studio3d-'+kind)/ident/'status.json')
            rows.append(native_stage('native-tool/'+kind+'/'+ident,receipt))
    totals=summary(rows);stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    save(meta/'autopilot/cost-summary.json',{'updated_at':stamp,'status':state['status'],'summary':totals,'stages':rows,'author_interventions':state['author_interventions']})
    ledger=read(meta/'costs.json');ledger['stages']=[r for r in ledger['stages'] if r.get('record_owner')!='studio3d-autopilot.v1']+rows
    ledger['updated_utc']=stamp;ledger['summary']['production_trial']=totals;ledger['summary']['total_tokens']=None;ledger['summary']['total_usd']=None
    save(meta/'costs.json',ledger)
    model_path=meta/'current-model.json';current=read(model_path) if model_path.exists() else None
    files=[]
    for path in [*asset.glob('reference-*.png'),*asset.glob('PaK38-high.*'),*asset.glob('renders/*.png')]:
        files.append({'path':path.relative_to(asset).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    save(meta/'package-manifest.json',{'schema':'jarvis.studio3d.asset-package.v1','asset_id':'PaK38','updated_at':stamp,'asset_files':files,'current_model':current,
        'high_approved':False,'lod_authorized':False,'textures_embedded':False,'status':'HIGH_CANDIDATE_IN_PROGRESS','resume':'metadata/autopilot/state.json'})
    trial=read(meta/'production-trial.json');trial.update(status=state['status'],updated_at=stamp,current_model=current,production_cost=totals,
        user_high_approved=False,cross_asset_quality_gain_verified=False,automatic_experience_promotion=False)
    save(meta/'production-trial.json',trial)
    text='''5 cm PaK 38 Anti-Tank Gun — 高模制作进行中

5张参考图：reference-front/rear/left/right/top.png，2048×2048。
原生1254×1254经本地增强；独立生成视图不是同一模型的标定蓝图。
冲突策略：低矮双层弧盾、仅武器左侧观察孔；侧视图决定制退器侧孔；排除右图无依据的后向管件。

PaK38-high.blend / PaK38-high.glb：当前保留的高模候选。
renders/：同一模型的实际Blender渲染。metadata/current-model.json绑定文件SHA256和查看地址。
尚未达到用户验收；未制作低模或LOD。程序涂装保存在BLEND，当前GLB仍为基础PBR。
可动归属已声明，但此候选尚未通过绑定、合批或游戏引擎性能验证。

metadata/autopilot/：可恢复迭代、实际模型调用、候选、五视图审查和退步记录。
metadata/costs.json：完整尝试账本；API估算不等于实际账单；作者/本地计算未知费用保持null。
metadata/production-trial.json：本次能力试验边界；工具由Codex补写，不能当作Jarvis自主学会编程。
ATTRIBUTION.txt / metadata/sources：历史实拍来源。metadata/native：原始生成参考。
中间证据为复查与恢复保留，未散放到根目录；不将失败候选作为通用经验。
'''
    if current:
        text+='\n当前保留：'+current['iteration']+'，'+str(current['triangles'])+' triangles\n'+current['viewer']+'\n'
        candidate=current.get('working_candidate',{})
        if candidate.get('viewer'):
            text+='\n最新工作候选（未验收）：'+candidate['id']+'\n'+candidate['viewer']+'\n'
            if candidate.get('pbr_textures_embedded'):text+='该工作候选已嵌入高模表面 PBR 贴图；不代表旧保留 r25 文件同步更新。\n'
    (asset/'README.txt').write_text(text,encoding='utf-8')
    return {'status':state['status'],'current':current and current['iteration'],'costs':totals}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--asset-root',type=Path,required=True);args=p.parse_args();print(json.dumps(update(args.asset_root),ensure_ascii=False))
