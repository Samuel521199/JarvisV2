import bpy,json
from collections import Counter
from mathutils import Vector
from pathlib import Path
src='D:/Jarvis/user-data/artifacts/studio3d-character/reference-iris-study-03/candidate.blend'
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
Path('D:/Jarvis/user-data/artifacts/studio3d-character/reference-iris-study-03/face-components.json').write_text(json.dumps(components,indent=2),encoding='utf8');ev.to_mesh_clear()
