"""Bounded visible hanging-tab silhouette; no mechanical mechanism."""
import math
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.trail-tab.v1'

def shape(extension):
    if type(extension) not in (int,float) or not math.isfinite(extension) or not .125<=extension<=.145:raise ValueError('Tab extension envelope')
    center=-extension+.026
    outer=[[-.018,-.012],[.018,-.012],[.020,-.014],[.020,-.030],[.014,-extension+.014]]
    outer.extend([[.014*math.cos(-math.pi*i/20),-extension+.014+.014*math.sin(-math.pi*i/20)] for i in range(1,21)])
    outer.extend([[-.020,-.030],[-.020,-.014]])
    inner=[]
    for cy,a in ((center+.008,0),(center-.008,math.pi)):
        inner.extend([[.0055*math.cos(a+math.pi*i/16),cy+.0055*math.sin(a+math.pi*i/16)] for i in range(17)])
    # Shared angular samples form a closed annular face with the visible slot.
    angles=sorted(set(round(math.atan2(y-center,x),10) for x,y in outer+inner))
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    def hit(poly,angle):
        d=[math.cos(angle),math.sin(angle)];hits=[]
        for p,q in zip(poly,poly[1:]+poly[:1]):
            p=[p[0],p[1]-center];e=[q[0]-p[0],q[1]-center-p[1]];den=cross(d,e)
            if abs(den)<1e-12:continue
            t=cross(p,e)/den;u=cross(p,d)/den
            if t>0 and -1e-7<=u<=1+1e-7:hits.append(t)
        if not hits:raise ValueError('Non-star-shaped tab contour')
        t=min(hits);return [d[0]*t,center+d[1]*t]
    o=[hit(outer,a) for a in angles];h=[hit(inner,a) for a in angles];n=len(o)
    points=[[x,y,z] for z in (-.006,.006) for ring in (o,h) for x,y in ring];faces=[]
    for i in range(n):
        j=(i+1)%n
        faces.extend([[i,j,n+j,n+i],[2*n+i,3*n+i,3*n+j,2*n+j],[i,2*n+i,2*n+j,j],[n+i,n+j,3*n+j,3*n+i]])
    return points,faces

def validate(c,names):
    if not isinstance(c,dict) or set(c)!={'schema','author','evidence','source_sha256','targets','extension','inspection'} or c['schema']!=SCHEMA:raise ValueError('Unexpected tab contract')
    if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600:raise ValueError('Visible evidence required')
    sha=lambda x:isinstance(x,str) and len(x)==64 and all(v in '0123456789abcdef' for v in x)
    if not sha(c['source_sha256']):raise ValueError('Full source binding required')
    shape(c['extension'])
    if not isinstance(c['targets'],list) or len(c['targets'])!=2:raise ValueError('Two original strap objects required')
    seen=set()
    for t in c['targets']:
        if not isinstance(t,dict) or set(t)!={'object','dependency_digest','support','support_dependency_digest','collar_dependency_digest','components'}:raise ValueError('Complete source/component binding required')
        n=t['object'];side=n.removeprefix('trail-strap-details-')
        if side not in ('left','right') or n in seen or n not in names or t['support']!='trail-tube-'+side or t['support'] not in names or 'trail-collars-'+side not in names:raise ValueError('Target/support inventory')
        seen.add(n)
        if any(not sha(t[k]) for k in ('dependency_digest','support_dependency_digest','collar_dependency_digest')):raise ValueError('Dependency digest required')
        starts=(792,1888,2984) if side=='left' else (944,2040,3136)
        if t['components']!=[list(range(i,i+152)) for i in starts]:raise ValueError('Original outer side components required')
    inspect_validate(c['inspection'],names)
    if c['inspection'].get('focus_region') or c['inspection']['resolution']!=[960,640] or c['inspection']['samples']!=12 or len(c['inspection']['views'])!=2:raise ValueError('Fixed explicit tab frame required')
    return c
