"""Check the face trial remains reversible and preserves the hair collection."""
import bpy,hashlib,json
from pathlib import Path
ROOT=Path('D:/Jarvis');src=ROOT/'3DModels/SilverHairCharacter/user-fbx-face-study-01/candidate.blend'
out=ROOT/'user-data/artifacts/studio3d-character/face-outline-study-01';trial=out/'candidate.blend'
def hashcoords(vs):return hashlib.sha256(';'.join(','.join(f'{v.co[i]:.7f}' for i in range(3)) for v in vs).encode()).hexdigest()
def read(path):
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];body=bpy.data.objects['Body'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 return {'face_basis':hashcoords(face.data.shape_keys.key_blocks['Basis'].data),'body_basis':hashcoords(body.data.shape_keys.key_blocks['Basis'].data),
  'hair':{o.name:hashcoords(o.data.vertices) for o in hair.objects if o.type=='MESH'},'bones':len(bpy.data.objects['Armature'].data.bones),
  'face_keys':{k.name:k.value for k in face.data.shape_keys.key_blocks},'face_materials':[m.name for m in face.data.materials]}
a=read(src);b=read(trial)
result={'face_basis_unchanged':a['face_basis']==b['face_basis'],'body_basis_unchanged':a['body_basis']==b['body_basis'],
 'hair_meshes_unchanged':a['hair']==b['hair'],'hair_count':len(b['hair']),'bones_unchanged':a['bones']==b['bones'],
 'face_materials_unchanged':a['face_materials']==b['face_materials'],'shape_key_value':b['face_keys'].get('EyeAndChinOutlineStudy'),
 'limits':['Readback only; no animation or engine export test']}
result['passed']=all(result[k] for k in ('face_basis_unchanged','body_basis_unchanged','hair_meshes_unchanged','bones_unchanged','face_materials_unchanged')) and result['shape_key_value']==1.
(out/'structure-validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
if not result['passed']:raise ValueError('Unexpected face study change')
print('FACE_READBACK_OK')
