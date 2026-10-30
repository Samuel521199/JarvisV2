"""Source-bound blind rear surface relief for a game-art pedestal, not internals."""
import math
from collections import Counter
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.rear-face-relief.v1'
def validate(c,names):
 if not isinstance(c,dict) or set(c)!={'schema','author','evidence','target','source_digest','depth','inspection'} or c['schema']!=SCHEMA:raise ValueError('Unexpected rear relief contract')
 if c['author'] not in ('Codex','Jarvis') or c['target']!='central-pedestal' or c['target'] not in names:raise ValueError('Bound pedestal required')
 if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Exterior hypothesis required')
 if not isinstance(c['source_digest'],str) or len(c['source_digest'])!=64 or any(x not in '0123456789abcdef' for x in c['source_digest']):raise ValueError('Bound source digest required')
 if type(c['depth']) not in (float,int) or not math.isfinite(c['depth']) or not .025<=c['depth']<=.055:raise ValueError('Blind shallow exterior depth only')
 inspect_validate(c['inspection'],names);return c

def patch(vertices,faces,depth):
 if type(depth) not in (int,float) or not math.isfinite(depth) or not .025<=depth<=.055:raise ValueError('Relief depth envelope')
 bounds=[[min(p[j] for p in vertices) for j in range(3)],[max(p[j] for p in vertices) for j in range(3)]]
 if any(abs(bounds[k][j]-[[-.215,-.225,.555],[.155,.225,.825]][k][j])>2e-6 for k in range(2) for j in range(3)):raise ValueError('Original exterior envelope required')
 candidates=[i for i,f in enumerate(faces) if len(f)==4 and all(abs(vertices[v][0]+.215)<2e-6 for v in f)]
 if len(candidates)!=1:raise ValueError('One original rear flat quad required')
 removed=candidates[0];outer=faces[removed];ps=[vertices[i] for i in outer]
 if any(abs(abs(p[1])-.2)>2e-6 or min(abs(p[2]-.58),abs(p[2]-.8))>2e-6 for p in ps):raise ValueError('Expected bevel boundary required')
 newv=[list(p) for p in vertices];newf=[list(f) for i,f in enumerate(faces) if i!=removed];kept=len(newf);rings=[]
 for x,hy,hz,r in [(-.215,.167,.084,.012),(-.209,.161,.078,.010),(-.215+depth-.006,.161,.078,.010),(-.215+depth,.155,.072,.009)]:
  corners=[[x,math.copysign(hy,p[1]),.69+math.copysign(hz,p[2]-.69)] for p in ps];ring=[]
  for i,q in enumerate(corners):
   prev=corners[(i-1)%4];nxt=corners[(i+1)%4]
   def towards(dst):
    length=math.dist(q,dst);return [q[j]+(dst[j]-q[j])*r/length for j in range(3)]
   a,b=towards(prev),towards(nxt)
   for t in (0,.25,.5,.75,1):
    ring.append(len(newv));newv.append([(1-t)**2*a[j]+2*t*(1-t)*q[j]+t*t*b[j] for j in range(3)])
  rings.append(ring)
 first=rings[0]
 for i in range(4):
  for k in range(4):newf.append([outer[i],first[i*5+k+1],first[i*5+k]])
  newf.append([outer[i],outer[(i+1)%4],first[((i+1)%4)*5],first[i*5+4]])
 for a,b in zip(rings,rings[1:]):
  for i in range(20):newf.append([a[i],a[(i+1)%20],b[(i+1)%20],b[i]])
 newf.append(rings[-1])
 edges=Counter(tuple(sorted((a,b))) for f in newf for a,b in zip(f,f[1:]+f[:1]))
 if any(v!=2 for v in edges.values()):raise ValueError('Relief must remain closed')
 return newv,newf,{'removed_face_index':removed,'preserved_faces':kept,'preserved_vertices':len(vertices),'new_vertices':80,'new_faces':81,'blind_depth':depth}
