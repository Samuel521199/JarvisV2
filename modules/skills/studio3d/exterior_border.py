"""Bounded visible perimeter bead on the existing PaK38 perforated art plate."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.exterior-border.v1'

def validate(c,names):
 if not isinstance(c,dict) or set(c)!={'schema','author','evidence','target','source_digest','dependency_digest','radius','inspection'} or c['schema']!=SCHEMA:raise ValueError('Unexpected border contract')
 if c['target']!='external-arm' or c['target'] not in names or c['author'] not in ('Codex','Jarvis'):raise ValueError('Bound visible plate required')
 if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Visible reference evidence required')
 for k in ('source_digest','dependency_digest'):
  if not isinstance(c[k],str) or len(c[k])!=64 or any(v not in '0123456789abcdef' for v in c[k]):raise ValueError('Source/dependency binding required')
 geometry(c['radius']);inspect_validate(c['inspection'],names);return c

def geometry(radius):
 if type(radius) not in (int,float) or not math.isfinite(radius) or not .005<=radius<=.008:raise ValueError('Border radius envelope')
 # Existing semicircular plate end; ends remain at the existing mounting side.
 r=.0525-radius;path=[(-.53,1.11+r),(-.74,1.11+r)]
 for i in range(65):
  a=math.pi/2+math.pi*i/64;path.append((-.96+r*math.cos(a),1.11+r*math.sin(a)))
 path.extend([(-.74,1.11-r),(-.53,1.11-r)])
 vs=[];fs=[];uv=[];lengths=[0.]
 for a,b in zip(path,path[1:]):lengths.append(lengths[-1]+math.dist(a,b))
 for i,(x,z) in enumerate(path):
  a=path[max(0,i-1)];b=path[min(len(path)-1,i+1)];dx,dz=b[0]-a[0],b[1]-a[1];l=math.hypot(dx,dz);nx,nz=-dz/l,dx/l
  for j in range(16):
   t=2*math.pi*j/16;vs.append([x+radius*math.cos(t)*nx,.1665+radius*math.sin(t),z+radius*math.cos(t)*nz])
 for i in range(len(path)-1):
  for j in range(16):
   fs.append([i*16+j,i*16+(j+1)%16,(i+1)*16+(j+1)%16,(i+1)*16+j]);uv.append([(lengths[i],j/16),(lengths[i],(j+1)/16),(lengths[i+1],(j+1)/16),(lengths[i+1],j/16)])
 for i in (0,len(path)-1):
  center=len(vs);vs.append([path[i][0],.1665,path[i][1]])
  for j in range(16):
   fs.append([center,i*16+j,i*16+(j+1)%16]);uv.append([(.5,.5),(.5+.4*math.cos(j*math.pi/8),.5+.4*math.sin(j*math.pi/8)),(.5+.4*math.cos((j+1)*math.pi/8),.5+.4*math.sin((j+1)*math.pi/8))])
 return vs,fs,uv,path
