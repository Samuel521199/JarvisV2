"""Source-measured rotational exterior profiles, not functional mechanisms."""
import math
from modules.skills.studio3d.assembly_geometry import add,sub,mul,cross,norm
from modules.skills.studio3d.render_inspection import validate as inspect_validate
SCHEMA='jarvis.studio3d.trail-band.v1'
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def mean(ps):return [sum(p[i] for p in ps)/len(ps) for i in range(3)]
def frame(axis):
    a=norm(axis);u=norm(cross(a,[0,0,1]));return a,u,cross(a,u)
def fit(points,axis,kind):
    if kind not in ('bead','collar') or len(points)!=(320 if kind=='bead' else 130):raise ValueError('Original measured component required')
    if any(len(p)!=3 or any(not math.isfinite(v) for v in p) for p in points):raise ValueError('Finite geometry required')
    center=mean(points);a,u,v=frame(axis);rows=[]
    for p in points:
        q=sub(p,center);h=dot(q,a);x=dot(q,u);y=dot(q,v);rows.append((h,math.hypot(x,y),math.atan2(y,x)))
    if kind=='bead':
        radius=sum(r for h,r,t in rows)/len(rows);slots={}
        for h,r,t in rows:
            k=round(t*16/math.tau);err=abs(t*16/math.tau-k)
            if err>2e-5:raise ValueError('Nonuniform original bead angular lattice')
            slots.setdefault(k%16,[]).append((h,r))
        if set(slots)!=set(range(16)) or any(len(x)!=20 for x in slots.values()):raise ValueError('Original rounded diamond profile required')
        ordered=[sorted(slots[i],key=lambda q:math.atan2(q[0],q[1]-radius)) for i in range(16)]
        # The negative pi seam is noisy in stored float geometry; sort with a
        # stable quarter-turn offset so no profile vertex sits on the seam.
        ordered=[sorted(slots[i],key=lambda q:(math.atan2(q[0],q[1]-radius)+.31)%math.tau) for i in range(16)]
        profile=[[sum(row[j][k] for row in ordered)/16 for k in (0,1)] for j in range(20)]
        error=max(abs(row[j][k]-profile[j][k]) for row in ordered for j in range(20) for k in (0,1))
        if not .085<radius<.095 or error>2e-6 or max(abs(h) for h,r in profile)>.004:raise ValueError('Unsupported measured bead profile')
    else:
        ring=[q for q in rows if q[1]>.02];caps=[q for q in rows if q[1]<=.02]
        if len(ring)!=128 or len(caps)!=2 or max(q[1] for q in caps)>2e-6:raise ValueError('Four circular sleeve rows required')
        ring.sort();groups=[ring[i:i+32] for i in range(0,128,32)];profile=[[sum(q[k] for q in g)/32 for k in (0,1)] for g in groups];error=0
        for g,p in zip(groups,profile):
            error=max(error,max(abs(q[k]-p[k]) for q in g for k in (0,1)));slots=[]
            for h,r,t in g:
                k=round(t*32/math.tau)
                if abs(t*32/math.tau-k)>2e-5:raise ValueError('Nonuniform sleeve lattice')
                slots.append(k%32)
            if len(set(slots))!=32:raise ValueError('Incomplete sleeve ring')
        if error>2e-6 or any(not .08<r<.095 for h,r in profile) or abs(profile[0][0]+.018)>2e-6 or abs(profile[-1][0]-.018)>2e-6:raise ValueError('Unsupported original sleeve profile')
    return {'center':center,'axis':a,'profile':profile,'kind':kind,'fit_error':error,'source_vertices':len(points)}

def geometry(p,segments):
    if type(segments)!=int or segments not in (64,96,128):raise ValueError('Bounded circumference samples required')
    a,u,v=frame(p['axis']);profile=p['profile'];vs=[];fs=[];uv=[];smooth=[];count=len(profile)
    for h,r in profile:
        for i in range(segments):
            t=math.tau*i/segments;vs.append(add(p['center'],add(mul(a,h),mul(add(mul(u,math.cos(t)),mul(v,math.sin(t))),r))))
    bands=count if p['kind']=='bead' else count-1
    for j in range(bands):
        nxt=(j+1)%count
        for i in range(segments):
            k=(i+1)%segments;fs.append([j*segments+i,j*segments+k,nxt*segments+k,nxt*segments+i]);uv.append([[i/segments,j/count],[(i+1)/segments,j/count],[(i+1)/segments,(j+1)/count],[i/segments,(j+1)/count]]);smooth.append(True)
    if p['kind']=='collar':
        for j in (0,count-1):
            center=len(vs);vs.append(add(p['center'],mul(a,profile[j][0])))
            for i in range(segments):
                k=(i+1)%segments;f=[center,j*segments+i,j*segments+k];tex=[[.5,.5],[.5+.45*math.cos(math.tau*i/segments),.5+.45*math.sin(math.tau*i/segments)],[.5+.45*math.cos(math.tau*k/segments),.5+.45*math.sin(math.tau*k/segments)]]
                if j==0:f.reverse();tex.reverse()
                fs.append(f);uv.append(tex);smooth.append(False)
    return vs,fs,uv,smooth

def validate(c,names):
    if not isinstance(c,dict) or set(c)!={'schema','author','evidence','source_sha256','targets','segments','inspection'} or c['schema']!=SCHEMA:raise ValueError('Invalid measured band contract')
    sha=lambda x:isinstance(x,str) and len(x)==64 and all(a in '0123456789abcdef' for a in x)
    if c['author'] not in ('Codex','Jarvis') or not isinstance(c['evidence'],str) or not 1<=len(c['evidence'])<=1600 or not sha(c['source_sha256']):raise ValueError('Source/evidence required')
    if type(c['segments'])!=int or c['segments'] not in (64,96,128):raise ValueError('Bounded circumference samples required')
    if not isinstance(c['targets'],list) or len(c['targets'])!=2:raise ValueError('Both trail sides required')
    seen=set()
    for t in c['targets']:
        if set(t)!={'side','strap_digest','collar_digest','tube_digest','bead_components'} or t['side'] not in ('left','right') or t['side'] in seen:raise ValueError('Invalid side binding')
        seen.add(t['side'])
        if any(not sha(t[k]) for k in ('strap_digest','collar_digest','tube_digest')) or any(n+'-'+t['side'] not in names for n in ('trail-strap-details','trail-collars','trail-tube')):raise ValueError('Bound components required')
        if t['bead_components']!=[list(range(i,i+320)) for i in (0,320,1096,1416,2192,2512)]:raise ValueError('Original six edge components required')
    inspect_validate(c['inspection'],names)
    if c['inspection'].get('focus_region') or c['inspection']['resolution']!=[960,640] or c['inspection']['samples']!=12 or len(c['inspection']['views'])!=2:raise ValueError('Fixed explicit band frame required')
    return c
