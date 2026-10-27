import bpy,json
from pathlib import Path
from mathutils.kdtree import KDTree
root=Path('D:/Jarvis');folder=root/'user-data/artifacts/studio3d/417ecb2c747f4435b32a8bb7d478320e';out=root/'docs/evidence/studio3d-apple-2026-10-24/texture-implementation'
bpy.ops.wm.open_mainfile(filepath=str(folder/'model.blend'),load_ui=False,use_scripts=False)
receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'));names=[x['id'] for x in receipt['report']['objects']];source={}
for name in names:
    o=bpy.data.objects[name];m=o.data;mat=o.matrix_world.to_3x3().inverted().transposed();rows=[(o.matrix_world@m.vertices[l.vertex_index].co,(mat@m.corner_normals[l.index].vector).normalized()) for l in m.loops];tree=KDTree(len(rows))
    for i,(v,n) in enumerate(rows):tree.insert(v,i)
    tree.balance();source[name.split(' ·')[0]]=(tree,rows)
bpy.ops.import_scene.gltf(filepath=str(folder/'model.glb'));result=[]
for o in bpy.context.selected_objects:
    if o.type!='MESH':continue
    key=next(k for k in source if o.name.startswith(k));tree,rows=source[key];mat=o.matrix_world.to_3x3().inverted().transposed();dots=[];bad=[]
    for l in o.data.loops:
        v=o.matrix_world@o.data.vertices[l.vertex_index].co;n=(mat@o.data.corner_normals[l.index].vector).normalized();near=tree.find_range(v,1e-6);dot=max(n.dot(rows[i][1]) for _,i,d in near);dots.append(dot)
        if dot<.999:bad.append({'point':list(v),'normal':list(n),'best_dot':dot,'source_normals':[list(rows[i][1]) for _,i,d in near]})
    result.append({'name':o.name,'corner_count':len(dots),'min_normal_dot':min(dots),'bad_count':len(bad),'examples':bad[:30]})
(out/'normal-diff.json').write_text(json.dumps(result,indent=2))
