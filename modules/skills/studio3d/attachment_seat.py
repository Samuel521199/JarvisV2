"""Bounded exterior fastener seating on a receipt-bound rendered support surface."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
VERSION='1.18.2'

def validate(c,names):
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.rear-contour.v1':
  from modules.skills.studio3d.rear_contour import validate as contour_validate
  return contour_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.curve-foot.v1':
  from modules.skills.studio3d.curve_foot import validate as foot_validate
  return foot_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.surface-cleanup.v1':
  from modules.skills.studio3d.microface_cleanup import validate as cleanup_validate
  return cleanup_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.trail-tab.v1':
  from modules.skills.studio3d.trail_tab import validate as tab_validate
  return tab_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.trail-pad.v1':
  from modules.skills.studio3d.trail_pad import validate as pad_validate
  return pad_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.curve-grip.v1':
  from modules.skills.studio3d.curve_grip import validate as grip_validate
  return grip_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.spade-frame.v1':
  from modules.skills.studio3d.spade_frame import validate as frame_validate
  return frame_validate(c,names)
 if isinstance(c,dict) and c.get('schema') in ('jarvis.studio3d.facade-pocket.v1','jarvis.studio3d.facade-pocket.v2','jarvis.studio3d.facade-slot-repair.v1'):
  from modules.skills.studio3d.facade_pocket import validate as pocket_validate
  return pocket_validate(c,names)
 if isinstance(c,dict) and c.get('schema') in ('jarvis.studio3d.evaluated-shading.v1','jarvis.studio3d.evaluated-shading.v2'):
  from modules.skills.studio3d.evaluated_shading import validate as shading_validate
  return shading_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.exterior-border.v1':
  from modules.skills.studio3d.exterior_border import validate as border_validate
  return border_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.rear-face-relief.v1':
  from modules.skills.studio3d.rear_face_relief import validate as relief_validate
  return relief_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.saddle-fascia.v1':
  from modules.skills.studio3d.saddle_fascia import validate as fascia_validate
  return fascia_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.pedestal-profile.v1':
  from modules.skills.studio3d.pedestal_profile import validate as profile_validate
  return profile_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.exterior-closure.v1':
  from modules.skills.studio3d.exterior_closure import validate as closure_validate
  return closure_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.component-seat.v1':
  from modules.skills.studio3d.component_seat import validate as component_validate
  return component_validate(c,names)
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.fastener-layout.v1':
  from modules.skills.studio3d.fastener_layout import validate as layout_validate
  return layout_validate(c,names)
 v2=isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.attachment-seat.v2'
 if not isinstance(c,dict) or set(c)!=({'schema','author','evidence','targets','inspection','radial_inset','embed','max_move'}|({'footprint_scale'} if v2 else set())):raise ValueError('Unexpected attachment fields')
 if c['schema'] not in ('jarvis.studio3d.attachment-seat.v1','jarvis.studio3d.attachment-seat.v2') or c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Declare bounded author/evidence')
 if v2 and (type(c['footprint_scale']) not in (int,float) or not math.isfinite(c['footprint_scale']) or not .65<=c['footprint_scale']<=1):raise ValueError('Footprint scale envelope')
 for k,lo,hi in [('radial_inset',0,.012),('embed',.0003,.0015),('max_move',.005,.03)]:
  if type(c[k]) not in (int,float) or not math.isfinite(c[k]) or not lo<=c[k]<=hi:raise ValueError('Attachment movement envelope')
 if not isinstance(c['targets'],list) or not 1<=len(c['targets'])<=2:raise ValueError('One or two declared attachments')
 seen=set()
 for t in c['targets']:
  if not isinstance(t,dict) or set(t)!=({'object','support','center','axis','radial_range','axial_range','expected_components'}|({'blockers'} if v2 else set())):raise ValueError('Invalid attachment target')
  if t['object'] not in names or t['support'] not in names or t['object']==t['support'] or t['object'] in seen:raise ValueError('Invalid object/support binding')
  seen.add(t['object'])
  if v2 and (not isinstance(t['blockers'],list) or not 1<=len(t['blockers'])<=6 or len(set(t['blockers']))!=len(t['blockers']) or any(n not in names or n in (t['object'],t['support']) for n in t['blockers'])):raise ValueError('Declare adjacent blocker objects')
  for k in ('center','axis'):
   if not isinstance(t[k],list) or len(t[k])!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>5 for v in t[k]):raise ValueError('Invalid attachment frame')
  if abs(sum(v*v for v in t['axis'])-1)>1e-6:raise ValueError('Unit axis required')
  for k in ('radial_range','axial_range'):
   v=t[k]
   if not isinstance(v,list) or len(v)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in v) or not 0<=v[0]<v[1]<=.4:raise ValueError('Invalid local component interval')
  if type(t['expected_components']) is not int or not 1<=t['expected_components']<=24:raise ValueError('Expected component budget')
 if any(t['support'] in seen or any(n in seen for n in t.get('blockers',[])) for t in c['targets']):raise ValueError('Support/blocker cannot also be moved')
 inspect_validate(c['inspection'],names)
 return c

def components(count,faces):
 parent=list(range(count))
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 for face in faces:
  for a,b in zip(face,face[1:]+face[:1]):parent[root(a)]=root(b)
 groups={}
 for i in range(count):groups.setdefault(root(i),[]).append(i)
 return sorted(groups.values(),key=lambda v:v[0])

def axial_translation(base,top,hits,embed,max_move):
 if not hits or any(not math.isfinite(v) for v in [base,top,*hits]) or not .004<=top-base<=.04:raise ValueError('Not a supported flat-foot fastener')
 desired=min(hits)-embed;delta=desired-base
 if abs(delta)>max_move:raise ValueError('Seat beyond movement limit')
 remaining=top+delta-max(hits)
 if remaining<.004 or max(hits)-desired>(top-base)*.65:raise ValueError('Support is too uneven; fastener would be buried')
 return delta,{'base_gap_before':[base-max(hits),base-min(hits)],'base_gap_after':[desired-max(hits),desired-min(hits)],'minimum_visible_height':remaining,'sample_count':len(hits)}
