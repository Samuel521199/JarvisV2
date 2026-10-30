"""Read-only inspection of the in-project posed character candidate."""
import bpy, json, sys
from pathlib import Path
source=Path(sys.argv[sys.argv.index('--')+1])
bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
obj=bpy.data.objects['Body']
deps=bpy.context.evaluated_depsgraph_get()
evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
for z in [.10,.20,.30,.40,.50,.60,.70,.80,.90,1.00,1.10,1.20,1.28]:
    pts=[obj.matrix_world@v.co for v in mesh.vertices if abs((obj.matrix_world@v.co).z-z)<.006]
    # Central torso, excluding arms where possible.
    if z>.85: pts=[v for v in pts if abs(v.x)<.16]
    if pts: print('SLICE',z,len(pts),round(min(v.x for v in pts),4),round(max(v.x for v in pts),4),round(min(v.y for v in pts),4),round(max(v.y for v in pts),4))
print('MATRIX',json.dumps([list(r) for r in obj.matrix_world]));print('MODIFIERS', [(m.name,m.type) for m in obj.modifiers]);print('VERTICES',len(mesh.vertices))
evaluated.to_mesh_clear()
