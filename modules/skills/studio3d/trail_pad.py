"""Reference-visible trail pad exterior; bounded art shapes, no mechanism."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.trail-pad.v1'

def footprint(length,width,radius,nx=16,ny=12):
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (length,width,radius)):raise ValueError('Finite footprint required')
    if not .035<=length<=.34 or not .04<=width<=.095 or not .005<=radius<=min(width,length)/3:raise ValueError('Pad envelope')
    if type(nx)!=int or type(ny)!=int or not 4<=nx<=20 or not 4<=ny<=16:raise ValueError('Sampling budget')
    points=[];faces=[]
    for j in range(ny+1):
        t=width*(j/ny-.5);q=max(0,abs(t)-(width/2-radius));limit=length/2-radius+math.sqrt(max(0,radius*radius-q*q))
        points.extend([[limit*(2*i/nx-1),t] for i in range(nx+1)])
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i;faces.append([a,a+1,a+nx+2,a+nx+1])
    boundary=list(range(nx+1))+[j*(nx+1)+nx for j in range(1,ny+1)]+[ny*(nx+1)+i for i in range(nx-1,-1,-1)]+[j*(nx+1) for j in range(ny-1,0,-1)]
    return points,faces,boundary

def validate(c,names):
    if not isinstance(c,dict) or set(c)!={'schema','author','evidence','source_sha256','targets','pad_length','inspection'} or c['schema']!=SCHEMA:raise ValueError('Unexpected trail pad contract')
    if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Exterior evidence required')
    sha=lambda x:isinstance(x,str) and len(x)==64 and all(v in '0123456789abcdef' for v in x)
    if not sha(c['source_sha256']):raise ValueError('Full source binding required')
    if type(c['pad_length']) not in (int,float) or not math.isfinite(c['pad_length']) or not .26<=c['pad_length']<=.32:raise ValueError('Pad length envelope')
    if not isinstance(c['targets'],list) or len(c['targets'])!=2:raise ValueError('Two original strap objects required')
    seen=set()
    for t in c['targets']:
        if not isinstance(t,dict) or set(t)!={'object','dependency_digest','support','support_dependency_digest','grips'}:raise ValueError('Complete dependency binding required')
        n=t['object'];side=n.removeprefix('trail-strap-details-')
        if side not in ('left','right') or n in seen or n not in names or t['support']!='trail-tube-'+side or t['support'] not in names:raise ValueError('Original target/support inventory required')
        seen.add(n)
        if any(not sha(t[k]) for k in ('dependency_digest','support_dependency_digest')):raise ValueError('Dependency digest required')
        if not isinstance(t['grips'],dict) or set(t['grips'])!={'trail-handle-'+side+'-'+str(i) for i in range(3)} or any(n not in names or not sha(v) for n,v in t['grips'].items()):raise ValueError('Three current grip bindings required')
    inspect_validate(c['inspection'],names)
    if c['inspection'].get('focus_region'):raise ValueError('Explicit whole-pad bounds required')
    if c['inspection']['resolution']!=[960,640] or c['inspection']['samples']!=12 or len(c['inspection']['views'])!=2:raise ValueError('Fixed inspection budget')
    return c
