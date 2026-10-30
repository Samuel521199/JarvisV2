"""Source-bound cosmetic casing closure and open upper silhouette, game art only."""
import math
from modules.skills.studio3d.assembly_geometry import Mesh
from modules.skills.studio3d.render_inspection import validate as inspection
SCHEMA='jarvis.studio3d.exterior-closure.v1'

def validate(c,names):
 if not isinstance(c,dict) or set(c)!={'schema','author','evidence','target','source_digest','support_digests','cap_depth','saddle_span','inspection'} or c['schema']!=SCHEMA or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid exterior closure contract')
 if c['target']!='cradle-rails' or c['target'] not in names or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Bound exterior source required')
 def digest(v):return isinstance(v,str) and len(v)==64 and all(x in '0123456789abcdef' for x in v)
 if not digest(c['source_digest']) or not isinstance(c['support_digests'],dict) or set(c['support_digests'])!={'cradle-trough','barrel'} or any(n not in names or not digest(h) for n,h in c['support_digests'].items()):raise ValueError('Support/source digests required')
 for k,lo,hi in [('cap_depth',.05,.08),('saddle_span',.10,.14)]:
  if type(c[k]) not in (int,float) or not math.isfinite(c[k]) or not lo<=c[k]<=hi:raise ValueError('Exterior silhouette envelope')
 inspection(c['inspection'],names);return c

def rounded_rect(y0,y1,z0,z1,r,steps=6):
 result=[]
 for cy,cz,start in [(y1-r,z0+r,-math.pi/2),(y1-r,z1-r,0),(y0+r,z1-r,math.pi/2),(y0+r,z0+r,math.pi)]:
  for i in range(steps+1):
   a=start+i*math.pi/(2*steps);result.append([cy+r*math.cos(a),cz+r*math.sin(a)])
 return result

def notch_from_surface(radii):
 if len(radii)!=3 or any(not math.isfinite(r) or not .04<=r<=.08 for r in radii) or max(radii)-min(radii)>.003:raise ValueError('Unsupported local exterior cross-section')
 return max(radii)+.0025

def build(c,notch_radius=.0542):
 """Append surfaces to an existing static semantic group, no operational internals."""
 parts=[];depth=c['cap_depth'];front=.765+depth
 def add(role,m,bevel=0,smooth=False):parts.append({'role':role,'vertices':m.vertices,'faces':m.faces,'bevel':bevel,'smooth_sides':smooth})
 cap=Mesh();cap.extrude(rounded_rect(-.18,.18,.883,1.055,.018),0,.765,front);add('front-closure',cap,.002)
 face=Mesh();face.extrude(rounded_rect(-.112,.112,.901,1.038,.012),0,front-.001,front+.009);add('raised-face',face,.0015)
 bosses=Mesh();bosses.tube([front+.008,0,.969],[front+.021,0,.969],.038,64);bosses.tube([front+.020,0,.969],[front+.028,0,.969],.022,48)
 for y in (-.087,.087):
  for z in (.916,1.022):bosses.tube([front+.008,y,z],[front+.016,y,z],.009,32)
 add('front-visible-round-heads',bosses,smooth=True)
 foot=Mesh();foot.box([.665,0,1.037],[c['saddle_span']+.02,.352,.030]);add('upper-foot',foot,.002)
 # U outline goes around the exterior barrel silhouette; it is not a functional bearing.
 if not .0425<=notch_radius<=.0825:raise ValueError('Bound measured exterior notch radius')
 outline=[[-.112,1.033],[.112,1.033],[.112,1.150],[notch_radius,1.150]]
 for i in range(1,33):
  a=-math.pi*i/32;outline.append([notch_radius*math.cos(a),1.150+notch_radius*math.sin(a)])
 outline.append([-.112,1.150]);upper=Mesh();upper.extrude(outline,0,.665-c['saddle_span']/2,.665+c['saddle_span']/2);add('open-upper-silhouette',upper,.0015)
 sides=Mesh()
 for s in (-1,1):sides.tube([.665,s*.111,1.114],[.665,s*.123,1.114],.017,48)
 add('upper-visible-round-heads',sides,smooth=True)
 return parts

def check_source(rows):
 """This version is deliberately limited to the measured original casing layout."""
 expected={'cradle-trough':([-.65,-.115,.895],[.81,.115,1.025]),'barrel':([-.57,-.07755,1.07245],[2.05,.07755,1.22755])}
 for n,b in expected.items():
  if n not in rows or any(abs(rows[n][k][i]-b[k][i])>2e-5 for k in range(2) for i in range(3)):raise ValueError('Unsupported casing/barrel envelope')
 return True
