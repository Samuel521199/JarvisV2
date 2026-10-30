"""Bounded cosmetic waist profile for the measured PaK38 pedestal box."""
import math
from modules.skills.studio3d.exterior_closure import rounded_rect
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.pedestal-profile.v1'

def validate(c,names):
 if not isinstance(c,dict) or set(c)!={'schema','author','evidence','target','source_digest','waist_inset','foot_height','inspection'} or c['schema']!=SCHEMA or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid pedestal profile contract')
 if c['target']!='central-pedestal' or c['target'] not in names or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Explicit original pedestal required')
 if not isinstance(c['source_digest'],str) or len(c['source_digest'])!=64 or any(x not in '0123456789abcdef' for x in c['source_digest']):raise ValueError('Source digest required')
 for k,lo,hi in [('waist_inset',.02,.04),('foot_height',.025,.045)]:
  if type(c[k]) not in (int,float) or not math.isfinite(c[k]) or not lo<=c[k]<=hi:raise ValueError('Pedestal profile bounds')
 inspect_validate(c['inspection'],names);return c

def check_original(vertices):
 expected={(x,y,z) for x in (-.215,.155) for y in (-.225,.225) for z in (.555,.825)}
 if len(vertices)!=8:raise ValueError('Original eight-vertex box required')
 for v in vertices:
  match=next((p for p in expected if max(abs(v[i]-p[i]) for i in range(3))<2e-6),None)
  if match is None:raise ValueError('Unsupported pedestal coordinates')
  expected.remove(match)
 return True

def build(c):
 """Keep upper/lower contact bands; sculpt only the visible middle silhouette."""
 inset=c['waist_inset'];foot=.555+c['foot_height']
 sections=[(.555,0),(foot,0),(.635,inset),(.675,inset),(.715,0),(.825,0)]
 verts=[];faces=[];n=36
 for z,i in sections:
  outline=rounded_rect(-.215+i,.155-i,-.225+i,.225-i,.023,8)
  assert len(outline)==n
  verts.extend([[x,y,z] for x,y in outline])
 for j in range(len(sections)-1):
  for k in range(n):faces.append([j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k])
 faces.extend([list(reversed(range(n))),list(range((len(sections)-1)*n,len(sections)*n))])
 return {'vertices':verts,'faces':faces,'bevel':.003,'smooth_sides':False,'role':'layered-pedestal-silhouette','sections':sections}
