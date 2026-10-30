"""Bounded first-party implicit character blockout (not animation topology).

The skin is sampled as a smooth union of declared ellipsoids and capsules.
Marching tetrahedra produces one indexed surface without external packages.
"""
import math


def body(p):
    # Nominal metres; X forward, Y lateral, Z up.
    s=p['height']/1.68
    # Proportions are calibrated against the supplied orthographic reference:
    # the joint line is higher than the earlier generic capsule mannequin.
    shapes=[('ell',(-.012,0,.895),(.117*p['depth_scale'],.150*p['hip_scale'],.118)),
            ('ell',(0,0,1.095),(.073*p['depth_scale'],.092*p['waist_scale'],.160)),
            ('ell',(.005,0,1.245),(.102*p['depth_scale'],.143*p['shoulder_scale'],.135)),
            ('ell',(0,0,1.35),(.038,.043,.09)),
            ('ell',(-.006,0,1.49),(.082*p['head_scale'],.073*p['face_width']*p['head_scale'],.111*p['head_scale']))]
    for sign in (-1,1):
        yy=lambda n:sign*n
        shapes.extend([
          ('ell',(.084,yy(.059),1.225),(.048*p['depth_scale'],.051,.057)),
          ('ell',(-.007,yy(.071),.735),(.071*p['leg_scale'],.068*p['leg_scale'],.235)),
          ('ell',(.005,yy(.076),.570),(.044,.044,.067)),
          ('ell',(-.012,yy(.078),.375),(.049*p['leg_scale'],.046*p['leg_scale'],.205)),
          ('ell',(0,yy(.079),.115),(.030,.030,.075)),
          ('ell',(.060,yy(.079),.045),(.110,.045,.036)),
          ('capsule',(0,yy(.144*p['shoulder_scale']),1.320),(0,yy(.238),1.09),.040*p['arm_scale'],.032*p['arm_scale']),
          ('capsule',(0,yy(.238),1.09),(.006,yy(.338),.886),.032*p['arm_scale'],.022*p['arm_scale']),
          ('ell',(.008,yy(.36),.862),(.020,.032,.055))])
    def smoothmin(a,b,k=.027):
        delta=abs(a-b)
        return min(a,b) if delta>=k else min(a,b)-(k-delta)**2/(4*k)
    def distance(x,y,z):
        out=9.
        for shape in shapes:
            _,c,d,*extra=shape
            if shape[0]=='ell':
                rx,ry,rz=d
                value=(math.sqrt(((x-c[0])/rx)**2+((y-c[1])/ry)**2+((z-c[2])/rz)**2)-1)*min(rx,ry,rz)
            else:
                dx,dy,dz=(d[i]-c[i] for i in range(3)); den=dx*dx+dy*dy+dz*dz
                t=max(0.,min(1.,((x-c[0])*dx+(y-c[1])*dy+(z-c[2])*dz)/den))
                radius=extra[0]+t*(extra[1]-extra[0])
                value=math.sqrt((x-c[0]-t*dx)**2+(y-c[1]-t*dy)**2+(z-c[2]-t*dz)**2)-radius
            out=smoothmin(out,value)
        return out
    step=.024
    xs=[-.20+i*step for i in range(20)]; ys=[-.46+i*step for i in range(40)]; zs=[-.015+i*step for i in range(73)]
    ny,nz=len(ys),len(zs)
    def ix(i,j,k):return (i*ny+j)*nz+k
    values=[distance(x,y,z) for x in xs for y in ys for z in zs]
    points=[];faces=[];cache={}
    def position(index):
        i,index=divmod(index,ny*nz);j,k=divmod(index,nz)
        return xs[i],ys[j],zs[k]
    def edge(a,b):
        key=(a,b) if a<b else (b,a)
        if key not in cache:
            u,v=position(a),position(b);da,db=values[a],values[b];t=da/(da-db)
            cache[key]=len(points);points.append([s*(u[q]+t*(v[q]-u[q])) for q in range(3)])
        return cache[key]
    tets=((0,5,1,6),(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6))
    for i in range(len(xs)-1):
      for j in range(ny-1):
       for k in range(nz-1):
        nodes=(ix(i,j,k),ix(i+1,j,k),ix(i+1,j+1,k),ix(i,j+1,k),ix(i,j,k+1),ix(i+1,j,k+1),ix(i+1,j+1,k+1),ix(i,j+1,k+1))
        flags=[values[n]<0 for n in nodes]
        if all(flags) or not any(flags):continue
        for tet in tets:
            inside=[nodes[t] for t in tet if flags[t]];outside=[nodes[t] for t in tet if not flags[t]]
            if not inside or not outside:continue
            if len(inside)==1 or len(outside)==1:
                one,many=(inside[0],outside) if len(inside)==1 else (outside[0],inside)
                faces.append([edge(one,v) for v in many])
            else:
                a,b,c,d=edge(inside[0],outside[0]),edge(inside[0],outside[1]),edge(inside[1],outside[0]),edge(inside[1],outside[1])
                faces.extend([[a,b,c],[b,d,c]])
    if len(points)>20000 or len(faces)>20000:raise ValueError('Character surface exceeds bounded mesh contract')
    return points,faces
