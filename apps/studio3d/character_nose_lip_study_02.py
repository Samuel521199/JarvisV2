"""Reversible nose and lip shape study with separate surface lip accents."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/face-eye-proportion-study-04/candidate.blend';identity=hashlib.sha256(src.read_bytes()).hexdigest()
out=ROOT/'user-data/artifacts/studio3d-character/face-nose-lips-study-02'
if out.exists():raise ValueError('Existing trial requires review')
out.mkdir(parents=True)
def sm(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
def gaussian(v,c,s):return math.exp(-((v-c)/s)**2)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];arm=bpy.data.objects['Armature'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 # Coordinates for controls are derived from the current evaluated surface.
 deps=bpy.context.evaluated_depsgraph_get();ev=face.evaluated_get(deps);mesh=ev.to_mesh();coords=[ev.matrix_world@v.co for v in mesh.vertices];ev.to_mesh_clear()
 if len(coords)!=len(face.data.vertices):raise ValueError('Modifier changed vertex count')
 key=face.shape_key_add(name='NoseLipVolumeStudy',from_mix=False);m=face.matrix_world;inv=m.inverted();changed=0
 for i,v in enumerate(key.data):
  p=coords[i];ax=abs(p.x);front=1-sm(-.050,-.025,p.y)
  nose=(1-sm(.004,.021,ax))*sm(1.393,1.405,p.z)*(1-sm(1.431,1.461,p.z))*front
  lipx=1-sm(.008,.019,ax)
  upper=gaussian(p.z,1.382,.0021)*lipx*front
  lower=gaussian(p.z,1.376,.0022)*lipx*front
  dy=-.0010*nose-.0010*upper-.0008*lower
  if abs(dy)>1e-8:
   q=m@v.co;q.y+=dy;v.co=inv@q;changed+=1
 key.value=1.;bpy.context.view_layer.update()
 details=bpy.data.collections.new('Face_Lips_Trial');bpy.context.scene.collection.children.link(details)
 def mat(name,color):
  m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=.64;return m
 uppermat=mat('lip-upper-soft-rose-trial',(.62,.39,.37));lowermat=mat('lip-lower-soft-rose-trial',(.72,.48,.45))
 deps=bpy.context.evaluated_depsgraph_get();ev=face.evaluated_get(deps);iv=ev.matrix_world.inverted()
 pose=arm.pose.bones['J_Bip_C_Head'];bone=arm.data.bones['J_Bip_C_Head'];deform=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted();bind_inverse=deform.inverted()
 created=[];misses=[]
 for label,material in [('upper',uppermat),('lower',lowermat)]:
  verts=[];faces=[];cols=37;rows=5
  for j in range(rows):
   t=j/(rows-1)
   for i in range(cols):
    u=2*i/(cols-1)-1;x=.0135*u;edge=(1-u*u)**.7
    # Soft upper cupid bow and subtle lower fullness, tapered at the corners.
    seam=1.3788-.00022*(1-u*u)
    if label=='upper':z=seam+t*edge*(.00215+.00035*math.cos(u*math.pi))
    else:z=seam-t*edge*.0022
    hit,p,_,_=ev.ray_cast(iv@Vector((x,-.30,z)),iv.to_3x3()@Vector((0,1,0)))
    if not hit:misses.append([label,i,j]);raise RuntimeError('Lip ray missed face')
    p=ev.matrix_world@p;p.y-=.00014;verts.append(tuple(bind_inverse@p))
  for j in range(rows-1):
   for i in range(cols-1):
    n=j*cols+i;faces.append((n,n+1,n+cols+1,n+cols))
  mesh=bpy.data.meshes.new('lip-'+label+'-trial');mesh.from_pydata(verts,[],faces);mesh.update();ob=bpy.data.objects.new('lip-'+label+'-trial',mesh);details.objects.link(ob);mesh.materials.append(material)
  for f in mesh.polygons:f.use_smooth=True
  g=ob.vertex_groups.new(name='J_Bip_C_Head');g.add(list(range(len(verts))),1.,'REPLACE');mod=ob.modifiers.new('Head follow','ARMATURE');mod.object=arm;created.append(ob.name)
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=32;sc.cycles.use_denoising=True;sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));hair.hide_render=True
 for name,d in [('front',(0,-1,0)),('30-left',(-.5,-.8660254,0)),('side',(-1,0,0)),('side-right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,'shape_key':key.name,'face_vertices_changed':changed,'lip_collection':details.name,'lip_objects':created,'ray_misses':misses,'limitations':['Lip meshes are surface accents, not complete lip topology','Color and position need visual review','Only static images; expressions, deformation and export unverified']},indent=2),encoding='utf8')
