"""Check the saved body trial preserves the prior face, hair and armature."""
import bpy,hashlib,json
from pathlib import Path
root=Path('D:/Jarvis');src=root/'3DModels/SilverHairCharacter/user-fbx-detachable-hair-01/replaceable-hair.blend'
trial=root/'user-data/artifacts/studio3d-character/body-silhouette-refine-01/candidate.blend'
def digest_coords(vertices):
 return hashlib.sha256(';'.join(','.join(f'{v.co[i]:.7f}' for i in range(3)) for v in vertices).encode()).hexdigest()
def read(path):
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
 col=bpy.data.collections['Hair_SilverHair_Replaceable_01'];face=bpy.data.objects['Face'];body=bpy.data.objects['Body'];arm=bpy.data.objects['Armature']
 return {'face_sha':digest_coords(face.data.vertices),'body_basis_sha':digest_coords(body.data.shape_keys.key_blocks['Basis'].data),
  'hair':{o.name:digest_coords(o.data.vertices) for o in col.objects if o.type=='MESH'},
  'bones':len(arm.data.bones),'keys':{k.name:k.value for k in body.data.shape_keys.key_blocks}}
before=read(src);after=read(trial)
passed=(before['face_sha']==after['face_sha'] and before['body_basis_sha']==after['body_basis_sha'] and
 before['hair']==after['hair'] and before['bones']==after['bones'] and after['keys'].get('ReferenceWidthCorrection')==1.)
result={'passed':passed,'face_unchanged':before['face_sha']==after['face_sha'],'body_basis_unchanged':before['body_basis_sha']==after['body_basis_sha'],
 'hair_meshes_unchanged':before['hair']==after['hair'],'hair_count':len(after['hair']), 'bones_before':before['bones'],'bones_after':after['bones'],
 'trial_shape_key':after['keys'].get('ReferenceWidthCorrection'),
 'limitations':['Only structure/readback verified','No animation deformation or engine export test']}
(trial.parent/'structure-validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
if not passed:raise ValueError('Candidate structure mismatch')
print('STRUCTURE_READBACK_OK')
