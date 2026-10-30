"""Receipt-bound, axial seating of complete cosmetic mesh components."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.component-seat.v1'

def supported_modifiers(rows):
 # Existing tiny edge highlight bevels may stay; never evaluate arbitrary stacks.
 if len(rows)>1 or any(r['type']!='BEVEL' or not 0<r['width']<=.002 or not 1<=r['segments']<=6 for r in rows):raise ValueError('Only one bounded existing edge bevel is supported')
 return True

def validate(c,names):
 fields={'schema','author','evidence','object','source_digest','targets','max_move','embed','inspection'}
 if not isinstance(c,dict) or set(c)!=fields or c['schema']!=SCHEMA or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid component seating contract')
 if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600 or c['object'] not in names:raise ValueError('Bound component evidence/object required')
 h=c['source_digest']
 if not isinstance(h,str) or len(h)!=64 or any(v not in '0123456789abcdef' for v in h):raise ValueError('Source digest required')
 for k,lo,hi in [('max_move',.005,.03),('embed',.0003,.0015)]:
  if type(c[k]) not in (int,float) or not math.isfinite(c[k]) or not lo<=c[k]<=hi:raise ValueError('Component seating envelope')
 if not isinstance(c['targets'],list) or not 1<=len(c['targets'])<=24:raise ValueError('Component budget')
 used=set()
 for t in c['targets']:
  if not isinstance(t,dict) or set(t)!={'indices','center','support','axis'}:raise ValueError('Bound component target required')
  ids=t['indices']
  if not isinstance(ids,list) or not 8<=len(ids)<=64 or any(type(i) is not int or i<0 or i>20000 for i in ids) or len(set(ids))!=len(ids) or used.intersection(ids):raise ValueError('Unique component indices')
  used.update(ids)
  if t['support'] not in names or t['support']==c['object']:raise ValueError('Immutable support required')
  if not isinstance(t['center'],list) or len(t['center'])!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>5 for v in t['center']):raise ValueError('Finite component center')
  if not isinstance(t['axis'],list) or len(t['axis'])!=3 or any(type(v) not in (int,float) for v in t['axis']) or t['axis'] not in ([1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]):raise ValueError('Canonical axial seating only')
 inspect_validate(c['inspection'],names);return c
