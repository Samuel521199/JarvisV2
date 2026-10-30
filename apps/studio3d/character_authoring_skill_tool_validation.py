"""Behavior checks for new mesh creation, morphing and edit rejection in Blender."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
tool=Path('C:/Users/samuel/.codex/skills/blender-character-authoring/scripts/character_tools.py')
spec=importlib.util.spec_from_file_location('authoring_validation',tool);t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
out=ROOT/'user-data/artifacts/studio3d-character/authoring-tool-validation-01'
if out.exists():raise ValueError('Validation exists')
out.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with render_lane(out):
    base=out/'create/candidate.blend'
    plan={'source':None,'output':str(base),'collection':'CreateTest','operations':[
        {'type':'loft','name':'TestHead','sections':[{'center':[0,0,z],'rx':x,'ry':y} for z,x,y in
          [(1.,.03,.05),(1.08,.07,.08),(1.16,.085,.095),(1.24,.06,.07),(1.27,.01,.01)]]},
        {'type':'loft','name':'TestNeck','sections':[{'center':[0,0,z],'rx':.025,'ry':.03} for z in (.9,1.)]}]}
    t.apply_plan(plan)
    assert bpy.data.objects['TestHead'].type=='MESH'
    src_hash=sha(base);before=t.mesh_fingerprint(bpy.data.objects['TestNeck'])
    edit={'source':str(base),'source_sha256':src_hash,'output':str(out/'modify/candidate.blend'),
          'collection':'ModifyTest','protected_objects':['TestNeck'],'operations':[
            {'type':'morph','object':'TestHead','key':'NoseLocalTrial','center':[0,-.08,1.08],
             'radius':[.03,.04,.03],'delta':[0,-.006,0],'max_displacement':.008}]}
    result=t.apply_plan(edit);face=bpy.data.objects['TestHead'];keys=face.data.shape_keys.key_blocks
    shift=max((a.co-b.co).length for a,b in zip(keys['Basis'].data,keys['NoseLocalTrial'].data))
    assert .004<shift<=.00601
    assert t.mesh_fingerprint(bpy.data.objects['TestNeck'])==before
    assert sha(base)==src_hash
    refused=[]
    for name,mutation in [('stale-source',{'source_sha256':'0'*64}),('overwrite',{}),
                          ('excess-displacement',{'output':str(out/'excess/candidate.blend')})]:
        bad=copy.deepcopy(edit);bad.update(mutation)
        if name=='stale-source':bad['output']=str(out/'stale/candidate.blend')
        if name=='excess-displacement':bad['operations'][0]['delta']=[0,-.5,0]
        try:t.apply_plan(bad)
        except ValueError:refused.append(name)
        else:raise AssertionError('Did not reject '+name)
    assert len(refused)==3
    # Exercise the read-only inspection path against the saved edited scene.
    bpy.ops.wm.open_mainfile(filepath=edit['output'],load_ui=False,use_scripts=False)
    info=t.inspect_scene();assert any(o['name']=='TestHead' and len(o['keys'])==2 for o in info['objects'])
    (out/'validation.json').write_text(json.dumps({'creation_saved_and_reloaded':True,
        'morph_max_local_displacement':shift,'protected_neck_unchanged':True,'source_file_unchanged':True,
        'rejected':refused,'inspection_shape_keys_readback':True,
        'limits':['Tool behavior only; no finished character, likeness or animation acceptance']},indent=2),encoding='utf8')
    print('VALIDATION_PASSED',refused,shift,flush=True)
