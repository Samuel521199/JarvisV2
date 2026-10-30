"""Independent eyebrow, liner wing and lash study against user's design."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/closed-lips-design-study-02/candidate.blend';identity=hashlib.sha256(src.read_bytes()).hexdigest();out=ROOT/'user-data/artifacts/studio3d-character/eye-brow-reference-study-01'
if out.exists():raise ValueError('Existing trial requires review')
out.mkdir(parents=True)
def sm(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];arm=bpy.data.objects['Armature'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01'];old=bpy.data.collections['Face_EyeDetails_Trial']
 key=face.shape_key_add(name='ReferenceBrowOuterLift',from_mix=False);m=face.matrix_world;inv=m.inverted()
 brow={i for p in face.data.polygons if p.material_index==5 for i in p.vertices};changed=0
 for i in brow:
  v=key.data[i];p=m@v.co;lift=.0030*sm(.030,.075,abs(p.x));p.z+=lift;v.co=inv@p;changed+=1
 key.value=1.
 # Hide only the former independent lashes; keep non-destructive copies of lower lashes.
 old.hide_render=True;old.hide_viewport=True;col=bpy.data.collections.new('Face_EyelinerLash_DesignTrial');bpy.context.scene.collection.children.link(col);copies=[]
 for ob in old.objects:
  if '-lower-' in ob.name:
   cp=ob.copy();cp.name='lower-lash-carry-'+ob.name;col.objects.link(cp);copies.append(cp.name)
 lashmat=bpy.data.materials.new('eyeliner-warm-dark-trial');lashmat.diffuse_color=(.028,.012,.012,1);lashmat.use_nodes=True;shader=next(n for n in lashmat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');shader.inputs['Base Color'].default_value=(.028,.012,.012,1);shader.inputs['Roughness'].default_value=.6
 bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();ev=face.evaluated_get(deps);iv=ev.matrix_world.inverted();pose=arm.pose.bones['J_Bip_C_Head'];bone=arm.data.bones['J_Bip_C_Head'];deform=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted();bind_inverse=deform.inverted();scale=.34/768.
 def hit(px,py,side):
  x=(px-384)*scale
  if side==1:x=-x
  z=1.43+(384-py)*scale
  ok,p,_,_=ev.ray_cast(iv@Vector((x,-.30,z)),iv.to_3x3()@Vector((0,1,0)))
  if not ok:raise RuntimeError('Eye ray missed face')
  p=ev.matrix_world@p;p.y-=.00028;return p
 def bind(o):
  g=o.vertex_groups.new(name='J_Bip_C_Head');g.add(list(range(len(o.data.vertices))),1.,'REPLACE');mod=o.modifiers.new('Head follow','ARMATURE');mod.object=arm
 created=[]
 for side in (-1,1):
  pts=[hit(x,y,side) for x,y in [(234,338),(240,335),(236,345),(219,332)]]
  # A narrow outer wing, joined visually to the upper lid; evaluate all views.
  mesh=bpy.data.meshes.new('liner-wing');mesh.from_pydata([tuple(bind_inverse@p) for p in pts],[],[(0,1,2),(0,2,3)]);mesh.update();ob=bpy.data.objects.new('liner-wing-'+str(side),mesh);col.objects.link(ob);mesh.materials.append(lashmat);bind(ob);created.append(ob.name)
  for j,(px,py) in enumerate([(235,336),(245,331),(256,326),(269,324)]):
   p=hit(px,py,side);length=[.0058,.0052,.0044,.0034][j];spread=[.0032,.0022,.0016,.0009][j]
   c=bpy.data.curves.new('eyelash-cluster','CURVE');c.dimensions='3D';c.resolution_u=10;c.bevel_depth=.00023 if j<2 else .00018;c.bevel_resolution=3
   sp=c.splines.new('POLY');sp.points.add(5)
   for k,pt in enumerate(sp.points):
    t=k/5;q=p+Vector((side*spread*(t+.25*t*t),-.00030*t,length*(t-.12*t*t)));q=bind_inverse@q;pt.co=(*q,1);pt.radius=max(.04,1-.96*t)
   c.materials.append(lashmat);ob=bpy.data.objects.new('eyelash-cluster-%s-%s'%(side,j),c);col.objects.link(ob)
   bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.convert(target='MESH');ob=bpy.context.object;bind(ob);created.append(ob.name)
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=36;sc.cycles.use_denoising=True;sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));hair.hide_render=True
 for name,d in [('front',(0,-1,0)),('30-left',(-.5,-.8660254,0)),('side',(-1,0,0)),('side-right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,'brow_shape_key':key.name,'brow_vertices':changed,'new_eye_detail_collection':col.name,'created':created,'lower_lash_copies':copies,'limitations':['Visual trial; surface placement and style need review','No blink, facial motion or export test','Lip study also unaccepted']},indent=2),encoding='utf8')
