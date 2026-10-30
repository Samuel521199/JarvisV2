"""Reversible, bang-only depth compression on the known character derivative."""


def apply():
    import bpy
    from mathutils import Vector
    scene = bpy.context.scene
    names = sorted(o.name for o in scene.objects if o.name.startswith('bang-refined-'))
    if len(names) != 7 or not bpy.data.objects.get('headend'):
        raise ValueError('Expected seven original character fringe pieces')
    scalp = bpy.data.objects.get('hair-scalp-refined')
    if scalp:
        scalp.hide_render = True
        scalp.hide_set(True)
    for name in names:
        ob = bpy.data.objects[name]
        ob.data = ob.data.copy()
        inv = ob.matrix_world.inverted()
        for v in ob.data.vertices:
            p = ob.matrix_world @ v.co
            # Continuous affine compression toward the forehead on depth only,
            # unlike independent nearest-surface snaps that fold the mesh.
            p.y = -.070 + (p.y + .070) * .5
            v.co = inv @ p
        ob.data.update()
    return {'modified': names, 'depth_factor': .5, 'pivot_y': -.070,
            'scope': 'bang depth trial only', 'back_hair_modified': False,
            'hidden_scalp': bool(scalp), 'automatic_promotion': False}
