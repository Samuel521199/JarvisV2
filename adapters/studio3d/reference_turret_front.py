# SPDX-License-Identifier: GPL-2.0-or-later
"""Asset-bound Panzer reference front-shell reshaping, not a general CAD operation."""
import hashlib
import numpy as np

VERSION='1.0.0'


def reshape_front(obj):
    mesh=obj.data
    if len(mesh.vertices)!=1006488 or len(mesh.polygons)!=1934275:
        raise ValueError('This local recipe requires the inspected Panzer turret source')
    matrix=np.array(obj.matrix_world,dtype=np.float64)
    expected=np.diag([1.65,1.65,1.65,1.]);expected[:3,3]=[0,-.12,1.81]
    if np.max(np.abs(matrix-expected))>.00001:raise ValueError('Source assembly frame changed')
    local=np.empty((len(mesh.vertices),3),dtype=np.float32);mesh.vertices.foreach_get('co',local.ravel())
    world=local@matrix[:3,:3].T+matrix[:3,3]
    x,y,z=world.T
    def ease(v):
        t=np.clip(v,0,1);return t*t*(3-2*t)
    lateral=ease((.71-np.abs(x))/.22)
    depth=ease((-.30-y)/.45)
    height=ease((z-1.84)/.06)*(1-ease((z-2.37)/.05))
    weight=lateral*depth*height
    original_face=-.899+.186*(z-1.96)
    changed=world.copy()
    changed[:,1]+=weight*(-.935-original_face)
    changed[:,2]+=.035*weight*ease((z-2.21)/.075)
    delta=changed-world;mask=np.linalg.norm(delta,axis=1)>1e-7
    if not np.any(mask) or np.max(np.linalg.norm(delta,axis=1))>.16:raise ValueError('Unexpected edit extent')
    # Exact identity outside the explicit region; retain every face and UV loop.
    out=local.copy();out[mask]=((changed[mask]-matrix[:3,3])@np.linalg.inv(matrix[:3,:3]).T).astype(np.float32)
    indices=np.empty(len(mesh.loops),dtype=np.int32);mesh.loops.foreach_get('vertex_index',indices)
    if len(indices)!=len(mesh.polygons)*3:raise ValueError('Triangulated source required')
    faces=indices.reshape(-1,3);affected=faces[np.any(mask[faces],axis=1)]
    a,b=local[affected],out[affected]
    na=np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]);nb=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0])
    old_area=np.linalg.norm(na,axis=1);new_area=np.linalg.norm(nb,axis=1)
    newly_degenerate=int(np.sum((old_area>1e-10)&(new_area<=1e-10)))
    reversed_faces=int(np.sum(np.einsum('ij,ij->i',na,nb)<-1e-20))
    if newly_degenerate or reversed_faces:raise ValueError('Local deformation degraded triangle orientation/area')
    obj.shape_key_add(name='Basis')
    key=obj.shape_key_add(name='Front shell seating R3');key.data.foreach_set('co',out.ravel());key.value=1
    mesh.update()
    return {'version':VERSION,'vertices':len(mesh.vertices),'triangles':len(mesh.polygons),'moved_vertices':int(mask.sum()),'affected_triangles':len(affected),'newly_degenerate_triangles':newly_degenerate,'reversed_triangles':reversed_faces,'outside_region_unchanged':bool(np.array_equal(local[~mask],out[~mask])),'maximum_world_displacement':float(np.max(np.linalg.norm(delta,axis=1))),'minimum_world_displacement':float(np.min(np.linalg.norm(delta[mask],axis=1))),'original_vertices_sha256':hashlib.sha256(local.tobytes()).hexdigest(),'modified_vertices_sha256':hashlib.sha256(out.tobytes()).hexdigest(),'topology_changed':False,'uv_changed':False,'basis_preserved_in_native_part':True,'scope':'front shell only; art proportions, not surveyed dimensions or complete collision certification'}
