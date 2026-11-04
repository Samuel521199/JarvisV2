# SPDX-License-Identifier: GPL-2.0-or-later
"""Asset-bound front-shell reshaping with bounded, flat standard-library arrays."""
from array import array
import hashlib
import math

VERSION='1.0.0'


def ease(value):
    t=max(0.,min(1.,value));return t*t*(3-2*t)


def deform_coordinates(local,matrix):
    """Return float32 candidate, selection and world-space displacement audit.

    The recipe is tied to the inspected affine frame. Unselected coordinates
    retain the original float32 bytes, rather than round-tripping a matrix.
    """
    expected=((1.65,0,0,0),(0,1.65,0,-.12),(0,0,1.65,1.81),(0,0,0,1))
    if len(matrix)!=4 or any(len(row)!=4 for row in matrix) or any(not math.isfinite(matrix[i][j]) or abs(matrix[i][j]-expected[i][j])>.00001 for i in range(4) for j in range(4)):
        raise ValueError('Source assembly frame changed')
    if len(local)%3 or local.typecode!='f':raise ValueError('Flat float32 coordinates required')
    a,b,c=matrix[0][:3];d,e,f=matrix[1][:3];g,h,k=matrix[2][:3]
    det=a*(e*k-f*h)-b*(d*k-f*g)+c*(d*h-e*g)
    inv=((e*k-f*h,c*h-b*k,b*f-c*e),(f*g-d*k,a*k-c*g,c*d-a*f),(d*h-e*g,b*g-a*h,a*e-b*d))
    inv=tuple(tuple(v/det for v in row) for row in inv);shift=tuple(row[3] for row in matrix[:3])
    out=array('f',local);mask=bytearray(len(local)//3);minimum=math.inf;maximum=0.;moved=0
    for i in range(0,len(local),3):
        lx,ly,lz=local[i:i+3]
        if not all(math.isfinite(v) for v in (lx,ly,lz)):raise ValueError('Non-finite source vertex')
        x=a*lx+b*ly+c*lz+shift[0];y=d*lx+e*ly+f*lz+shift[1];z=g*lx+h*ly+k*lz+shift[2]
        weight=ease((.71-abs(x))/.22)*ease((-.30-y)/.45)*ease((z-1.84)/.06)*(1-ease((z-2.37)/.05))
        dy=weight*(-.935-(-.899+.186*(z-1.96)));dz=.035*weight*ease((z-2.21)/.075)
        distance=math.hypot(dy,dz);maximum=max(maximum,distance)
        if distance>1e-7:
            mask[i//3]=1;moved+=1;minimum=min(minimum,distance)
            v=(x-shift[0],y+dy-shift[1],z+dz-shift[2])
            out[i:i+3]=array('f',(sum(row[j]*v[j] for j in range(3)) for row in inv))
    if not moved or maximum>.16:raise ValueError('Unexpected edit extent')
    return out,mask,{'moved_vertices':moved,'maximum_world_displacement':maximum,'minimum_world_displacement':minimum}


def triangle_audit(local,out,mask,indices):
    if len(indices)%3 or len(local)!=len(out) or len(mask)*3!=len(local):raise ValueError('Triangulated source required')
    affected=degenerate=reversed_faces=0
    def normal(points,ids):
        x,y,z=[points[i*3:i*3+3] for i in ids]
        a=[y[i]-x[i] for i in range(3)];b=[z[i]-x[i] for i in range(3)]
        return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    for i in range(0,len(indices),3):
        ids=indices[i:i+3]
        if any(j<0 or j>=len(mask) for j in ids):raise ValueError('Invalid triangle vertex')
        if not any(mask[j] for j in ids):continue
        affected+=1;na=normal(local,ids);nb=normal(out,ids)
        degenerate+=math.hypot(*na)>1e-10 and math.hypot(*nb)<=1e-10
        reversed_faces+=sum(a*b for a,b in zip(na,nb)) < -1e-20
    if degenerate or reversed_faces:raise ValueError('Local deformation degraded triangle orientation/area')
    return {'affected_triangles':affected,'newly_degenerate_triangles':degenerate,'reversed_triangles':reversed_faces}


def reshape_front(obj):
    mesh=obj.data
    if len(mesh.vertices)!=1006488 or len(mesh.polygons)!=1934275:
        raise ValueError('This local recipe requires the inspected Panzer turret source')
    local=array('f',[0])*(len(mesh.vertices)*3);mesh.vertices.foreach_get('co',local)
    out,mask,report=deform_coordinates(local,[list(row) for row in obj.matrix_world])
    indices=array('i',[0])*len(mesh.loops);mesh.loops.foreach_get('vertex_index',indices)
    if len(indices)!=len(mesh.polygons)*3:raise ValueError('Triangulated source required')
    report.update(triangle_audit(local,out,mask,indices))
    unchanged=all(local[i:i+3].tobytes()==out[i:i+3].tobytes() for i in range(0,len(local),3) if not mask[i//3])
    if not unchanged:raise ValueError('Unselected coordinates changed')
    obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='Front shell seating R3')
    key.data.foreach_set('co',out);key.value=1;mesh.update()
    return {**report,'version':VERSION,'vertices':len(mesh.vertices),'triangles':len(mesh.polygons),
        'outside_region_unchanged':unchanged,'original_vertices_sha256':hashlib.sha256(local.tobytes()).hexdigest(),
        'modified_vertices_sha256':hashlib.sha256(out.tobytes()).hexdigest(),'topology_changed':False,'uv_changed':False,
        'basis_preserved_in_native_part':True,'scope':'front shell only; art proportions, not surveyed dimensions or complete collision certification'}
