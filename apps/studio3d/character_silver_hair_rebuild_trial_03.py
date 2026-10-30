"""Reference-guided, detachable hair experiment on a copied character scene."""
import hashlib, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from control.studio3d_lane import render_lane

source = ROOT / 'user-data/artifacts/studio3d-character/reference-eye-width-study-02/candidate.blend'
out = ROOT / 'user-data/artifacts/studio3d-character/silver-hair-rebuild-study-03'
if out.exists():
    raise ValueError('Output already exists')
digest = hashlib.sha256(source.read_bytes()).hexdigest()
out.mkdir(parents=True)

def cubic(p, t):
    return sum((Vector(q) * w for q, w in zip(p, ((1-t)**3, 3*t*(1-t)**2, 3*t*t*(1-t), t**3))), Vector())

def smooth(t):
    t = max(0., min(1., t))
    return t*t*(3-2*t)

with render_lane(out):
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    old = bpy.data.collections['Hair_SilverHair_Replaceable_01']
    old.hide_render = True
    old.hide_viewport = True
    hair = bpy.data.collections.new('Hair_Silver_Rebuild_Replaceable_Trial')
    bpy.context.scene.collection.children.link(hair)
    # Retain the existing base under the new locks, without modifying original data.
    for name in ('headend', 'hair-scalp-refined'):
        original = bpy.data.objects[name]
        copy = original.copy()
        copy.name = 'Rebuild_Base_' + name
        copy.hide_render = False
        copy.hide_viewport = False
        hair.objects.link(copy)

    arm = bpy.data.objects['Armature']
    bone = arm.data.bones['J_Bip_C_Head']
    pose = arm.pose.bones['J_Bip_C_Head']
    deform = arm.matrix_world @ pose.matrix @ bone.matrix_local.inverted() @ arm.matrix_world.inverted()
    inverse = deform.inverted()
    original_mat = bpy.data.materials['character-hair-procedural']
    mats = []
    for index, color in enumerate(((.73,.73,.79,1),(.80,.80,.86,1),(.76,.76,.82,1),(.84,.84,.89,1))):
        mat = original_mat.copy()
        mat.name = 'Rebuild_Silver_%02d' % index
        shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        # Disconnect atlas/procedural colors so each lock has a consistent silver tone.
        for link in list(shader.inputs['Base Color'].links):
            mat.node_tree.links.remove(link)
        shader.inputs['Base Color'].default_value = color
        shader.inputs['Roughness'].default_value = .39
        mats.append(mat)
    for ob in hair.objects:
        ob.data = ob.data.copy()
        ob.data.materials.clear()
        ob.data.materials.append(mats[2])

    created = []
    def lock(name, points, width, axis, material, crown=.002, root_width=.35):
        rows, cols = 36, 9
        verts, faces = [], []
        across = Vector(axis).normalized()
        for j in range(rows):
            t = j / (rows-1)
            p = cubic(points, t)
            w = width * (root_width + (1-root_width)*smooth(t/.23)) * (1-.995*smooth((t-.72)/.28))
            for i in range(cols):
                u = 2*i/(cols-1)-1
                # Rounded center catches a soft highlight rather than a flat card.
                q = p + across * (u*w)
                q.y -= crown*(1-u*u) if axis == (1,0,0) else 0
                q.z += crown*(1-u*u) if axis != (1,0,0) else 0
                verts.append(tuple(inverse @ q))
        for j in range(rows-1):
            for i in range(cols-1):
                n = j*cols+i
                faces.append((n,n+1,n+cols+1,n+cols))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        ob = bpy.data.objects.new(name, mesh)
        hair.objects.link(ob)
        mesh.materials.append(mats[material % len(mats)])
        for poly in mesh.polygons: poly.use_smooth = True
        group = ob.vertex_groups.new(name='J_Bip_C_Head')
        group.add(list(range(len(verts))), 1., 'REPLACE')
        mod = ob.modifiers.new('Follow head', 'ARMATURE')
        mod.object = arm
        mod = ob.modifiers.new('Fine thickness', 'SOLIDIFY')
        mod.thickness = .0005
        created.append(name)

    # Locks hug an approximate scalp ellipsoid before continuing down the back.
    # Mesh strips overlap slightly to cover the scalp, with staggered tapered ends.
    for k in range(23):
        a = .04 + (math.pi-.08)*k/22
        c, s = math.cos(a), math.sin(a)
        phase = math.sin(k*2.17)
        length = .405 + .045*math.sin(k*1.53+.2)
        rows, cols = 60, 9
        vs, fs = [], []
        for j in range(rows):
            t = j/(rows-1)
            t0 = min(1.,t/.43)
            theta=.10+1.70*t0
            x=.103*math.sin(theta)*c
            y=.025+.119*math.sin(theta)*s
            z=1.497+.108*math.cos(theta)
            if t>.43:
                v=(t-.43)/.57
                x=x*(1+.22*v)+.011*phase*v*v
                y=y+.016*v+.004*math.sin(v*math.pi*1.3+k*.6)*v
                z=z+(1.602-length-z)*v
            half=.016*(.35+.65*smooth(t/.11))*(1-.99*smooth((t-.83)/.17))
            for i in range(cols):
                u=2*i/(cols-1)-1
                # Constant angular widths around the ellipsoid keep the locks on the shell.
                da=u*half/.103
                ca,sa=math.cos(a+da),math.sin(a+da)
                xx=x+(.103*math.sin(theta))*(ca-c)
                yy=y+(.119*math.sin(theta))*(sa-s)+.0015*(1-u*u)*s
                zz=z+.0015*(1-u*u)*max(0.,math.cos(theta))
                vs.append(tuple(inverse@Vector((xx,yy,zz))))
        for j in range(rows-1):
            for i in range(cols-1):
                n=j*cols+i;fs.append((n,n+1,n+cols+1,n+cols))
        name='BackLock_%02d'%k
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(vs,[],fs);mesh.update()
        ob=bpy.data.objects.new(name,mesh);hair.objects.link(ob);mesh.materials.append(mats[k%3])
        for poly in mesh.polygons:poly.use_smooth=True
        group=ob.vertex_groups.new(name='J_Bip_C_Head');group.add(list(range(len(vs))),1.,'REPLACE')
        mod=ob.modifiers.new('Follow head','ARMATURE');mod.object=arm
        mod=ob.modifiers.new('Fine thickness','SOLIDIFY');mod.thickness=.0005
        created.append(name)

    # Forehead fringe starts at the part and sweeps into asymmetrical tapered tips.
    specs = [(-.062,-.080,1.486),(-.047,-.066,1.471),(-.032,-.049,1.459),
             (-.016,-.026,1.472),(.002,.006,1.459),(.020,.031,1.477),
             (.037,.050,1.469),(.053,.073,1.489)]
    for k,(root,tip,ztip) in enumerate(specs):
        p=[(root*.35,-.022,1.603),(root*.8,-.067,1.599),
           (tip*.88,-.099,1.535),(tip,-.103,ztip)]
        lock('Fringe_%02d'%k,p,.017,(1,0,0),[1,2,1,3][k%4],.0015,.24)

    # Side pieces frame the cheeks without being joined to the face.
    for sign in (-1,1):
        # Side crown fans connect the part to the region above and behind the ear.
        for k in range(5):
            y = -.050 + k*.027
            p=[(sign*.014,.015,1.604),(sign*.067,y*.45,1.605),
               (sign*.103,y,1.553),(sign*(.102+.003*k),y+.015,1.438-.012*k)]
            lock('CrownSide_%s_%02d'%('L' if sign<0 else 'R',k),p,.017,(0,1,0),k%3,.001,.45)
        for k in range(4):
            x=sign*(.067+.005*k)
            p=[(sign*(.036+.003*k),-.018,1.597),(x,-.074,1.574),
               (sign*(.085+.004*k),-.087,1.47),(sign*(.065+.011*k),-.062,1.373-.025*k)]
            lock('Side_%s_%02d'%('L' if sign<0 else 'R',k),p,.010,(1,0,0),k+1,.001,.35)

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'), check_existing=False)
    scene=bpy.context.scene
    cam=scene.camera
    scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=24
    scene.cycles.use_denoising=True
    scene.render.resolution_x=scene.render.resolution_y=768
    scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'
    cam.data.type='ORTHO'; cam.data.ortho_scale=.43
    center=Vector((0,0,1.40))
    for name,direction in [('front',(0,-1,0)),('oblique',(-.7071,-.7071,0)),('side',(-1,0,0)),('rear',(0,1,0))]:
        cam.location=center+Vector(direction)*5
        cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(out/(name+'.png'))
        bpy.ops.render.render(write_still=True)
        print('RENDER_READY',name,flush=True)
    (out/'report.json').write_text(json.dumps({'source_sha256':digest,'status':'experimental_not_accepted',
        'new_collection':hair.name,'old_collection_hidden':old.name,'new_locks':created,
        'limitations':['Hand-parameterized approximate reconstruction from concept, not a reference match',
                       'No movement, collision, spring, VRM export or weight deformation test',
                       'Individual locks may intersect scalp or each other']},indent=2),encoding='utf8')
