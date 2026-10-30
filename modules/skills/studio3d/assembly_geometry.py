"""Original reusable exterior-art mesh builders; returns bounded scene DATA only.

These routines express surfaces, not mechanical engineering or Blender code.
All generated data still passes the existing Studio3D contract and worker.
"""
import math


def add(a, b): return [x+y for x, y in zip(a, b)]
def mul(a, s): return [x*s for x in a]
def sub(a, b): return [x-y for x, y in zip(a, b)]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def norm(a):
    d=math.sqrt(sum(x*x for x in a))
    if d<1e-10: raise ValueError('Degenerate direction')
    return mul(a, 1/d)


def triangulate(outline):
    """Ear clipping preserves a concave outline instead of filling its notch."""
    def turn(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(outline,outline[1:]+outline[:1]))
    if abs(area)<1e-12:raise ValueError('Degenerate outline')
    sign=1 if area>0 else -1;indices=list(range(len(outline)));faces=[]
    while len(indices)>3:
        for j,i in enumerate(indices):
            prev=indices[j-1];nxt=indices[(j+1)%len(indices)];a,b,c=[outline[k] for k in (prev,i,nxt)]
            if sign*turn(a,b,c)<=1e-12:continue
            if any(all(sign*turn(u,v,outline[k])>=-1e-12 for u,v in ((a,b),(b,c),(c,a))) for k in indices if k not in (prev,i,nxt)):continue
            faces.append([prev,i,nxt]);indices.pop(j);break
        else:raise ValueError('Outline is self-intersecting or numerically degenerate')
    faces.append(indices);return faces


class Mesh:
    def __init__(self): self.vertices=[]; self.faces=[]

    def append(self, vertices, faces):
        offset=len(self.vertices)
        self.vertices.extend(vertices)
        self.faces.extend([[offset+i for i in face] for face in faces])

    def tube(self, a, b, radius, segments=32, end_radius=None, rounded=True):
        axis=norm(sub(b,a));u=norm(cross(axis,[0,0,1] if abs(axis[2])<.9 else [0,1,0]));v=cross(axis,u)
        verts=[];faces=[]
        # Small support rings make the silhouette rounded without a global subdivide.
        profile=[(0,.92),(.05,1),(.95,1),(1,.92)] if rounded else [(0,1),(1,1)]
        for t,shrink in profile:
            center=add(a,mul(sub(b,a),t));r=radius*(1-t)+(end_radius or radius)*t
            for i in range(segments):
                angle=i*math.tau/segments
                verts.append(add(center,mul(add(mul(u,math.cos(angle)),mul(v,math.sin(angle))),r*shrink)))
        for j in range(len(profile)-1):
            for i in range(segments):
                k=(i+1)%segments;faces.append([j*segments+i,j*segments+k,(j+1)*segments+k,(j+1)*segments+i])
        for j,reverse in [(0,True),(len(profile)-1,False)]:
            center=len(verts);verts.append([sum(verts[j*segments+i][k] for i in range(segments))/segments for k in range(3)])
            for i in range(segments):
                f=[center,j*segments+i,j*segments+(i+1)%segments];faces.append(f[::-1] if reverse else f)
        self.append(verts,faces)

    def box(self, center, size):
        v=[[center[0]+x*size[0]/2,center[1]+y*size[1]/2,center[2]+z*size[2]/2] for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
        self.append(v,[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]])

    def extrude(self, outline, axis, start, end):
        """Extrude an ordered planar art outline; includes real side walls."""
        if axis not in (0,1,2) or len(outline)<3 or end<=start:raise ValueError('Invalid extrusion')
        outline=list(outline)
        area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(outline,outline[1:]+outline[:1]))
        if area*(-1 if axis==1 else 1)<0:outline.reverse()
        axes=[i for i in range(3) if i!=axis];vertices=[]
        for depth in (start,end):
            for a,b in outline:
                v=[0.,0.,0.];v[axis]=depth;v[axes[0]]=a;v[axes[1]]=b;vertices.append(v)
        n=len(outline);triangles=triangulate(outline)
        faces=[f[::-1] for f in triangles]+[[i+n for i in f] for f in triangles]
        faces.extend([[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)])
        self.append(vertices,faces)

    def ring(self, center, axis, radius, tube, segments=64, sides=8):
        axis=norm(axis);u=norm(cross(axis,[0,0,1] if abs(axis[2])<.9 else [0,1,0]));v=cross(axis,u)
        verts=[];faces=[]
        for i in range(segments):
            t=i*math.tau/segments;rad=add(mul(u,math.cos(t)),mul(v,math.sin(t)))
            for j in range(sides):
                q=j*math.tau/sides
                verts.append(add(center,add(mul(rad,radius+tube*math.cos(q)),mul(axis,tube*math.sin(q)))))
        for i in range(segments):
            for j in range(sides):faces.append([i*sides+j,((i+1)%segments)*sides+j,((i+1)%segments)*sides+(j+1)%sides,i*sides+(j+1)%sides])
        self.append(verts,faces)

    def object(self, name, material, *, bevel=0, smooth=True):
        return {'id':name,'kind':'mesh','material':material,'params':{'vertices':self.vertices,'faces':self.faces},'shading':'smooth' if smooth else 'flat',
                'modifiers':{'bevel':bevel,'bevel_segments':4} if bevel else {}}


def panel(name, material, grid, thickness=.018):
    """Thin curved plate from rectangular sampled surface; real edge thickness."""
    rows=len(grid);cols=len(grid[0]);v=[p for row in grid for p in row];f=[]
    if any(len(r)!=cols for r in grid): raise ValueError('Panel row mismatch')
    for i in range(rows-1):
        for j in range(cols-1):
            a=i*cols+j;f.append([a,a+1,a+cols+1,a+cols])
    return {'id':name,'kind':'mesh','material':material,'params':{'vertices':v,'faces':f},'modifiers':{'thickness':thickness,'bevel':.002,'bevel_segments':4},'shading':'smooth'}
