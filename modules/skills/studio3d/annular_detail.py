"""Refine existing circular exterior beads; never invent functional geometry."""
import math
from modules.skills.studio3d.attachment_seat import components
from modules.skills.studio3d.render_inspection import validate as inspect_validate
VERSION='1.2.0'

def validate(c,names):
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.trail-band.v1':
  from modules.skills.studio3d.trail_band import validate as band
  return band(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.collar-profile.v1':
  from modules.skills.studio3d.collar_profile import validate as collar
  return collar(c,names)
 fields={'schema','author','evidence','targets','segments','tube_segments','embed','max_move','inspection'}
 if not isinstance(c,dict) or set(c)!=fields or c['schema']!='jarvis.studio3d.annular-detail.v1' or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid annular contract')
 if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Evidence required')
 if type(c['segments']) is not int or c['segments'] not in (128,192,256) or type(c['tube_segments']) is not int or c['tube_segments'] not in (12,16,24):raise ValueError('Bounded high sampling required')
 for k,lo,hi in [('embed',.0003,.0008),('max_move',.005,.012)]:
  if type(c[k]) not in (int,float) or not math.isfinite(c[k]) or not lo<=c[k]<=hi:raise ValueError('Seat envelope exceeded')
 if not isinstance(c['targets'],list) or not 1<=len(c['targets'])<=2:raise ValueError('One or two targets')
 seen=set()
 for t in c['targets']:
  if not isinstance(t,dict) or set(t)!={'object','center','supports','expected_components'} or t['object'] not in names or t['object'] in seen:raise ValueError('Invalid annular target')
  seen.add(t['object'])
  if not isinstance(t['center'],list) or len(t['center'])!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>10 for x in t['center']):raise ValueError('Invalid Y-axis center')
  if type(t['expected_components']) is not int or not 1<=t['expected_components']<=8:raise ValueError('Component budget')
  if not isinstance(t['supports'],list) or not 1<=len(t['supports'])<=4 or len(set(t['supports']))!=len(t['supports']) or any(n not in names for n in t['supports']):raise ValueError('Explicit support binding required')
 if any(n in seen for t in c['targets'] for n in t['supports']):raise ValueError('Support must stay unchanged')
 inspect_validate(c['inspection'],names)
 return c

def fit_rings(vertices,faces,center,expected):
 if not 64<=len(vertices)<=10000 or len(faces)>10000 or any(len(f)!=4 or len(set(f))!=4 or any(type(i) is not int or not 0<=i<len(vertices) for i in f) for f in faces):raise ValueError('Closed quad bead source required')
 edges={}
 for face in faces:
  for a,b in zip(face,face[1:]+face[:1]):
   k=tuple(sorted((a,b)));edges[k]=edges.get(k,0)+1
 if any(v!=2 for v in edges.values()):raise ValueError('Non-manifold bead source')
 groups=components(len(vertices),faces)
 if len(groups)!=expected:raise ValueError('Unexpected component count')
 result=[]
 for ids in groups:
  ps=[[v-c for v,c in zip(vertices[i],center)] for i in ids]
  if any(not all(math.isfinite(x) for x in p) for p in ps):raise ValueError('Non-finite source')
  rho=[math.hypot(p[0],p[2]) for p in ps];r=sum(rho)/len(ps);h=sum(p[1] for p in ps)/len(ps);tube=sum(math.hypot(q-r,p[1]-h) for q,p in zip(rho,ps))/len(ps)
  error=max(abs(math.hypot(q-r,p[1]-h)-tube) for q,p in zip(rho,ps))
  if not .03<r<1 or not .002<tube<.02 or not tube*2<abs(h)<.3 or error>2e-6:raise ValueError('Not a supported circular Y-axis bead')
  if max(abs(sum(p[k] for p in ps)/len(ps)) for k in (0,2))>2e-6:raise ValueError('Off-center or incomplete ring')
  angles=sorted({round(math.atan2(p[2],p[0])%math.tau,5) for p in ps})
  # Float points near zero may straddle 2pi; quantize to fitted angular lattice.
  n=next((n for n in (32,48,64,96,128) if len(ps)%n==0 and 4<=len(ps)//n<=16 and all(abs(((math.atan2(p[2],p[0])*n/math.tau)-round(math.atan2(p[2],p[0])*n/math.tau)))<2e-4 for p in ps)),None)
  if n is None:raise ValueError('Irregular source sampling')
  slots={}
  for p,q in zip(ps,rho):
   a=round(math.atan2(p[2],p[0])*n/math.tau)%n;slots.setdefault(a,[]).append(math.atan2(p[1]-h,q-r)%math.tau)
  count=len(ps)//n
  if len(slots)!=n or any(len(v)!=count for v in slots.values()):raise ValueError('Irregular tube lattice')
  for values in slots.values():
   values=sorted(values)
   if any(abs(((values[(i+1)%count]-values[i])%math.tau)-math.tau/count)>2e-4 for i in range(count)):raise ValueError('Nonuniform tube lattice')
  result.append({'radius':r,'axial_center':h,'tube':tube,'source_segments':n,'source_tube_segments':count,'fit_error':error,'source_vertices':len(ps)})
 return result

def geometry(r,h,tube,segments,tube_segments,center):
 vertices=[];faces=[]
 for i in range(segments):
  a=math.tau*i/segments
  for j in range(tube_segments):
   b=math.tau*j/tube_segments;rho=r+tube*math.cos(b)
   vertices.append([center[0]+rho*math.cos(a),center[1]+h+tube*math.sin(b),center[2]+rho*math.sin(a)])
 for i in range(segments):
  for j in range(tube_segments):faces.append([i*tube_segments+j,((i+1)%segments)*tube_segments+j,((i+1)%segments)*tube_segments+(j+1)%tube_segments,i*tube_segments+(j+1)%tube_segments])
 return vertices,faces
