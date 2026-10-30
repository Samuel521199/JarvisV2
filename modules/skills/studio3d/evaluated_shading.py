"""Correct flat-shaded bevel bands without moving the evaluated art surface."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.evaluated-shading.v1'
PLANAR_SCHEMA='jarvis.studio3d.evaluated-shading.v2'
PLANAR_DEPENDENCIES={'muzzle-brake','barrel','barrel-band-2','brake-port-0','brake-port-1','muzzle-opening'}
SOURCES={'rear-cover-body':(8,.025,5),'shaped-rear-cover':(20,.012,4),'breech-top-cover':(8,.008,5)}
def validate(c,names):
 if isinstance(c,dict) and c.get('schema')==PLANAR_SCHEMA:return validate_planar(c,names)
 if not isinstance(c,dict) or set(c)!={'schema','author','evidence','targets','inspection'} or c['schema']!=SCHEMA:raise ValueError('Unexpected shading contract')
 if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Author and diagnosis required')
 if not isinstance(c['targets'],list) or not 1<=len(c['targets'])<=3:raise ValueError('One to three diagnosed cover objects')
 seen=set()
 for t in c['targets']:
  if not isinstance(t,dict) or set(t)!={'object','source_digest'} or t['object'] not in SOURCES or t['object'] not in names or t['object'] in seen:raise ValueError('Bound unique cover target required')
  seen.add(t['object']);s=t['source_digest']
  if not isinstance(s,str) or len(s)!=64 or any(x not in '0123456789abcdef' for x in s):raise ValueError('Source digest required')
 inspect_validate(c['inspection'],names);return c
def retained_plane(points,normal,planes):
 return any(sum(a*b for a,b in zip(normal,n))>.99999 and all(abs(sum(a*b for a,b in zip(p,n))-d)<1e-6 for p in points) for n,d in planes)

def front_faces(points,faces):
 """Classify only an existing positive-X planar exterior end, not new geometry."""
 if not points or any(len(p)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in points):raise ValueError('Finite evaluated vertices required')
 plane=max(p[0] for p in points)
 if any(len(f)<3 or any(type(i)!=int or not 0<=i<len(points) for i in f) for f in faces):raise ValueError('Complete evaluated faces required')
 return [i for i,f in enumerate(faces) if all(abs(points[j][0]-plane)<1e-6 for j in f)]

def validate_planar(c,names):
 if set(c)!={'schema','author','evidence','source_sha256','dependencies','front_face_indices','inspection'}:raise ValueError('Unexpected planar shading contract')
 if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Author and actual diagnosis required')
 sha=lambda x:isinstance(x,str) and len(x)==64 and all(v in '0123456789abcdef' for v in x)
 if not sha(c['source_sha256']):raise ValueError('Exact source bytes required')
 if not isinstance(c['dependencies'],dict) or set(c['dependencies'])!=PLANAR_DEPENDENCIES or not all(sha(s) for s in c['dependencies'].values()):raise ValueError('All source/cutter/neighbor dependencies required')
 if not {'muzzle-brake','barrel','barrel-band-2'}<=set(names):raise ValueError('Declared visual inventory required')
 ids=c['front_face_indices']
 if not isinstance(ids,list) or len(ids)!=96 or any(type(i)!=int or not 0<=i<4900 for i in ids) or ids!=sorted(set(ids)):raise ValueError('Exact sorted unique96face binding required')
 inspect_validate(c['inspection'],names)
 if c['inspection'].get('focus_region')!='muzzle' or c['inspection']['regions']!={'muzzle':['muzzle-brake']} or c['inspection']['resolution']!=[960,640] or c['inspection']['samples']!=12 or len(c['inspection']['views'])!=2:raise ValueError('Bounded actual exterior inspection required')
 return c
