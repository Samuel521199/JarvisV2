import bpy,json
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath='D:/Jarvis/user-data/artifacts/studio3d-character/reference-iris-study-03/candidate.blend',load_ui=False,use_scripts=False)
o=bpy.data.objects['Face'];dg=bpy.context.evaluated_depsgraph_get();ev=o.evaluated_get(dg);me=ev.to_mesh();pts=[ev.matrix_world@v.co for v in me.vertices];adj=[[] for _ in me.vertices]
for e in me.edges:a,b=e.vertices;adj[a].append(b);adj[b].append(a)
seen={1633};st=[1633]
while st:
 for n in adj[st.pop()]:
  if n not in seen:seen.add(n);st.append(n)
for zcenter in [1.378,1.381,1.385]:
 band=[i for i in seen if abs(pts[i].x)<.020 and abs(pts[i].z-zcenter)<.010 and abs(pts[i].y+.075)<.022]
 for dp in [.0008,.0015,.0025,.004]:
  upper=[];lower=[];both=[]
  for i in band:
   near=[j for j in adj[i] if j in seen and pts[j].y-pts[i].y>dp]
   u=any(pts[j].z>pts[i].z+.0006 for j in near);l=any(pts[j].z<pts[i].z-.0006 for j in near)
   if u and l:both.append(i)
   elif u:upper.append(i)
   elif l:lower.append(i)
  stitches=[(i,j) for i in upper for j in adj[i] if j in lower]
  print('SEAM',zcenter,dp,'band',len(band),'up',len(upper),'low',len(lower),'both',len(both),'stitches',len(stitches))
ev.to_mesh_clear()
