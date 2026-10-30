"""Reversible rear-hair silhouette and layered tips on one FBX derivative."""
import hashlib, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
from modules.skills.studio3d.character_hair_shell_trial import apply as reshape_shell

source_dir=ROOT/'3DModels/SilverHairCharacter/user-fbx-detachable-hair-01'
source=source_dir/'replaceable-hair.blend'; manifest=json.loads((source_dir/'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['files'][source.name]:raise ValueError('Source changed')
out=ROOT/'user-data/artifacts/studio3d-character/hair-contour-study-01'
if out.exists():raise ValueError('Candidate already exists')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 col=bpy.data.collections.get('Hair_SilverHair_Replaceable_01');arm=bpy.data.objects.get('Armature')
 if not col or not arm or not arm.pose.bones.get('J_Bip_C_Head'):raise ValueError('Required hair/rig missing')
 reshape_shell(tails=False)
 shell=bpy.data.objects['headend']; material=bpy.data.materials['character-hair-procedural']
 deps=bpy.context.evaluated_depsgraph_get(); eval_shell=shell.evaluated_get(deps); inv=eval_shell.matrix_world.inverted()
 def shell_radius(a,z):
  unit=Vector((math.cos(a),math.sin(a),0));origin=Vector((0,.018,z))+unit*.5
  hit,p,_,_=eval_shell.ray_cast(inv@origin,inv.to_3x3()@-unit)
  if hit:
   q=eval_shell.matrix_world@p;return math.hypot(q.x,q.y-.018)
  return .083
 pose=arm.pose.bones['J_Bip_C_Head']; bone=arm.data.bones['J_Bip_C_Head']
 deformation=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted()
 back=deformation.inverted()
 # Unequal widths and lengths, with roots placed beneath the original rear
 # shell. Their surfaces fan outward gently around its lower edge.
 angles=[.17,.43,.70,.96,1.22,1.47,1.73,1.99,2.26,2.52,2.78,2.97]
 created=[]
 for k,mid in enumerate(angles):
  phase=math.sin(k*2.31);top=1.433+.004*math.sin(k*1.7)
  bottom=1.334+.010*math.sin(k*2.04)+.004*math.sin(k*4.12)
  width=.125+.018*math.sin(k*2.11);rows=22;cols=7;verts=[];faces=[]
  for j in range(rows):
   t=j/(rows-1); z=top*(1-t)+bottom*t; taper=max(0.,(t-.73)/.27)
   half=width*(1-.91*taper);shift=.028*phase*t*t
   for i in range(cols):
    u=2*i/(cols-1)-1;a=mid+half*u+shift
    r=shell_radius(a,max(1.405,z))-.004 + .008*(t*t*(3-2*t))
    r+=.003*phase*taper
    world=Vector((r*math.cos(a),.018+r*math.sin(a),z-.002*(1-u*u)*taper))
    verts.append(tuple(back@world))
  for j in range(rows-1):
   for i in range(cols-1):
    n=j*cols+i;faces.append((n,n+1,n+cols+1,n+cols))
  name='hair-contour-tip-%02d'%k;mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
  obj=bpy.data.objects.new(name,mesh);col.objects.link(obj);obj.data.materials.append(material)
  for polygon in mesh.polygons:polygon.use_smooth=True
  group=obj.vertex_groups.new(name='J_Bip_C_Head');group.add(list(range(len(verts))),1.0,'REPLACE')
  modifier=obj.modifiers.new('Head follow','ARMATURE');modifier.object=arm
  solid=obj.modifiers.new('Thin edge','SOLIDIFY');solid.thickness=.00045
  created.append(name)
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;camera=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=20;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 camera.data.type='ORTHO';camera.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,direction in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  camera.location=center+Vector(direction)*5;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':manifest['files'][source.name],
  'collection':col.name,'new_hair_objects':created,'head_binding':'100% J_Bip_C_Head',
  'limitations':['Rendered static previews only','Hair replacement switch and movement must be verified','Intersections and resemblance not yet checked']},indent=2),encoding='utf8')
