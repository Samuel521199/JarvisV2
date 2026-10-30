"""Reversible experimental layered rear/side hair for the user's FBX derivative.

This is an artist-authored approximation. It does not claim reference fidelity,
animation binding, or a valid hair topology. Apply only to a disposable scene.
"""
import math


def apply():
    import bpy

    scene = bpy.context.scene
    required = {'Body', 'Face', 'hair-scalp-refined', 'bang-refined-center'}
    if not required.issubset({o.name for o in scene.objects}):
        raise ValueError('Expected FBX-derived character scene')
    if bpy.data.objects.get('hair-layered-trial-00'):
        raise ValueError('Hair trial already applied')
    material = bpy.data.materials.get('character-hair-procedural')
    if material is None:
        raise ValueError('Expected hair material')

    # Retain objects for rollback but hide the narrow, parallel rear spikes.
    hidden = []
    for ob in scene.objects:
        if ob.name.startswith('back-hair-refined-'):
            ob.hide_render = True
            ob.hide_set(True)
            hidden.append(ob.name)

    created = []
    n, rows, cols = 13, 32, 7
    for k in range(n):
        verts, faces = [], []
        mid = (k + 0.5) * math.pi / n
        # Start beneath the dome, spread over the scalp and separate only at
        # the lower tip. Unequal lengths reduce the old comb-like silhouette.
        end_z = 1.355 + 0.012 * math.sin(2.1 * k) + 0.005 * math.sin(4.7 * k)
        if k in (0, n - 1):
            end_z += .006
        for j in range(rows):
            t = j / (rows - 1)
            z = (1.587 - .008 * math.sin(k * 2.3)) * (1 - t) + end_z * t
            # Dome centred at z=1.458, with measured upper ellipsoid radii.
            q = max(0.0, min(1.0, (z - 1.458) / .142))
            cap = math.sqrt(max(0.0, 1.0 - q * q))
            lower = max(0.0, min(1.0, (1.458 - z) / .11))
            rx = .09062 * cap * (1 - .09 * lower)
            ry = .1096 * cap * (1 - .06 * lower)
            # Keep the top slightly above the cap and the lower area connected.
            bulge = .004 + .002 * math.sin(math.pi * t)
            tip = max(0.0, (t - .78) / .22)
            width = (math.pi / n) * (0.67 * (1 - tip) + .02 * tip)
            sweep = .055 * math.sin(k * 1.7) * t * t
            for i in range(cols):
                u = 2 * i / (cols - 1) - 1
                a = mid + width * u + sweep
                crown = (1-u*u) * (.0013 + .001 * t)
                x = (rx + bulge + crown) * math.cos(a)
                y = .018 + (ry + bulge + crown) * math.sin(a)
                zz = z - tip * (.0035 * (1-u*u))
                verts.append((x, y, zz))
        for j in range(rows - 1):
            for i in range(cols - 1):
                a = j * cols + i
                faces.append((a, a + 1, a + 1 + cols, a + cols))
        name = 'hair-layered-trial-%02d' % k
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces); mesh.update()
        ob = bpy.data.objects.new(name, mesh); scene.collection.objects.link(ob)
        ob.data.materials.append(material)
        for face in mesh.polygons:
            face.use_smooth = True
        solid = ob.modifiers.new('Hair thickness', 'SOLIDIFY'); solid.thickness = .0005
        created.append(name)
    return {'created': created, 'hidden_existing': hidden, 'scope': 'experimental non-rigged hair',
            'automatic_promotion': False}
