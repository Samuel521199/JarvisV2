"""Independent eye-detail trial against the user's new head references."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
srcdir=ROOT/'3DModels/SilverHairCharacter/user-fbx-face-study-01';source=srcdir/'candidate.blend'
manifest=json.loads((srcdir/'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['files'][source.name]:raise ValueError('Source changed')
out=ROOT/'user-data/artifacts/studio3d-character/eye-detail-reference-02'
if out.exists():raise ValueError('Existing study requires inspection')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];arm=bpy.data.objects['Armature'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 # Copy only the iris shader; the original image remains packed and unchanged.
 index=next(i for i,m in enumerate(face.data.materials) if 'EyeIris_00_EYE'.lower() in m.name.lower())
 iris=face.data.materials[index].copy();iris.name='reference-blue-iris-trial';face.data.materials[index]=iris
 nodes=iris.node_tree.nodes;shader=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
 previous=shader.inputs['Base Color'].links[0].from_socket
 hue=nodes.new('ShaderNodeHueSaturation');hue.inputs['Hue'].default_value=.06;hue.inputs['Saturation'].default_value=1.25;hue.inputs['Value'].default_value=1.35
 iris.node_tree.links.new(previous,hue.inputs['Color']);iris.node_tree.links.new(hue.outputs['Color'],shader.inputs['Base Color'])
 # Adjust the editable eye-area shape, allowing the change to be dialed back.
 key=face.shape_key_add(name='ReferenceEyeOpeningStudy',from_mix=False)
 m=face.matrix_world;inv_m=m.inverted()
 def smooth(a,b,x):
  t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
 changed=0
 for v in key.data:
  p=m@v.co
  w=smooth(.008,.025,abs(p.x))*(1-smooth(.056,.087,abs(p.x)))*smooth(1.405,1.424,p.z)*(1-smooth(1.462,1.485,p.z))*smooth(.025,.050,-p.y)
  if w>1e-7:
   p.z=1.446+(p.z-1.446)*(1+.20*w)
   v.co=inv_m@p;changed+=1
 key.value=1.;bpy.context.view_layer.update()
 details=bpy.data.collections.new('Face_EyeDetails_Trial');bpy.context.scene.collection.children.link(details)
 lashmat=bpy.data.materials.new('eye-lash-deep-brown-trial');lashmat.diffuse_color=(.035,.016,.018,1);lashmat.use_nodes=True
 principled=next(n for n in lashmat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');principled.inputs['Base Color'].default_value=(.035,.016,.018,1);principled.inputs['Roughness'].default_value=.58
 deps=bpy.context.evaluated_depsgraph_get();ev=face.evaluated_get(deps);inv=ev.matrix_world.inverted()
 pose=arm.pose.bones['J_Bip_C_Head'];bone=arm.data.bones['J_Bip_C_Head']
 deformation=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted();bind_inverse=deformation.inverted()
 # Screen-space anchor positions are tied to the matching orthographic head
 # render: 768px, .34m ortho scale, centre z=1.43. The Face ray supplies depth.
 scale=.34/768.; upper=[(239,334),(247,329),(255,326),(264,322),(274,321),(283,321)]
 lower=[(242,361),(251,367),(261,372),(271,374),(281,375)]
 created=[];skipped=[]
 for side in (-1,1):
  for kind,samples in [('upper',upper),('lower',lower)]:
   for j,(px,py) in enumerate(samples):
    x=(px-384)*scale
    if side==1:x=-x
    z=1.43+(384-py)*scale
    origin=Vector((x,-.30,z));direction=Vector((0,1,0))
    hit,point,_,_=ev.ray_cast(inv@origin,inv.to_3x3()@direction)
    if not hit:skipped.append([side,kind,j]);continue
    p=ev.matrix_world@point;p.y-=.00045
    length=(.0045+.0015*(1-j/max(1,len(samples)-1))) if kind=='upper' else .0020
    offset=side*(.0011+.0015*(1-j/max(1,len(samples)-1)))
    curve=bpy.data.curves.new('eye-detail-curve','CURVE');curve.dimensions='3D';curve.resolution_u=8;curve.bevel_depth=.00016 if kind=='upper' else .00011;curve.bevel_resolution=2;curve.resolution_u=8
    spline=curve.splines.new('POLY');spline.points.add(4)
    for k,pt in enumerate(spline.points):
     t=k/4;direction_z=1 if kind=='upper' else -1
     q=p+Vector((offset*(t+.15*t*t),-.00035*t,direction_z*length*(t-.14*t*t)))
     q=bind_inverse@q;pt.co=(q.x,q.y,q.z,1);pt.radius=max(.08,1-t*.92)
    name='eye-detail-%s-%s-%02d'%('r' if side<0 else 'l',kind,j);ob=bpy.data.objects.new(name,curve);details.objects.link(ob);curve.materials.append(lashmat)
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH')
    ob=bpy.context.object;group=ob.vertex_groups.new(name='J_Bip_C_Head');group.add(list(range(len(ob.data.vertices))),1.,'REPLACE')
    mod=ob.modifiers.new('Head follow','ARMATURE');mod.object=arm;created.append(name)
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=24;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,d in [('front',(0,-1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':manifest['files'][source.name],
  'hair_collection':hair.name,'eye_detail_collection':details.name,'new_lashes':created,'skipped_anchors':skipped,
  'eye_shape_key':key.name,'eye_vertices_changed':changed,'iris_material':iris.name,'original_iris_material_retained':True,'binding':'100% head bone',
  'limits':['Approximate geometry, visual fit requires review','Only static head renders','No eyelid deformation, rig animation or export test']},indent=2),encoding='utf8')
