from pathlib import Path as _BootstrapPath
import sys as _bootstrap_sys
_bootstrap_sys.path.insert(0,str(_BootstrapPath(__file__).resolve().parents[2]))
from adapters.studio3d.learning_worker import install_runtime
install_runtime(__file__)
from sdk.runtime_paths import project_path, reference_path, optional_character_tool
from sdk.blender_api import require_blender
import json; bpy = require_blender().bpy
from collections import Counter
Vector = require_blender().mathutils.Vector
from pathlib import Path
src=str(project_path('user-data/artifacts/studio3d-character/reference-iris-study-03/candidate.blend'))
bpy.ops.wm.open_mainfile(filepath=src,load_ui=False,use_scripts=False)
o=bpy.data.objects['Face'];dg=bpy.context.evaluated_depsgraph_get();ev=o.evaluated_get(dg);me=ev.to_mesh();N=len(me.vertices);adj=[[] for _ in range(N)]
for e in me.edges:a,b=e.vertices;adj[a].append(b);adj[b].append(a)
mats=[set() for _ in range(N)]
for f in me.polygons:
 for i in f.vertices:mats[i].add(f.material_index)
seen=set();components=[];points=[ev.matrix_world@v.co for v in me.vertices]
for i in range(N):
 if i in seen:continue
 stack=[i];seen.add(i);ids=[]
 while stack:
  v=stack.pop();ids.append(v)
  for w in adj[v]:
   if w not in seen:seen.add(w);stack.append(w)
 if len(ids)<5:continue
 ps=[points[i] for i in ids];mi=Counter(k for v in ids for k in mats[v]);mouth=sum(abs(p.x)<.02 and 1.365<p.z<1.398 and p.y<-.05 for p in ps)
 components.append({'n':len(ids),'seed':ids[0],'materials':dict(mi),'bbox_min':[round(min(p[j] for p in ps),5) for j in range(3)],'bbox_max':[round(max(p[j] for p in ps),5) for j in range(3)],'mouth_region':mouth})
components.sort(key=lambda x:-x['n']);print(json.dumps(components,indent=2))
project_path('user-data/artifacts/studio3d-character/reference-iris-study-03/face-components.json').write_text(json.dumps(components,indent=2),encoding='utf8');ev.to_mesh_clear()
