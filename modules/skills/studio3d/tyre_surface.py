"""Bounded exterior tyre repair; visual geometry only, no simulation model."""
import math
from modules.skills.studio3d.render_inspection import validate as inspection

VERSION='1.0.1'

def validate(v,names):
 fields={'schema','author','goal','evidence','pairs','circumference_segments','longitudinal_depth','cross_depth','cross_count','rubber_color_scale','inspection'}
 if not isinstance(v,dict) or set(v)!=fields or v['schema']!='jarvis.studio3d.tyre-surface.v1' or v['author'] not in ('Codex','Jarvis'):raise ValueError('Invalid tyre contract')
 for k in ('goal','evidence'):
  if not isinstance(v[k],str) or not 1<=len(v[k])<=1600:raise ValueError('Bounded purpose/evidence required')
 if not isinstance(v['pairs'],list) or not 1<=len(v['pairs'])<=2:raise ValueError('One or two declared tyre pairs required')
 seen=set()
 for p in v['pairs']:
  if not isinstance(p,dict) or set(p)!={'tire','tread','center','axis'} or p['axis']!='Y':raise ValueError('Only declared Y-axis exterior wheels supported')
  for k in ('tire','tread'):
   if p[k] not in names or p[k] in seen:raise ValueError('Missing or reused target')
   seen.add(p[k])
  if not isinstance(p['center'],list) or len(p['center'])!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>20 for x in p['center']):raise ValueError('Invalid wheel center')
 for k,lo,hi in [('longitudinal_depth',.0005,.003),('cross_depth',.0003,.002),('rubber_color_scale',.15,.65)]:
  if type(v[k]) not in (int,float) or not math.isfinite(v[k]) or not lo<=v[k]<=hi:raise ValueError('Tyre visual envelope exceeded')
 if type(v['circumference_segments']) is not int or v['circumference_segments'] not in (256,384,512):raise ValueError('Bounded high-resolution ring required')
 if type(v['cross_count']) is not int or v['cross_count'] not in (32,48,64) or v['circumference_segments']%v['cross_count']:raise ValueError('Cut sampling must align')
 inspection(v['inspection'],names)
 if any(p['tread'] in members for p in v['pairs'] for members in v['inspection']['regions'].values()):raise ValueError('Comparison region must survive obsolete overlay removal')
 return v

def geometry(outer,inner,width,segments,longitudinal_depth,cross_depth,cross_count):
 if not .2<=outer<=1 or not outer*.75<=inner<outer*.97 or not .05<=width<=.4:raise ValueError('Unsupported source tyre dimensions')
 # Densely sample shallow grooves in the SAME continuous surface. Do not add
 # disconnected mini-cylinders to imitate cuts in rubber.
 samples={round(-.5+i/48,8) for i in range(49)}
 for center in (-.20,0,.20):
  samples.update(round(center+d,8) for d in (-.018,-.012,-.006,0,.006,.012,.018))
 profile=[]
 def smooth(x):x=max(0,min(1,x));return x*x*(3-2*x)
 for h in sorted(samples):
  r=outer-(outer-inner)*.52*smooth((abs(h)-.29)/.21)
  depth=max(math.exp(-((h-center)/.010)**2) for center in (-.20,0,.20))*longitudinal_depth
  # Carry transverse cuts around the shoulder, fading only at the sidewall.
  # The first trial faded at .41 and lost the reference-visible shoulder marks.
  profile.append((r-depth,h*width,1-smooth((abs(h)-.44)/.06)))
 profile.extend([(inner+.006,width*.49,0),(inner,width*.47,0),(inner,-width*.47,0),(inner+.006,-width*.49,0)])
 vertices=[];faces=[]
 for r,h,mask in profile:
  for i in range(segments):
   angle=math.tau*i/segments;phase=((i*cross_count/segments+.5)%1)-.5
   cut=cross_depth*max(0,1-abs(phase)/.14)**2*mask
   radius=r-cut;vertices.append([radius*math.cos(angle),h,radius*math.sin(angle)])
 for j in range(len(profile)):
  for i in range(segments):
   a=j*segments+i;b=j*segments+(i+1)%segments;d=((j+1)%len(profile))*segments+i;c=((j+1)%len(profile))*segments+(i+1)%segments
   faces.append([a,b,c,d])
 return vertices,faces
