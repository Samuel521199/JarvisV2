"""Run fixed local refinement against the one documented user-FBX derivative."""
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from control.recovery.gate import StopGate
from host.studio3d_learning import _process,validate_export
from tools.studio3d_character_iterate import ASSET,DATA,ROOT,load,save,sha
from modules.skills.studio3d.character_priorities import load as priorities_load


def main():
    StopGate(DATA).require_running()
    source=ASSET/'user-fbx-hair-face-candidate-v4'; manifest=load(source/'manifest.json')
    name='character-rigged-experimental.blend';baseline=source/name
    if sha(baseline)!=manifest['files'][name]:raise ValueError('Frozen baseline mismatch')
    priorities,priority_hash=priorities_load(ASSET/'metadata/visual-priorities.json','character-silverhair-01')
    output=ASSET/'user-fbx-refined-priorities-01'
    if output.exists():raise ValueError('Output already exists; inspect rather than overwrite')
    state_path=ASSET/'metadata/priority-refinement.json'
    if state_path.exists():raise ValueError('Existing refinement needs inspection')
    ident=uuid.uuid4().hex;folder=DATA/'artifacts/studio3d-character'/ident;folder.mkdir(parents=True)
    code=['apps/studio3d/character_worker.py','apps/studio3d/character_refinement_worker.py',
          'modules/skills/studio3d/character_body_refine.py','modules/skills/studio3d/character_face_refine.py',
          'control/studio3d_lane.py']
    hashes={p:sha(ROOT/p) for p in code}
    shutil.copyfile(baseline,folder/'source.blend')
    save(folder/'request.json',{'schema':'jarvis.character.refinement.v1','asset_id':'character-silverhair-01','source_sha256':sha(baseline)})
    status={'schema':'jarvis.character.refinement.status.v1','status':'BUILDING','run_id':ident,
            'source_sha256':sha(baseline),'priorities_sha256':priority_hash,'source_code_sha256':hashes,
            'source':'User-provided FBX derivative, first-party authored changes, not independent reconstruction',
            'user_approval':False,'automatic_promotion':False}
    save(state_path,status)
    try:
        prepared=load(DATA/'optional/studio3d/prepared.json');exe=Path(prepared['executable'])
        if sha(exe)!=prepared['executable_sha256']:raise ValueError('Blender executable changed')
        _process(DATA,folder,exe,operation='character')
        if any(sha(ROOT/p)!=v for p,v in hashes.items()):raise ValueError('Refinement source changed during build')
        report=load(folder/'report.json')
        if not report['roundtrip']['passed']:raise ValueError('GLB reimport failed')
        valid=validate_export(folder/'character-refined-static.glb');save(folder/'format-validation.json',valid)
        output.mkdir()
        for name in ('character-refined.blend','character-refined-static.glb','report.json','format-validation.json','resource-lane.json',
                     'view-front.png','view-rear.png','view-left.png','view-right.png','view-head.png'):
            shutil.copyfile(folder/name,output/name)
        files={p.name:sha(p) for p in output.iterdir() if p.is_file()}
        save(output/'manifest.json',{'asset_id':'character-silverhair-01','source_sha256':sha(baseline),
             'priorities_sha256':priority_hash,'source_code_sha256':hashes,'files':files,'user_approval':False})
        status.update(status='BUILT_AWAITING_FOUR_VIEW_REVIEW',output=str(output),manifest_sha256=sha(output/'manifest.json'))
        save(state_path,status);print(json.dumps(status,ensure_ascii=False),flush=True)
    except BaseException as exc:
        status.update(status='FAILED_OR_UNKNOWN',error=str(exc));save(state_path,status);raise


if __name__=='__main__':main()
