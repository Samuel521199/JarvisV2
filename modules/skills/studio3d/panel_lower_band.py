"""PaK38 exterior-only coupled lower shield profile, in nominal art units.

This operator is deliberately asset-family specific. It does not infer hardware
or functioning armor mechanisms. It raises an existing lower silhouette while
retaining its sheet plane and translating the original rigid attachments.
"""
import math,re
from modules.skills.studio3d.render_inspection import validate as inspection

SCHEMA='jarvis.studio3d.panel-lower-band.v1'
PANELS=('shield-left-0','shield-left-1','shield-right-0','shield-right-1')
FLAPS=('shield-lower-flap--1','shield-lower-flap-1')
HARDWARE=('shield-seated-tabs','fasteners-shield')
TARGETS=PANELS+FLAPS+HARDWARE
RAKE=.44/.9

def validate(c,names):
 fields={'schema','author','evidence','source_digests','raise_height','inspection'}
 if not isinstance(c,dict) or set(c)!=fields or c['schema']!=SCHEMA or c['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid lower band contract')
 if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1800:raise ValueError('Actual source/reference evidence required')
 if type(c['raise_height']) not in (int,float) or not math.isfinite(c['raise_height']) or not .08<=c['raise_height']<=.14:raise ValueError('Lower silhouette envelope')
 if not isinstance(c['source_digests'],dict) or set(c['source_digests'])!=set(TARGETS) or any(n not in names or not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for n,v in c['source_digests'].items()):raise ValueError('All coupled source bindings required')
 if 'shield-struts' not in names or 'axle' not in names:raise ValueError('Unchanged support and occlusion evidence required')
 inspection(c['inspection'],names)
 return c

def displacement(z,height):
 t=min(1.,max(0.,(z-.66)/.24))
 dz=height*(1-t*t*(3-2*t))
 return (-RAKE*dz,0.,dz)

def shift(point,height):
 delta=displacement(point[2],height)
 return [p+d for p,d in zip(point,delta)]

def validate_sheet(name,points,faces):
 if name in FLAPS:
  if len(points)!=18 or len(faces)!=10 or any(len(f)!=4 for f in faces):raise ValueError('Original flap grid required')
  if abs(min(p[2] for p in points)-.41)>2e-6 or abs(max(p[2] for p in points)-.58)>2e-6:raise ValueError('Flap already changed or unsupported')
 elif name in PANELS:
  if len(points)!=142 or abs(min(p[2] for p in points)-.53)>2e-6 or abs(max(p[2] for p in points)-1.43)>2e-6:raise ValueError('Original bound panel profile required')
 else:raise ValueError('Not a supported sheet')
