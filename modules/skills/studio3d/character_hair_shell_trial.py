"""Disposable shell reshaping and layered ends on a known FBX derivative."""
import math


def apply(*, tails=False):
    import bpy
    from mathutils import Vector
    scene = bpy.context.scene
    shell = bpy.data.objects.get('headend')
    material = bpy.data.materials.get('character-hair-procedural')
    if not shell or not material or not bpy.data.objects.get('Body'):
        raise ValueError('Expected character FBX derivative')
    if bpy.data.objects.get('hair-shell-tail-00'):
        raise ValueError('Already applied')
    hidden = []
    for ob in scene.objects:
        if ob.name.startswith('back-hair-refined-') and tails:
            ob.hide_render = True; ob.hide_set(True); hidden.append(ob.name)

    shell.data = shell.data.copy()
    inverse = shell.matrix_world.inverted()
    for v in shell.data.vertices:
        p = shell.matrix_world @ v.co
        # Preserve the crown and forehead. Extend only the rear shell in an
        # uninterrupted, gently tapered region; no new upper seam is created.
        height = max(0.0, min(1.0, (1.49-p.z)/.115))
        height = height*height*(3-2*height)
        rear = max(0.0, min(1.0, (p.y+.015)/.060))
        amount = height*rear
        scale = 1 + .25*amount
        p.x *= scale; p.y = .018+(p.y-.018)*scale
        p.z -= .013*amount
        v.co = inverse @ p
    shell.data.update(); bpy.context.view_layer.update()

    if not tails:
        return {'modified':'headend mesh copy','hidden_existing':hidden,'created':[],
                'automatic_promotion':False,'bound_to_rig':True}

    # Wide, overlapping lower clumps start embedded under the reshaped shell.
    # They appear only near the bottom, with unequal curved tips.
    deps = bpy.context.evaluated_depsgraph_get(); evaluated = shell.evaluated_get(deps)
    inv = evaluated.matrix_world.inverted()
    def radius(angle,z):
        unit = Vector((math.cos(angle),math.sin(angle),0))
        origin = Vector((0,.018,z)) + unit*.5
        ok, co, _, _ = evaluated.ray_cast(inv@origin, inv.to_3x3()@-unit)
        if ok:
            pt = evaluated.matrix_world@co
            return Vector((pt.x,pt.y-.018,0)).length
        return .079
    objects = []
    for k in range(9):
        mid = (k+.5)*math.pi/9
        variation = math.sin(k*2.17)
        start_z = 1.437 + .008*math.sin(k*1.8)
        end_z = 1.337 + .007*math.sin(k*2.4)+.004*math.sin(k*4.6)
        vs=[]; fs=[]; rows=28; cols=9
        for j in range(rows):
            t=j/(rows-1); z=start_z*(1-t)+end_z*t
            tip=max(0.,(t-.72)/.28)
            half=math.pi/9*(.7-.49*tip)
            shift=.025*variation*t*t
            for i in range(cols):
                u=2*i/(cols-1)-1; angle=min(math.pi-.01,max(.01,mid+half*u+shift))
                r=radius(angle,max(1.385,z))
                r += -.004 + .007*min(1., t*1.7)
                r += .002*variation*tip
                vs.append((r*math.cos(angle),.018+r*math.sin(angle), z-.003*tip*(1-u*u)))
        for j in range(rows-1):
            for i in range(cols-1):
                a=j*cols+i;fs.append((a,a+1,a+cols+1,a+cols))
        name='hair-shell-tail-%02d'%k
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(vs,[],fs);mesh.update()
        ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob);ob.data.materials.append(material)
        for f in mesh.polygons:f.use_smooth=True
        mod=ob.modifiers.new('Thin hair edge','SOLIDIFY');mod.thickness=.0005;objects.append(name)
    return {'modified':'headend mesh copy','hidden_existing':hidden,'created':objects,
            'automatic_promotion':False,'new_tails_bound_to_rig':False}
