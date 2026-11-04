"""Produce one LOD from the explicitly approved current first-party high source."""
import argparse,json,hashlib,time,shutil,uuid,msvcrt,os,re
from pathlib import Path
from host.studio3d_high_finish import asset_source
from host.studio3d_learning import _process,save,validate_export
from modules.skills.studio3d.game_lod import validate
ROOT=Path(__file__).resolve().parents[1]
def run(asset,cfg,ident,package='PaK38_LOD_v1'):
    asset=Path(asset).resolve();cfg=validate(cfg)
    from host.studio3d import enabled,readiness
    enabled(ROOT/'user-data')
    if not readiness(ROOT/'user-data')['ready']:raise ValueError('Prepared Blender required')
    if not asset.is_relative_to(ROOT/'3DModels'):raise ValueError('Asset-local output required')
    if not re.fullmatch(r'PaK38_LOD_v[1-9][0-9]?',package):raise ValueError('Explicit bounded package name required')
    output=asset/'game'/package
    with (asset/'metadata/autopilot/run.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        current=json.loads((asset/'metadata/current-model.json').read_text());w=current['working_candidate']
        if w.get('user_approval') is not True or w.get('lod_authorized') is not True:raise ValueError('Current high must be explicitly accepted for LOD')
        auth=json.loads((output/'evidence/authorization.json').read_text())
        if auth['source_candidate']!=w['id'] or auth['sources']['blend']['sha256']!=w['blend_sha256']:raise ValueError('Approval binding changed')
        if cfg['triangle_budget']>auth.get('max_triangles',[100000]*4)[cfg['level']]:raise ValueError('User level triangle cap exceeded')
        names,files=asset_source(ROOT/'user-data',w['viewer_job_id'],'production');raw=files['model.blend']['raw']
        if hashlib.sha256(raw).hexdigest()!=w['blend_sha256']:raise ValueError('Mapped high receipt mismatch')
        folder=ROOT/'user-data/artifacts/studio3d-game-lod'/ident;folder.mkdir(parents=True,exist_ok=False)
        (folder/'source.blend').write_bytes(raw);request={'source_sha256':w['blend_sha256'],'visible_names':names,'contract':cfg}
        if cfg.get('geometry_mode') in ('silhouette','structured'):
            semantic_names,semantic=asset_source(ROOT/'user-data',w['editable_source_job'],w['editable_source_operation'])
            if semantic['model.blend']['sha256']!=w['editable_blend_sha256']:raise ValueError('Editable silhouette reference changed')
            (folder/'semantic.blend').write_bytes(semantic['model.blend']['raw']);request.update(semantic_sha256=w['editable_blend_sha256'],semantic_names=semantic_names)
        save(folder/'request.json',request)
        prepared=json.loads((ROOT/'user-data/optional/studio3d/prepared.json').read_text());exe=Path(prepared['executable'])
        if hashlib.sha256(exe.read_bytes()).hexdigest()!=prepared['executable_sha256']:raise ValueError('Blender executable changed')
        status={'id':ident,'operation':'game_lod','status':'RUNNING','started_at':time.time(),'owner_pid':os.getpid(),'request':request,'model_calls':0,'api_usd':0,'local_compute_usd':None,'source_code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['modules/skills/studio3d/game_lod.py','adapters/studio3d/game_lod_worker.py','adapters/studio3d/asset_pipeline.py','adapters/studio3d/projection.py','tools/studio3d_game_lod.py']}}
        save(folder/'status.json',status);index=output/'evidence'/('lod'+str(cfg['level'])+'-run.json');save(index,{'id':ident,'folder':str(folder),'contract':cfg})
        try:
            _process(ROOT/'user-data',folder,exe,operation='game_lod')
            report=json.loads((folder/'report.json').read_text());official=validate_export(folder/'model.glb');save(folder/'format-validation.json',official)
            if official['issues']['numErrors']:raise ValueError('Official glTF validation failed')
            raw_glb=(folder/'model.glb').read_bytes();n=int.from_bytes(raw_glb[12:16],'little');doc=json.loads(raw_glb[20:20+n])
            if any(p.get('mode',4)!=4 or doc['accessors'][p['indices']]['count']%3 for m in doc['meshes'] for p in m['primitives']):raise ValueError('Export must contain only triangle primitives')
            status.update(status='BUILT_AWAITING_VISUAL_COMPARISON',report=report,official_format_issues=official['issues'])
            status['files']={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in folder.iterdir() if p.suffix in ('.blend','.glb','.png') and p.name!='source.blend'}
            dest=output/('LOD'+str(cfg['level']));dest.mkdir(exist_ok=False)
            for p in folder.iterdir():
                if p.name not in {'source.blend','semantic.blend'} and p.suffix in ('.blend','.glb','.png','.json'):shutil.copy2(p,dest/p.name)
        except BaseException as e:status.update(status='FAILED',error=str(e));raise
        finally:
            status['finished_at']=time.time();status['elapsed_seconds']=status['finished_at']-status['started_at'];save(folder/'status.json',status);save(index,{**json.loads(index.read_text()),'status':status['status'],'elapsed_seconds':status['elapsed_seconds']})
        return {'id':ident,'status':status['status'],'triangles':report['triangles'],'folder':str(dest)}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--asset-root',type=Path,required=True);p.add_argument('--package',default='PaK38_LOD_v1');p.add_argument('--mode',choices=['reduce','silhouette','structured'],default='reduce');p.add_argument('--level',type=int,required=True);p.add_argument('--budget',type=int,required=True);p.add_argument('--texture-size',type=int,required=True);p.add_argument('--ray-distance',type=float,default=.03);a=p.parse_args();print(json.dumps(run(a.asset_root,{'level':a.level,'triangle_budget':a.budget,'texture_size':a.texture_size,'ray_distance':a.ray_distance,'geometry_mode':a.mode},uuid.uuid4().hex,a.package),ensure_ascii=False))
