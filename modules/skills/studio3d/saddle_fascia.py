"""Visible shallow exterior panels on a source-bound carriage box; art only."""
import math
from modules.skills.studio3d.assembly_geometry import Mesh
from modules.skills.studio3d.exterior_closure import rounded_rect
from modules.skills.studio3d.render_inspection import validate as inspection
SCHEMA='jarvis.studio3d.saddle-fascia.v1'
def validate(c,names):
 if not isinstance(c,dict) or set(c)!={'schema','author','evidence','target','source_digest','face_depth','inspection'} or c['schema']!=SCHEMA or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid saddle face contract')
 if c['target']!='axle-saddle' or c['target'] not in names or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Bound original saddle required')
 if not isinstance(c['source_digest'],str) or len(c['source_digest'])!=64 or any(x not in '0123456789abcdef' for x in c['source_digest']):raise ValueError('Invalid source digest')
 if type(c['face_depth']) not in (int,float) or not math.isfinite(c['face_depth']) or not .012<=c['face_depth']<=.024:raise ValueError('Shallow fascia depth only')
 inspection(c['inspection'],names);return c

def build(c):
 parts=[];d=c['face_depth'];front=.115+d;rear=-.235-d
 def part(role,m,bevel=0,smooth=False):parts.append({'role':role,'vertices':m.vertices,'faces':m.faces,'bevel':bevel,'smooth_sides':smooth})
 m=Mesh();m.extrude(rounded_rect(-.085,.085,.387,.617,.012),0,.113,front);part('front-vertical-fascia',m,.0015)
 m=Mesh()
 for z in (.435,.565):
  m.tube([front-.001,0,z],[front+.006,0,z],.026,48);m.tube([front+.005,0,z],[front+.011,0,z],.017,32)
 for y in (-.061,.061):
  for z in (.409,.594):m.tube([front-.001,y,z],[front+.006,y,z],.007,24)
 part('front-visible-relief',m,smooth=True)
 m=Mesh();m.extrude(rounded_rect(-.225,.225,.435,.565,.016),0,rear,-.233);part('rear-horizontal-fascia',m,.0015)
 m=Mesh()
 for y in (-.135,0,.135):
  m.tube([rear-.008,y,.50],[rear+.001,y,.50],.020,48)
  m.tube([rear-.013,y,.50],[rear-.007,y,.50],.011,6)
 part('rear-visible-relief',m,smooth=True)
 return parts
