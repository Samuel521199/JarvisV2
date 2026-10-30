"""Local visual opening reprofiling on source-bound thin surface grids."""
import math
from modules.skills.studio3d.render_inspection import validate as inspection
SCHEMA='jarvis.studio3d.panel-aperture.v1'

def validate(c,names):
 fields={'schema','author','evidence','bridge','panels','anchors','source_digests','half_width','top_drop','corner_radius','falloff','max_displacement','max_anchor_distance_increase','inspection'}
 if not isinstance(c,dict) or set(c)!=fields or c['schema']!=SCHEMA or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid aperture contract')
 if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Source/reference evidence required')
 if c['bridge'] not in names or not isinstance(c['panels'],list) or len(c['panels'])!=4 or len(set(c['panels']))!=4 or any(n not in names or n==c['bridge'] for n in c['panels']):raise ValueError('One bridge and four bound sheets required')
 targets={c['bridge'],*c['panels']}
 if not isinstance(c['source_digests'],dict) or set(c['source_digests'])!=targets or any(not isinstance(h,str) or len(h)!=64 or any(v not in '0123456789abcdef' for v in h) for h in c['source_digests'].values()):raise ValueError('Source geometry digests required')
 for key,lo,hi in [('half_width',.14,.22),('top_drop',.13,.20),('corner_radius',.025,.065)]:
  if type(c[key]) not in (int,float) or not math.isfinite(c[key]) or not lo<=c[key]<=hi:raise ValueError('Aperture parameter envelope')
 if c['falloff']!=.42 or c['max_displacement']!=.15 or c['max_anchor_distance_increase']!=.0005:raise ValueError('Fixed local preservation guards')
 if not isinstance(c['anchors'],list) or not 1<=len(c['anchors'])<=6 or len(set(c['anchors']))!=len(c['anchors']) or any(n not in names or n in targets for n in c['anchors']):raise ValueError('Unchanged anchors required')
 inspection(c['inspection'],names);return c

def sample_x(points,faces,y,z):
 """Interpolate depth only inside the original control surface in YZ."""
 for face in faces:
  for i in range(1,len(face)-1):
   a,b,c=[points[j] for j in (face[0],face[i],face[i+1])]
   den=(b[2]-c[2])*(a[1]-c[1])+(c[1]-b[1])*(a[2]-c[2])
   if abs(den)<1e-12:continue
   u=((b[2]-c[2])*(y-c[1])+(c[1]-b[1])*(z-c[2]))/den
   v=((c[2]-a[2])*(y-c[1])+(a[1]-c[1])*(z-c[2]))/den;w=1-u-v
   if min(u,v,w)>=-1e-6:return u*a[0]+v*b[0]+w*c[0]
 raise ValueError('Requested aperture point leaves original surface span')

def panel_points(points,faces,half_width,falloff):
 sign=1 if min(p[1] for p in points)>0 else -1 if max(p[1] for p in points)<0 else 0
 inner=min(abs(p[1]) for p in points)
 if not sign or not .10<=inner<=.11 or not inner<half_width<falloff:raise ValueError('Not the bound original central sheet span')
 result=[]
 for p in points:
  if abs(p[1])>=falloff:result.append(list(p));continue
  q=list(p);t=(abs(p[1])-inner)/(falloff-inner);q[1]+=sign*(half_width-inner)*(1-t)**2
  q[0]=sample_x(points,faces,q[1],q[2]);result.append(q)
 return result

def bridge_points(points,panels,half_width,top_drop,radius,edge_panels=None):
 # Only a three-row, seventeen-column source patch, without arbitrary topology.
 cols={}
 for p in points:cols.setdefault(round(p[1],6),[]).append(p)
 if len(points)!=51 or len(cols)!=17 or any(len(v)!=3 for v in cols.values()):raise ValueError('Bridge is not the original supported surface grid')
 cols=sorted((y,sorted(v,key=lambda p:p[2])) for y,v in cols.items());top=max(p[2] for p in points)
 if any(abs(v[-1][2]-top)>1e-6 for _,v in cols) or abs(cols[0][0]+.12)>1e-5 or abs(cols[-1][0]-.12)>1e-5:raise ValueError('Unsupported bridge span/crest')
 slopes=[(v[-1][0]-v[0][0])/(v[-1][2]-v[0][2]) for _,v in cols]
 if max(slopes)-min(slopes)>1e-5:raise ValueError('Bridge rake is not consistent')
 slope=sum(slopes)/len(slopes)
 def depth(y,z):
  if abs(y)>.12:
   mesh=next((p for p in panels if min(v[1] for v in p['points'])>0 and y>0 or max(v[1] for v in p['points'])<0 and y<0),None)
   if mesh is None:raise ValueError('Missing adjacent source panel')
   return sample_x(mesh['points'],mesh['faces'],y,z)
  for (a,av),(b,bv) in zip(cols,cols[1:]):
   if a-1e-6<=y<=b+1e-6:
    t=(y-a)/(b-a);return av[-1][0]*(1-t)+bv[-1][0]*t+slope*(z-top)
  raise ValueError('Bridge depth interpolation failed')
 verts=[];faces=[];half=half_width
 for k in range(3):
  for j in range(65):
   y=(j/64*2-1)*half;d=max(0,abs(y)-(half_width-radius))
   lower=top-top_drop-radius+math.sqrt(max(0,radius*radius-min(d,radius)**2));z=lower+(top-lower)*k/2
   x=depth(y,z)
   if edge_panels is not None and abs(y)>1e-8:
    sign=1 if y>0 else -1
    adjacent=next((p for p in edge_panels if min(v[1] for v in p['points'])>0 and sign>0 or max(v[1] for v in p['points'])<0 and sign<0),None)
    if adjacent is None:raise ValueError('Missing deformed sheet edge')
    correction=sample_x(adjacent['points'],adjacent['faces'],sign*half,z)-depth(sign*half,z)
    x+=correction*(abs(y)/half)**4
   verts.append([x,y,z])
 for k in range(2):
  for j in range(64):a=k*65+j;faces.append([a,a+1,a+66,a+65])
 return verts,faces
