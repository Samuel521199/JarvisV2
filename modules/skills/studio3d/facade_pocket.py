"""A bounded blind cosmetic pocket behind an existing game-asset facade."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.facade-pocket.v1'
NAMES=('rear-cover-body','shaped-rear-cover','breech-recess')

def validate(c,names):
 if isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.facade-slot-repair.v1':
  if set(c)!={'schema','author','evidence','source_digest','inspection'} or c['author']!='Codex' or 'rear-cover-body' not in names:raise ValueError('Bound author slot repair required')
  d=c['source_digest']
  if not isinstance(d,str) or len(d)!=64 or any(x not in '0123456789abcdef' for x in d):raise ValueError('Slot repair source digest')
  if not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Slot failure evidence required')
  inspect_validate(c['inspection'],names);return c
 v2=isinstance(c,dict) and c.get('schema')=='jarvis.studio3d.facade-pocket.v2'
 if not isinstance(c,dict) or set(c)!=({'schema','author','evidence','bindings','depth','inspection'}|({'mirror_facade','remove_front_trim'} if v2 else set())) or c['schema'] not in (SCHEMA,'jarvis.studio3d.facade-pocket.v2'):raise ValueError('Unexpected facade pocket fields')
 if v2 and (c['mirror_facade'] is not True or c['remove_front_trim'] is not True):raise ValueError('Reference-directed facade and trim correction required')
 if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Author and visible reference required')
 if type(c['depth']) not in (int,float) or not math.isfinite(c['depth']) or not .025<=c['depth']<=.045:raise ValueError('Blind cosmetic depth envelope')
 required=set(NAMES)|({'rear-seated-cosmetic-fittings','fasteners-breech'} if v2 else set())
 if not isinstance(c['bindings'],dict) or set(c['bindings'])!=required or any(n not in names for n in required):raise ValueError('Bound facade objects required')
 for d in c['bindings'].values():
  if not isinstance(d,str) or len(d)!=64 or any(x not in '0123456789abcdef' for x in d):raise ValueError('Source digest required')
 inspect_validate(c['inspection'],names);return c

def placement(rear,depth,disc_front,disc_back,body_front):
 if not .025<=depth<=.045 or not .009<=disc_back-disc_front<=.013:raise ValueError('Unexpected cosmetic surface depth')
 floor=rear+depth
 if body_front-floor<.2:raise ValueError('Blind pocket must retain solid back wall')
 delta=floor+.001-disc_back
 if not .08<=delta<=.12 or disc_front+delta<=rear+.01:raise ValueError('Existing badge must sit behind the rear face')
 return floor,delta
