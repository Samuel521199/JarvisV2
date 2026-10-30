"""Read back source and candidate; verify static data without editing either."""
import hashlib, json, struct
from pathlib import Path
import bpy

root=Path(__file__).resolve().parents[2]/'user-data/artifacts/studio3d-character'
source=root/'reference-eye-width-study-02/candidate.blend'
folder=root/'silver-hair-rebuild-study-03'
candidate=folder/'candidate.blend'

def scene_info(path):
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    face=bpy.data.objects['Face']
    h=hashlib.sha256()
    for v in face.data.vertices:
        h.update(struct.pack('<3d',*v.co))
    for key in face.data.shape_keys.key_blocks:
        h.update(key.name.encode('utf8'))
        h.update(struct.pack('<d',key.value))
        for v in key.data:h.update(struct.pack('<3d',*v.co))
    arm=bpy.data.objects['Armature']
    bones=sorted(b.name for b in arm.data.bones)
    col=bpy.data.collections.get('Hair_Silver_Rebuild_Replaceable_Trial')
    return {'face_and_shape_key_sha256':h.hexdigest(),'bones':bones,
            'hair_objects':sorted(o.name for o in col.objects) if col else [],
            'face_in_new_hair':face.name in col.objects if col else False,
            'old_hair_present':bool(bpy.data.collections.get('Hair_SilverHair_Replaceable_01'))}

before=scene_info(source);after=scene_info(candidate)
result={'face_data_identical':before['face_and_shape_key_sha256']==after['face_and_shape_key_sha256'],
        'bone_names_identical':before['bones']==after['bones'],
        'new_hair_object_count':len(after['hair_objects']),
        'face_in_new_hair_collection':after['face_in_new_hair'],
        'old_hair_present':after['old_hair_present'],
        'limitations':['Data comparison only, not animation, attachment, collision or export validation']}
(folder/'readback.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
