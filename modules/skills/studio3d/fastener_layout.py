"""Bounded relocation of explicitly bound exterior head components."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.fastener-layout.v1'

def validate(c,names):
 fields={'schema','author','evidence','object','source_digest','targets','blockers','max_move','embed','inspection'}
 if not isinstance(c,dict) or set(c)!=fields or c['schema']!=SCHEMA or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid layout contract')
 if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600 or c['object'] not in names:raise ValueError('Bound layout evidence/object required')
 h=c['source_digest']
 if not isinstance(h,str) or len(h)!=64 or any(v not in '0123456789abcdef' for v in h):raise ValueError('Source digest required')
 if c['max_move']!=.65 or c['embed']!=.0006:raise ValueError('Fixed displacement and seating guards')
 if not isinstance(c['targets'],list) or not 1<=len(c['targets'])<=24:raise ValueError('Component budget')
 used=set()
 for t in c['targets']:
  if not isinstance(t,dict) or set(t)!={'indices','center','support','yz'}:raise ValueError('Bound component target required')
  ids=t['indices']
  if not isinstance(ids,list) or not 8<=len(ids)<=64 or any(type(i) is not int or i<0 or i>20000 for i in ids) or len(set(ids))!=len(ids) or used.intersection(ids):raise ValueError('Unique component indices')
  used.update(ids)
  if t['support'] not in names or t['support']==c['object']:raise ValueError('Immutable support required')
  for k,n in [('center',3),('yz',2)]:
   if not isinstance(t[k],list) or len(t[k])!=n or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>5 for v in t[k]):raise ValueError('Finite layout position')
  if not .3<=abs(t['yz'][0])<=.88 or not .55<=t['yz'][1]<=1.405 or t['yz'][0]*t['center'][1]<=0:raise ValueError('Local same-side shield layout envelope')
 if not isinstance(c['blockers'],list) or not 1<=len(c['blockers'])<=6 or len(set(c['blockers']))!=len(c['blockers']) or any(n not in names or n==c['object'] for n in c['blockers']):raise ValueError('Adjacent blockers required')
 inspect_validate(c['inspection'],names);return c

def rotate_x_to_normal(p,n):
 """Minimal rotation, preserving head dimensions and handedness."""
 if len(n)!=3 or any(not math.isfinite(v) for v in n) or abs(sum(v*v for v in n)-1)>1e-5 or n[0]<.7:raise ValueError('Support normal outside facing envelope')
 v=(0,-n[2],n[1])
 def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
 a=cross(v,p);b=cross(v,a)
 return [p[i]+a[i]+b[i]/(1+n[0]) for i in range(3)]

def bound_component(groups,indices):
 if set(indices) not in [set(g) for g in groups]:raise ValueError('Selection must equal one complete disconnected component')
 return indices
