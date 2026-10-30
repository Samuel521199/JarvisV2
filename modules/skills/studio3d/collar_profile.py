"""Bounded art-only profile replacement for two source-bound axle covers."""
import math,re
from modules.skills.studio3d.render_inspection import validate as inspect
SCHEMA='jarvis.studio3d.collar-profile.v1'
TARGETS=('axle-collar-left','axle-collar-right')

def validate(c,names):
 fields={'schema','author','evidence','source_digests','neck_radius','shoulder_width','inspection'}
 if not isinstance(c,dict) or set(c)!=fields or c['schema']!=SCHEMA or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid collar profile contract')
 if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1800:raise ValueError('Visible reference/source evidence required')
 for k,lo,hi in [('neck_radius',.098,.108),('shoulder_width',.018,.028)]:
  if type(c[k]) not in (int,float) or not math.isfinite(c[k]) or not lo<=c[k]<=hi:raise ValueError('Collar profile envelope: '+k)
 if not isinstance(c['source_digests'],dict) or set(c['source_digests'])!=set(TARGETS) or any(n not in names or not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for n,v in c['source_digests'].items()):raise ValueError('Both original cover bindings required')
 if 'axle' not in names:raise ValueError('Axle support required')
 inspect(c['inspection'],names);return c

def fit(points,faces,side):
 if len(points)!=194 or len(faces)!=240 or side not in (-1,1):raise ValueError('Original four-ring cylinder required')
 rings={}
 for p in points:
  y=side*p[1];r=math.hypot(p[0],p[2]-.5)
  i=min(range(4),key=lambda i:abs(y-(.64,.65075,.84425,.855)[i]))
  if abs(y-(.64,.65075,.84425,.855)[i])>2e-6:raise ValueError('Source axial position mismatch')
  if r<1e-6:
   if i not in (0,3):raise ValueError('Unexpected center point')
   rings.setdefault(('cap',i),[]).append(p);continue
  if abs(r-(.1104,.12,.12,.1104)[i])>2e-6:raise ValueError('Original cover radius mismatch')
  rings.setdefault(i,[]).append(p)
 if any(len(rings.get(i,[]))!=48 for i in range(4)) or any(len(rings.get(('cap',i),[]))!=1 for i in (0,3)):raise ValueError('Original source sampling mismatch')
 for i in range(4):
  angles=sorted(math.atan2(p[2]-.5,p[0])%math.tau for p in rings[i])
  if any(abs((angles[(j+1)%48]-angles[j])%math.tau-math.tau/48)>1e-5 for j in range(48)):raise ValueError('Irregular source angular grid')
 edges={}
 for f in faces:
  if len(f) not in (3,4) or len(set(f))!=len(f) or any(type(i) is not int or not 0<=i<194 for i in f):raise ValueError('Unexpected source faces')
  for a,b in zip(f,f[1:]+f[:1]):key=tuple(sorted((a,b)));edges[key]=edges.get(key,0)+1
 if any(n!=2 for n in edges.values()):raise ValueError('Source must be closed')
 return {'axis':'Y','side':side,'center_xz':[0,.5],'span':[.64,.855],'maximum_radius':.12,'source_vertices':194}

def profile(c):
 r=c['neck_radius'];w=c['shoulder_width'];length=.215
 left=[(0.,.1104),(.005375,.1152),(.01075,.12),(w,.12)]
 for u in (.25,.5,.75,1.):left.append((w+.024*u,.12+(r-.12)*(u*u*(3-2*u))))
 return left+[(length/2,r)]+[(length-y,radius) for y,radius in left[::-1]]

def build(c,side):
 rings=profile(c);n=128;v=[];f=[]
 for y,r in rings:
  for i in range(n):a=math.tau*i/n;v.append([r*math.cos(a),side*(.64+y),.5+r*math.sin(a)])
 for j in range(len(rings)-1):
  for i in range(n):k=(i+1)%n;f.append([j*n+i,(j+1)*n+i,(j+1)*n+k,j*n+k])
 for j,end in ((0,False),(len(rings)-1,True)):
  index=len(v);v.append([0,side*(.64+rings[j][0]),.5])
  for i in range(n):face=[index,j*n+i,j*n+(i+1)%n];f.append(face[::-1] if end else face)
 if side<0:f=[p[::-1] for p in f]
 return v,f

def face_uv(points):
 """Separate two planar cap islands from the unwrapped side strip."""
 if max(p[1] for p in points)-min(p[1] for p in points)<1e-7:
  center=.25 if abs(points[0][1])<.75 else .75
  return [[center+.22*p[0]/.12,.25+.22*(p[2]-.5)/.12] for p in points]
 us=[math.atan2(p[2]-.5,p[0])%math.tau/math.tau for p in points]
 if max(us)-min(us)>.5:us=[u+1 if u<.5 else u for u in us]
 return [[u,.5+.5*(abs(p[1])-.64)/.215] for u,p in zip(us,points)]
