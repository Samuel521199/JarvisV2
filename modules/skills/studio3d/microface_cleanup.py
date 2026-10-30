"""Bounded cosmetic cleanup of a measured frozen surface; no decimation/LOD."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.surface-cleanup.v1'
DEPENDENCIES={'muzzle-brake','barrel','barrel-band-2'}
def validate(c,names):
 if not isinstance(c,dict) or set(c)!={'schema','author','evidence','source_sha256','dependencies','small_faces','affected_vertices','strategy','inspection'} or c['schema']!=SCHEMA:raise ValueError('Unexpected local surface cleanup')
 if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Actual surface diagnosis required')
 sha=lambda s:isinstance(s,str) and len(s)==64 and all(x in '0123456789abcdef' for x in s)
 if not sha(c['source_sha256']) or not isinstance(c['dependencies'],dict) or set(c['dependencies'])!=DEPENDENCIES or not all(sha(s) for s in c['dependencies'].values()):raise ValueError('Complete exact source and neighbor dependencies required')
 for key,size,limit in [('small_faces',94,4900),('affected_vertices',260,5312)]:
  ids=c[key]
  if not isinstance(ids,list) or len(ids)!=size or any(type(i)!=int or not 0<=i<limit for i in ids) or ids!=sorted(set(ids)):raise ValueError('Measured complete component binding required')
 if c['strategy'] not in ('dissolve_only','merge_only','merge_then_dissolve'):raise ValueError('Unknown finite cleanup strategy')
 if not DEPENDENCIES<=set(names):raise ValueError('Declared inventory required')
 inspect_validate(c['inspection'],names)
 if c['inspection'].get('focus_region')!='muzzle' or c['inspection']['regions']!={'muzzle':['muzzle-brake']} or c['inspection']['resolution']!=[960,640] or c['inspection']['samples']!=12 or len(c['inspection']['views'])!=2:raise ValueError('Bounded actual pair required')
 return c
def coplanar(points,normal,anchor):
 if len(normal)!=3 or len(anchor)!=3 or not all(math.isfinite(v) for v in (*normal,*anchor)) or abs(sum(v*v for v in normal)-1)>1e-4:return False
 return bool(points) and all(len(p)==3 and all(math.isfinite(v) for v in p) and abs(sum(normal[i]*(p[i]-anchor[i]) for i in range(3)))<=1e-7 for p in points)
