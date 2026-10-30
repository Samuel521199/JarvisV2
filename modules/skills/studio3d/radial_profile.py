"""Bounded exterior plate reprofile, derived from the actual annular source.

Replaces soft periodic bulges by a defined crown and rounded shoulders. This is
an art operation, not a manufacturing or historical reconstruction model.
"""
import bisect
import math


def frame(a):
    u, n = a['radial_u'], a['axis']
    v = [n[1]*u[2]-n[2]*u[1], n[2]*u[0]-n[0]*u[2], n[0]*u[1]-n[1]*u[0]]
    return u, v, n


def smooth(x):
    x = max(0., min(1., x))
    return x*x*(3-2*x)


def crown(angle, a):
    # q=0 is a rib centre, q=1 is the next valley centre.
    q = abs((a['lobes']*(angle-a['phase'])+math.pi) % math.tau-math.pi)/math.pi
    flat, shoulder = a['crown_fraction'], a['shoulder_fraction']
    return 1-smooth((q-flat)/shoulder)


def reprofile(vertices, faces, a):
    """Accept only a closed, regular two-sided annulus; reject other geometry.

    Existing radial rows are retained; added rows sample the original surface.
    The ring minima define the dish, so no asset-specific dish formula is used.
    The centre/hub boundary, outer rim and regions outside the selected annulus
    retain their source positions. No disconnected detail objects are added.
    """
    if len(vertices)>50000 or len(faces)>50000 or len(vertices)<32:
        raise ValueError('Unsupported plate size')
    if any(len(f)!=4 or len(set(f))!=4 or any(type(i) is not int or not 0<=i<len(vertices) for i in f) for f in faces):
        raise ValueError('Regular quad annulus required')
    edges={}
    for face in faces:
        for i,j in zip(face,face[1:]+face[:1]):
            key=tuple(sorted((i,j)));edges[key]=edges.get(key,0)+1
    if any(n!=2 for n in edges.values()) or len(vertices)-len(edges)+len(faces)!=0:
        raise ValueError('Closed manifold annulus required')
    u,v,n=frame(a);groups={-1:{},1:{}}
    for p in vertices:
        p=[x-y for x,y in zip(p,a['center'])]
        x=sum(i*j for i,j in zip(p,u));y=sum(i*j for i,j in zip(p,v));z=sum(i*j for i,j in zip(p,n))
        if abs(z)<1e-5:raise ValueError('Plate faces must be separated')
        r=math.hypot(x,y);key=round(r,5);side=1 if z>0 else -1
        angle=math.atan2(y,x)%math.tau
        if angle>math.tau-1e-5:angle=0.
        groups[side].setdefault(key,[]).append((angle,abs(z),r))
    keys=sorted(groups[1])
    if keys!=sorted(groups[-1]) or not 3<=len(keys)<=100 or not keys[0]<a['inner']<a['outer']<keys[-1]:
        raise ValueError('Action annulus must lie inside both source faces')
    count=len(groups[1][keys[0]])
    if not 24<=count<=512 or count%a['lobes']:
        raise ValueError('Unsupported angular sampling')
    step=math.tau/count
    for side in (-1,1):
        for key in keys:
            row=sorted(groups[side][key]);groups[side][key]=row
            if len(row)!=count:raise ValueError('Uneven source rings')
            # Reject unaligned or irregular rings rather than guessing a surface.
            if any(abs(((t-i*step+math.pi)%math.tau)-math.pi)>1e-4 for i,(t,_,_) in enumerate(row)):
                raise ValueError('Source rings must share the declared angular origin')
    if len(vertices)!=count*len(keys)*2 or len(faces)!=len(vertices):
        raise ValueError('Unexpected annular topology')
    # Superset of original angles and radial rows. Never reduces the high model.
    out_count=count*4
    radii=sorted(set(keys+[round(a['inner']+(a['outer']-a['inner'])*i/32,5) for i in range(33)]))
    def sample(side,r,t):
        i=max(0,min(len(keys)-2,bisect.bisect_right(keys,r)-1));f=(r-keys[i])/(keys[i+1]-keys[i])
        angular=(t%math.tau)/step;j=int(angular)%count;k=(j+1)%count;g=angular-int(angular)
        rows=[groups[side][keys[i]],groups[side][keys[i+1]]]
        z=[row[j][1]*(1-g)+row[k][1]*g for row in rows]
        base=[min(q[1] for q in row) for row in rows]
        return z[0]*(1-f)+z[1]*f,base[0]*(1-f)+base[1]*f
    output=[];max_change=0.;min_separation=math.inf
    for side in (-1,1):
        for r in radii:
            envelope=smooth((r-a['inner'])/a['end_blend'])*smooth((a['outer']-r)/a['end_blend'])
            for i in range(out_count):
                t=i*math.tau/out_count;old,base=sample(side,r,t)
                depth=old*(1-envelope)+(base+a['amplitude']*crown(t,a))*envelope
                max_change=max(max_change,abs(depth-old));min_separation=min(min_separation,depth*2)
                output.append([a['center'][j]+r*math.cos(t)*u[j]+r*math.sin(t)*v[j]+side*depth*n[j] for j in range(3)])
    if max_change>.06 or min_separation<=1e-5:raise ValueError('Reprofile exceeds displacement/separation bounds')
    result=[];stride=len(radii)*out_count
    for side_index,side in enumerate((-1,1)):
        for j in range(len(radii)-1):
            for i in range(out_count):
                b=side_index*stride+j*out_count+i;k=side_index*stride+j*out_count+(i+1)%out_count
                face=[b,b+out_count,k+out_count,k]
                result.append(face if side==1 else face[::-1])
    for j in (0,len(radii)-1):
        for i in range(out_count):
            b=j*out_count+i;k=j*out_count+(i+1)%out_count;face=[b,k,k+stride,b+stride]
            result.append(face[::-1] if j==0 else face)
    return output,result,{'source_vertices':len(vertices),'result_vertices':len(output),'max_axial_change':max_change,
                          'minimum_face_separation_bound':min_separation,'source_angular_samples':count,'output_angular_samples':out_count,
                          'scope':'Exterior radial profile only; fastener contact and reference fidelity require separate checks'}
