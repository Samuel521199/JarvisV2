"""Bounded rounding of identified open-sheet exterior corners."""
import math
from modules.skills.studio3d.render_inspection import validate as inspection
VERSION='1.2.0'

def validate(c,names):
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.panel-lower-band.v1':
  from modules.skills.studio3d.panel_lower_band import validate as lower_band
  return lower_band(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.panel-aperture.v1':
  from modules.skills.studio3d.panel_aperture import validate as aperture
  return aperture(c,names)
 fields={'schema','author','evidence','targets','anchors','offset','segments','max_anchor_distance_increase','inspection'}
 if not isinstance(c,dict) or set(c)!=fields or c['schema']!='jarvis.studio3d.panel-corner.v1' or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid panel corner contract')
 if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Reference and source evidence required')
 if type(c['offset']) not in (int,float) or not math.isfinite(c['offset']) or not .015<=c['offset']<=.05:raise ValueError('Corner offset envelope')
 if type(c['segments']) is not int or c['segments'] not in (6,8,12):raise ValueError('Corner sampling envelope')
 if c['max_anchor_distance_increase']!=.0005 or type(c['max_anchor_distance_increase']) not in (int,float):raise ValueError('Anchor guard is fixed')
 if not isinstance(c['targets'],list) or not 1<=len(c['targets'])<=4:raise ValueError('Target budget')
 seen=set()
 for t in c['targets']:
  if not isinstance(t,dict) or set(t)!={'object','corners'} or t['object'] not in names or t['object'] in seen:raise ValueError('Explicit unique panel target required')
  seen.add(t['object'])
  if not isinstance(t['corners'],list) or not 1<=len(t['corners'])<=4:raise ValueError('Corner count budget')
  indices=set()
  for v in t['corners']:
   if not isinstance(v,dict) or set(v)!={'index','world_position'} or type(v['index']) is not int or not 0<=v['index']<10000 or v['index'] in indices:raise ValueError('Corner index binding')
   indices.add(v['index']);p=v['world_position']
   if not isinstance(p,list) or len(p)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>20 for x in p):raise ValueError('Finite corner position binding')
 if not isinstance(c['anchors'],list) or not 1<=len(c['anchors'])<=6 or len(set(c['anchors']))!=len(c['anchors']) or any(n not in names or n in seen for n in c['anchors']):raise ValueError('Unchanged attachment anchors required')
 inspection(c['inspection'],names)
 return c
