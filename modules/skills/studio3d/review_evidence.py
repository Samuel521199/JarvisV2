"""Bind visual feedback to one exported model and immutable render inputs."""
import hashlib
from pathlib import Path


def file_evidence(path):
    path=Path(path).resolve()
    if not path.is_file():raise ValueError(f'Missing evidence file: {path}')
    data=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}


def candidate_manifest(model, renders, *, iteration, camera_settings=None):
    from modules.skills.studio3d.hard_surface_review import VIEWS
    if set(renders)!=set(VIEWS):raise ValueError('Exactly five named reference views are required')
    if not iteration:raise ValueError('Iteration identity is required')
    return {'schema':1,'iteration':iteration,'model':file_evidence(model),
            'renders':{view:file_evidence(renders[view]) for view in VIEWS},
            'cameras':camera_settings or {},'user_approval':False,'lod_authorized':False}


def verify_manifest(manifest, render_paths=None):
    from modules.skills.studio3d.hard_surface_review import VIEWS
    if manifest.get('schema')!=1 or set(manifest.get('renders',{}))!=set(VIEWS):
        raise ValueError('Invalid candidate evidence manifest')
    files=[manifest['model'],*manifest['renders'].values()]
    for row in files:
        actual=file_evidence(row['path'])
        if actual['sha256']!=row['sha256'] or actual['bytes']!=row['bytes']:
            raise ValueError(f'Evidence changed after capture: {row["path"]}')
    if render_paths:
        for view,path in render_paths.items():
            if view not in manifest['renders']:raise ValueError('Unknown evidence view')
            if file_evidence(path)['sha256']!=manifest['renders'][view]['sha256']:
                raise ValueError(f'Review image is from a different candidate: {view}')
    return {'iteration':manifest['iteration'],'model_sha256':manifest['model']['sha256'],
            'all_five_render_hashes_verified':True,'user_approval':False,'lod_authorized':False}
