import bpy,hashlib,json,struct
from pathlib import Path
root=Path('D:/Jarvis/user-data/artifacts/studio3d-character')
src=root/'face-studio-adapter-test-01/draft.blend';out=root/'reference-eye-width-study-02/candidate.blend'
def snap(path):
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False);col=bpy.data.collections['Hair_SilverHair_Replaceable_01'];f=bpy.data.objects['Face'];d={}
 for o in col.objects:
  h=hashlib.sha256()
  for v in o.data.vertices:h.update(struct.pack('<fff',*v.co))
  for p in o.data.polygons:
   for i in p.vertices:h.update(struct.pack('<I',i))
  d[o.name]=h.hexdigest()
 return d,sorted(b.name for b in bpy.data.objects['Armature'].data.bones),{k.name:k.value for k in f.data.shape_keys.key_blocks},[m.name for m in f.data.materials]
a,ab,ak,am=snap(src);b,bb,bk,bm=snap(out)
checks={'hair_mesh_data_unchanged':a==b,'hair_object_count':len(b),'bone_names_unchanged':ab==bb,'eye_key':bk.get('Refine_Eyes'),'brow_key':bk.get('Refine_Brows'),'mouth_key':bk.get('Refine_NoseMouth'),'width_key':bk.get('ReferenceEyeWidthFine'),'iris_material':bm[1], 'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'limits':['Data comparison only','No animation, export or visual approval']}
if not checks['hair_mesh_data_unchanged'] or not checks['bone_names_unchanged'] or len(b)!=30 or any(checks[k]!=1. for k in ('eye_key','brow_key','mouth_key','width_key')):raise RuntimeError('Readback failed')
p=root/'reference-eye-width-study-02/readback.json'
if p.exists():raise ValueError('Readback exists')
p.write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(checks,ensure_ascii=False))
