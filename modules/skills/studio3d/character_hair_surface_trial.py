"""Disposable hair trial fitted to the original headend surface via ray casts."""
import math


def apply():
    import bpy
    from mathutils import Vector
    scene = bpy.context.scene
    source = bpy.data.objects.get('headend')
    mat = bpy.data.materials.get('character-hair-procedural')
    if not source or not mat or not bpy.data.objects.get('Body'):
        raise ValueError('Unexpected character FBX derivative')
    if bpy.data.objects.get('hair-surface-trial-00'):
        raise ValueError('Already applied')
    deps = bpy.context.evaluated_depsgraph_get()
    surface = source.evaluated_get(deps)
    inverse = surface.matrix_world.inverted()
    hidden = []
    for ob in scene.objects:
        if ob.name.startswith('back-hair-refined-'):
            ob.hide_render = True; ob.hide_set(True); hidden.append(ob.name)

    def radius(angle, z):
        direction = Vector((math.cos(angle), math.sin(angle), 0.0))
        origin = Vector((0, .018, z)) + direction * .5
        hit, co, _, _ = surface.ray_cast(inverse @ origin, inverse.to_3x3() @ -direction)
        if hit:
            point = surface.matrix_world @ co
            return (Vector((point.x, point.y - .018, 0))).length
        # At ear gaps sample just behind the ear, not through the skin.
        return .090 if z < 1.52 else .078

    objects = []
    count, rows, columns = 15, 44, 9
    for k in range(count):
        mid = (k + .5) * math.pi / count
        phase = math.sin(k * 2.37)
        top = 1.575 + .008 * math.sin(k * 1.78)
        bottom = 1.342 + .010 * math.sin(k * 1.67) + .006 * math.sin(k * 3.93)
        vertices, faces = [], []
        for j in range(rows):
            t = j / (rows-1)
            z = top * (1-t) + bottom * t
            root = min(1.0, t * 4)
            tip = max(0.0, (t-.84)/.16)
            half_width = (math.pi/count) * (.7 * (1-.83*tip)) * max(.35, root)
            sweep = (.042 * phase * t*t) + .013 * math.sin(5*t+k)
            for i in range(columns):
                u = 2*i/(columns-1)-1
                angle = min(math.pi-.005, max(.005, mid + u*half_width+sweep))
                sample_z = max(1.465, z)
                r = radius(angle, sample_z)
                if z < 1.465:
                    # Keep the curtain clear of the neck, then curl individual
                    # ends subtly in different directions rather than uniform spikes.
                    r *= (1 - .08 * min(1.0, (1.465-z)/.13))
                    r += .004 * phase * tip
                r += -.004 + root * (.0054 + .0005*(1-u*u))
                end_shape = tip * (.0032*(1-u*u) + .0012*phase*u)
                vertices.append((r*math.cos(angle), .018+r*math.sin(angle), z-end_shape))
        for j in range(rows-1):
            for i in range(columns-1):
                n = j*columns+i; faces.append((n,n+1,n+columns+1,n+columns))
        name = 'hair-surface-trial-%02d' % k
        mesh = bpy.data.meshes.new(name); mesh.from_pydata(vertices, [], faces); mesh.update()
        ob = bpy.data.objects.new(name, mesh); scene.collection.objects.link(ob); ob.data.materials.append(mat)
        for p in mesh.polygons: p.use_smooth = True
        thick = ob.modifiers.new('Hair thickness','SOLIDIFY'); thick.thickness = .0005
        objects.append(name)
    return {'created':objects, 'hidden_existing':hidden, 'headend_retained':True,
            'bound_to_rig':False, 'automatic_promotion':False}
