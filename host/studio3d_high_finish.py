"""Verified first-party high surface finishing, callable through Jarvis CLI.

Only a delivered Studio3D job's receipt-verified BLEND is opened. No arbitrary
BLEND upload, Python supplied by a model, low-poly reduction or LOD operation.
"""
import hashlib,json,time,uuid,os,re
from pathlib import Path
from control.paths import child,data_root
from host.studio3d_learning import _process,save,validate_export
from modules.skills.studio3d.high_finish import validate,VERSION

ROOT=Path(__file__).resolve().parents[1]


def asset_source(root, ident, operation='production'):
    """Resolve only receipt-bound first-party production or demonstration files."""
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Invalid source identity')
    from host.studio3d import file,state
    if operation=='production':
        prior=state(root,ident)
        if prior['status']!='DELIVERED':raise ValueError('Delivered first-party source required')
        receipt=prior['receipt'];names=[o['id'] for o in receipt['report']['objects']]
        paths=None
    elif operation in ('demonstration','surface_material','tyre_surface','attachment_seat','annular_detail','panel_corner','high_finish'):
        folder=child(root,'artifacts/studio3d-'+operation.replace('_','-')+'/'+ident)
        receipt=json.loads((folder/'status.json').read_text(encoding='utf-8'))
        if (receipt.get('id')!=ident or receipt.get('operation')!=operation
            or receipt.get('status')!='BUILT_AWAITING_VISUAL_COMPARISON'):raise ValueError('Completed native source required')
        if operation=='surface_material':
            if (receipt.get('report',{}).get('geometry_and_transform_unchanged') is not True
                or receipt.get('report',{}).get('source_unchanged') is not True):raise ValueError('Unverified material edit source')
        elif operation in ('tyre_surface','attachment_seat','annular_detail','panel_corner'):
            if (receipt.get('report',{}).get('unchanged_non_targets') is not True
                or receipt.get('report',{}).get('source_unchanged') is not True
                or not receipt.get('report',{}).get('actions')):raise ValueError('Unverified local tyre source')
            if operation in ('attachment_seat','annular_detail') and receipt['report'].get('contacts_checked') is not True:raise ValueError('Attachment contacts not verified')
            if operation=='panel_corner' and receipt['report'].get('anchors_checked') is not True:raise ValueError('Panel anchors not verified')
        elif receipt.get('official_format_issues',{}).get('numErrors')!=0:raise ValueError('Validated export required')
        names=([g['group'] for g in receipt['report']['groups']] if operation=='high_finish' else list(receipt['report']['after_object_digests']));paths=folder
    else:raise ValueError('Unsupported source kind')
    if not names or len(names)>512 or len(set(names))!=len(names):raise ValueError('Invalid source inventory')
    files={}
    for name in (('model.blend',) if operation in ('surface_material','tyre_surface','attachment_seat','annular_detail','panel_corner') else ('model.blend','model.glb')):
        raw=(paths/name).read_bytes() if paths else file(root,ident,name)[0]
        expected=receipt['files'][name]['sha256']
        if not 10<len(raw)<128*1024**2 or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Source receipt mismatch: '+name)
        files[name]={'raw':raw,'sha256':expected}
    return names,files


def run(root,source_job,contract, *, ident=None):
    return native_asset_operation(root,source_job,contract,ident=ident,operation='high_finish')


def native_asset_operation(root,source_job,contract, *, ident=None,operation,source_operation='production'):
    """Shared receipt, idempotence, execution and usage for fixed asset tools."""
    if operation=='high_finish':check=validate;version=VERSION;kind='high-finish'
    elif operation=='inspection':
        from modules.skills.studio3d.render_inspection import validate as check, VERSION as version
        kind='inspection'
    elif operation=='demonstration':
        from modules.skills.studio3d.demonstration import validate as check, VERSION as version
        kind='demonstration'
    elif operation=='roundtrip':
        from modules.skills.studio3d.render_inspection import validate as check, VERSION as version
        kind='roundtrip'
    elif operation=='surface_material':
        from modules.skills.studio3d.surface_material import validate as check, VERSION as version
        kind='surface-material'
    elif operation=='tyre_surface':
        from modules.skills.studio3d.tyre_surface import validate as check, VERSION as version
        kind='tyre-surface'
    elif operation=='attachment_seat':
        from modules.skills.studio3d.attachment_seat import validate as check, VERSION as version
        kind='attachment-seat'
    elif operation=='annular_detail':
        from modules.skills.studio3d.annular_detail import validate as check, VERSION as version
        kind='annular-detail'
    elif operation=='panel_corner':
        from modules.skills.studio3d.panel_corner import validate as check, VERSION as version
        kind='panel-corner'
    else:raise ValueError('Unregistered asset operation')
    from host.studio3d import enabled,readiness,file,state
    root=data_root(root);enabled(root)
    if not readiness(root)['ready']:raise ValueError('Prepared Blender required')
    names,source_files=asset_source(root,source_job,source_operation)
    if operation=='roundtrip' and 'model.glb' not in source_files:raise ValueError('Unbaked coating has no GLB; export high surface maps first')
    config=check(contract,names)
    raw=source_files['model.blend']['raw'];expected=source_files['model.blend']['sha256']
    prepared=json.loads(child(root,'optional/studio3d/prepared.json').read_text(encoding='utf-8'));executable=Path(prepared['executable'])
    if hashlib.sha256(executable.read_bytes()).hexdigest()!=prepared['executable_sha256']:raise ValueError('Blender executable changed')
    ident=ident or uuid.uuid4().hex
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Invalid high finish run ID')
    inputs={'source_job':source_job,'contract':config}
    if source_operation!='production':inputs['source_operation']=source_operation
    signature=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
    folder=child(root,'artifacts/studio3d-'+kind+'/'+ident)
    try:folder.mkdir(parents=True)
    except FileExistsError:
        if not (folder/'status.json').exists():return {'id':ident,'status':'UNKNOWN','reason':'Run folder exists before status; inspect without replay'}
        previous=json.loads((folder/'status.json').read_text(encoding='utf-8'))
        if previous.get('signature')!=signature:raise ValueError('Existing run input differs')
        if previous['status']=='RUNNING' and previous.get('owner_pid')!=os.getpid():previous={**previous,'status':'UNKNOWN','reason':'Existing worker ownership needs inspection; not replayed'}
        return previous
    (folder/'source.blend').write_bytes(raw)
    request={'source_job':source_job,'source_operation':source_operation,'source_sha256':expected,'visible_names':names,'contract':config}
    if operation=='roundtrip':
        (folder/'source.glb').write_bytes(source_files['model.glb']['raw']);request['source_glb_sha256']=source_files['model.glb']['sha256']
    save(folder/'request.json',request)
    if operation=='high_finish' and 'reuse' in config:
        base_id=config['reuse']['export_id'];_,base_files=asset_source(root,base_id,'high_finish')
        base_folder=child(root,'artifacts/studio3d-high-finish/'+base_id);base_status=json.loads((base_folder/'status.json').read_text(encoding='utf-8'))
        base_config=base_status['request']['contract']
        if any(base_config[k]!=config[k] for k in ('groups','texture_size')):raise ValueError('Reuse changes grouping, origin, hierarchy or texture size')
        baseline=(base_folder/'source.blend').read_bytes();baseline_sha=hashlib.sha256(baseline).hexdigest()
        if baseline_sha!=base_status['request']['source_sha256']:raise ValueError('Reuse editable source mismatch')
        (folder/'reuse-source.blend').write_bytes(baseline);(folder/'reuse-high.blend').write_bytes(base_files['model.blend']['raw'])
        request['reuse']={'source_sha256':baseline_sha,'high_sha256':base_files['model.blend']['sha256'],'export_id':base_id,'groups':{g['group']:g for g in base_status['report']['groups']}}
        for group in config['reuse']['groups']:
            for channel in ('basecolor.png','normal.png','orm.png','ao.png'):
                name=group+'/'+channel;raw_map=(base_folder/name).read_bytes()
                if hashlib.sha256(raw_map).hexdigest()!=base_status['files'][name]['sha256']:raise ValueError('Reused map receipt mismatch')
                target=folder/name;target.parent.mkdir(exist_ok=True);target.write_bytes(raw_map)
        save(folder/'request.json',request)
    if operation=='surface_material':
        from modules.skills.studio3d.surface_material import TEXTURES
        for role,(path,sha) in TEXTURES.items():
            texture=(ROOT/path).read_bytes()
            if hashlib.sha256(texture).hexdigest()!=sha:raise ValueError('Pinned coating texture changed')
            (folder/('texture-'+role+'.png')).write_bytes(texture)
    sources=['host/studio3d_high_finish.py','host/studio3d_learning.py','modules/skills/studio3d/'+('render_inspection' if operation in ('inspection','roundtrip') else operation)+'.py','apps/studio3d/'+operation+'_worker.py','adapters/studio3d/'+operation+'_worker.py']
    if operation=='roundtrip':sources.append('adapters/studio3d/inspection_worker.py')
    if operation=='high_finish':sources.extend(['adapters/studio3d/asset_pipeline.py','adapters/studio3d/high_finish_reuse.py','tools/studio3d_blender_material_projection.py'])
    if operation=='demonstration':sources.append('modules/skills/studio3d/radial_profile.py')
    if operation=='surface_material':sources.extend(['adapters/studio3d/demonstration_worker.py','tools/studio3d_blender_material_projection.py'])
    if operation=='tyre_surface':sources.extend(['adapters/studio3d/demonstration_worker.py','adapters/studio3d/inspection_worker.py','modules/skills/studio3d/render_inspection.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/fastener_layout.py','modules/skills/studio3d/component_seat.py','modules/skills/studio3d/exterior_closure.py','modules/skills/studio3d/pedestal_profile.py','modules/skills/studio3d/saddle_fascia.py','modules/skills/studio3d/assembly_geometry.py','adapters/studio3d/exterior_closure_worker.py','adapters/studio3d/pedestal_profile_worker.py','adapters/studio3d/saddle_fascia_worker.py','adapters/studio3d/demonstration_worker.py','adapters/studio3d/inspection_worker.py','modules/skills/studio3d/render_inspection.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/rear_face_relief.py','adapters/studio3d/rear_face_relief_worker.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/exterior_border.py','adapters/studio3d/exterior_border_worker.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/evaluated_shading.py','adapters/studio3d/evaluated_shading_worker.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/microface_cleanup.py','adapters/studio3d/microface_cleanup_worker.py','adapters/studio3d/high_finish_reuse.py','modules/skills/studio3d/high_finish.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/facade_pocket.py','adapters/studio3d/facade_pocket_worker.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/spade_frame.py','adapters/studio3d/spade_frame_worker.py','adapters/studio3d/panel_corner_worker.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/curve_grip.py','adapters/studio3d/curve_grip_worker.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/curve_foot.py','adapters/studio3d/curve_foot_worker.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/rear_contour.py','adapters/studio3d/rear_contour_worker.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/trail_pad.py','adapters/studio3d/trail_pad_worker.py'])
    if operation=='attachment_seat':sources.extend(['modules/skills/studio3d/trail_tab.py','adapters/studio3d/trail_tab_worker.py'])
    if operation in ('annular_detail','panel_corner'):sources.extend(['modules/skills/studio3d/attachment_seat.py','adapters/studio3d/attachment_seat_worker.py','adapters/studio3d/demonstration_worker.py','adapters/studio3d/inspection_worker.py','modules/skills/studio3d/render_inspection.py'])
    if operation=='panel_corner':sources.extend(['modules/skills/studio3d/panel_aperture.py','modules/skills/studio3d/panel_lower_band.py','adapters/studio3d/panel_lower_band_worker.py'])
    if operation=='annular_detail':sources.extend(['modules/skills/studio3d/collar_profile.py','adapters/studio3d/collar_profile_worker.py','adapters/studio3d/exterior_closure_worker.py','modules/skills/studio3d/exterior_closure.py','modules/skills/studio3d/assembly_geometry.py'])
    if operation=='annular_detail':sources.extend(['modules/skills/studio3d/trail_band.py','adapters/studio3d/trail_band_worker.py','adapters/studio3d/spade_frame_worker.py','modules/skills/studio3d/spade_frame.py','adapters/studio3d/panel_corner_worker.py'])
    status={'id':ident,'status':'RUNNING','version':version,'operation':operation,'started_at':time.time(),'source_job':source_job,'owner_pid':os.getpid(),'signature':signature,
            'source_code_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources},'request':request}
    save(folder/'status.json',status)
    try:
        _process(root,folder,executable,operation=operation)
        report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
        if operation in ('high_finish','demonstration'):
            official=validate_export(folder/'model.glb');save(folder/'format-validation.json',official)
            status['official_format_issues']=official['issues']
        elif operation=='inspection':
            from PIL import Image
            for view in report['views']:
                with Image.open(folder/view['file']) as source_image:
                    if source_image.format!='PNG' or list(source_image.size)!=config['resolution']:raise ValueError('Invalid native inspection image')
                    for name,region in view['regions'].items():
                        target='crop-'+view['view']+'-'+name+'.png'
                        crop=source_image.crop(region['rect']);crop.save(folder/target)
                        with Image.open(folder/target) as loaded:
                            if loaded.tobytes()!=crop.tobytes():raise ValueError('Crop evidence pixels changed')
                        region.update(file=target,crop_sha256=hashlib.sha256((folder/target).read_bytes()).hexdigest(),resampled=False)
            save(folder/'report.json',report)
        status.update(status='BUILT_AWAITING_VISUAL_COMPARISON',report=report,user_approval=False,lod_authorized=False)
        status['files']={p.relative_to(folder).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in folder.rglob('*') if p.is_file() and p.suffix in ('.glb','.blend','.png')}
    except BaseException as error:
        status.update(status='FAILED',error=str(error));raise
    finally:
        status['finished_at']=time.time();status['elapsed_seconds']=status['finished_at']-status['started_at'];status['model_calls']=0;status['api_usd']=0;status['local_compute_usd']=None
        save(folder/'status.json',status)
    return status
