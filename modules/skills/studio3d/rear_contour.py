"""One source-bound cosmetic C silhouette, with immutable surrounding parts."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate

SCHEMA='jarvis.studio3d.rear-contour.v1'
NAMES={'shaped-rear-cover','rear-cover-body','breech-recess','fasteners-breech','rear-seated-cosmetic-fittings'}

def outline(clearance,cy,cz,disc_radius):
    if type(clearance) not in (int,float) or not math.isfinite(clearance) or not .008<=clearance<=.010:raise ValueError('Bounded exterior clearance required')
    if not all(math.isfinite(x) for x in (cy,cz,disc_radius)) or abs(cy)>1e-6 or abs(cz-1.135)>1e-6 or abs(disc_radius-.061)>1e-6:raise ValueError('Original decorative circle binding changed')
    r=disc_radius+clearance
    return [[.125,.99],[-.125,.99],[-.125,cz-r]]+[[cy+r*math.cos(-math.pi/2+i*math.pi/32),cz+r*math.sin(-math.pi/2+i*math.pi/32)] for i in range(33)]+[[-.125,cz+r],[-.125,1.31],[.125,1.31]]

def validate(c,names):
    fields={'schema','author','evidence','source_sha256','dependencies','clearance','inspection'}
    if not isinstance(c,dict) or set(c)!=fields or c['schema']!=SCHEMA:raise ValueError('Unexpected exterior contour contract')
    sha=lambda s:isinstance(s,str) and len(s)==64 and all(v in '0123456789abcdef' for v in s)
    if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Explicit actor and observed evidence required')
    if not sha(c['source_sha256']) or not isinstance(c['dependencies'],dict) or set(c['dependencies'])!=NAMES or not all(sha(v) for v in c['dependencies'].values()):raise ValueError('Full source and local dependency binding required')
    if not NAMES<=set(names):raise ValueError('Original semantic inventory required')
    outline(c['clearance'],0,1.135,.061);inspect_validate(c['inspection'],names)
    i=c['inspection']
    if i.get('focus_region')!='rear-contour' or i['regions']!={'rear-contour':['shaped-rear-cover','rear-cover-body','breech-recess']} or i['resolution']!=[960,640] or i['samples']!=12 or len(i['views'])!=2 or i.get('bounds')!=[[-1.3,-.55,.6],[-.2,.55,1.6]]:raise ValueError('Fixed paired contour inspection required')
    return c
