"""Bound planar U-grip exterior profiles; no mechanism reconstruction."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.curve-grip.v1'

def grip_path(start,end,crown,radius):
    if type(radius) not in (int,float) or not math.isfinite(radius) or not .014<=radius<=.022:raise ValueError('Grip corner envelope')
    if any(len(p)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in p) for p in (start,end)):raise ValueError('Finite endpoints required')
    if abs(start[1]-end[1])>1e-6 or not .08<=abs(end[0]-start[0])<=.12:raise ValueError('Original planar grip span required')
    if not math.isfinite(crown) or not .07<=crown-max(start[2],end[2])<=.13:raise ValueError('Grip height envelope')
    sign=1 if end[0]>start[0] else -1;y=start[1];r=radius;k=.5522847498307936
    points=[list(start),[start[0],y,crown-r],[start[0]+sign*r,y,crown],[end[0]-sign*r,y,crown],[end[0],y,crown-r],list(end)]
    left=[p.copy() for p in points];right=[p.copy() for p in points]
    # Exact straight segments and the usual cubic quarter-circle approximation.
    for a,b in ((0,1),(2,3),(4,5)):
        step=[(points[b][j]-points[a][j])/3 for j in range(3)]
        right[a]=[points[a][j]+step[j] for j in range(3)];left[b]=[points[b][j]-step[j] for j in range(3)]
    right[1][2]+=k*r;left[2][0]-=sign*k*r;right[3][0]+=sign*k*r;left[4][2]+=k*r
    left[0]=[2*points[0][j]-right[0][j] for j in range(3)];right[5]=[2*points[5][j]-left[5][j] for j in range(3)]
    return [{'co':p,'left':a,'right':b} for p,a,b in zip(points,left,right)]

def validate(c,names):
    if not isinstance(c,dict) or set(c)!={'schema','author','evidence','source_sha256','targets','corner_radius','inspection'} or c['schema']!=SCHEMA:raise ValueError('Unexpected grip contract')
    if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Author/exterior evidence required')
    def sha(x):return isinstance(x,str) and len(x)==64 and all(v in '0123456789abcdef' for v in x)
    if not sha(c['source_sha256']):raise ValueError('Full source binding required')
    allowed={'trail-handle-'+s+'-'+str(i) for s in ('left','right') for i in range(3)}
    if not isinstance(c['targets'],list) or len(c['targets'])!=6:raise ValueError('Six existing grips required')
    seen=set()
    for t in c['targets']:
        if not isinstance(t,dict) or set(t)!={'object','support','base_digest','dependency_digest','support_dependency_digest'}:raise ValueError('Grip/support binding required')
        n=t['object']
        if n not in allowed or n in seen or n not in names:raise ValueError('Original grip inventory required')
        seen.add(n);support='trail-tube-'+n.split('-')[2]
        if t['support']!=support or support not in names:raise ValueError('Original immutable tube support required')
        if any(not sha(t[k]) for k in ('base_digest','dependency_digest','support_dependency_digest')):raise ValueError('Bound dependencies required')
    grip_path([0,0,0],[.1,0,0],.1,c['corner_radius']);inspect_validate(c['inspection'],names)
    if c['inspection']['resolution']!=[960,640] or c['inspection']['samples']!=12 or len(c['inspection']['views'])!=2:raise ValueError('Fixed inspection budget')
    return c
