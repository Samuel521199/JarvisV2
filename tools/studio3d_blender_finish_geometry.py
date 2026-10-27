"""Conservative native hard-surface finish helpers; no remeshing or decimation."""
import math
from collections import defaultdict
import bmesh
from mathutils import Vector


def finish_object(obj, maximum_tiny_loop_diameter=.001, sharp_angle_degrees=50):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    pending = {e for e in bm.edges if e.is_boundary}
    capped = []
    while pending:
        first = pending.pop()
        group = {first}
        queue = [first]
        while queue:
            edge = queue.pop()
            for vertex in edge.verts:
                for other in vertex.link_edges:
                    if other in pending:
                        pending.remove(other)
                        group.add(other)
                        queue.append(other)
        vertices = {v for e in group for v in e.verts}
        closed = all(sum(e in group for e in v.link_edges) == 2 for v in vertices)
        if not closed or len(vertices) < 8:
            continue
        low = Vector(tuple(min(v.co[k] for v in vertices) for k in range(3)))
        high = Vector(tuple(max(v.co[k] for v in vertices) for k in range(3)))
        if (high-low).length > maximum_tiny_loop_diameter:
            continue
        filled = bmesh.ops.holes_fill(bm, edges=list(group), sides=0)['faces']
        for face in filled:
            face.smooth = False
        capped.append({'diameter_bound': (high-low).length, 'edges': len(group),
                       'new_faces': len(filled)})
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    sharp = 0
    for edge in bm.edges:
        if edge.is_manifold and edge.calc_face_angle() > math.radians(sharp_angle_degrees):
            edge.smooth = False
            sharp += 1
    # Connected planar fan faces need flat normals; a rounded rim keeps its
    # smooth faces. Grouping by plane avoids flattening the curved cylinder.
    groups = defaultdict(list)
    for face in bm.faces:
        normal = face.normal
        center = face.calc_center_median()
        groups[tuple(round(x, 5) for x in normal)+(round(normal.dot(center), 5),)].append(face)
    flat = 0
    for faces in groups.values():
        if len(faces) >= 8 and sum(f.calc_area() for f in faces) > .00005:
            for face in faces:
                face.smooth = False
                flat += 1
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return {'object': obj.name, 'tiny_loops_capped': capped,
            'sharp_edges': sharp, 'planar_faces_flat': flat,
            'no_decimation': True}
