"""Experimental layered back hair; keep it independently replaceable."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
srcdir=ROOT/'3DModels/SilverHairCharacter/user-fbx-silhouette-02';source=srcdir/'candidate.blend'
man=json.loads((srcdir/'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=man['files'][source.name]:raise ValueError('Source changed')
out=ROOT/'user-data/artifacts/studio3d-character/hair-nested-strands-01'
if out.exists():raise ValueError('Existing trial requires inspection')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 col=bpy.data.collections['Hair_SilverHair_Replaceable_01'];arm=bpy.data.objects['Armature'];shell=bpy.data.objects['headend'];mat=bpy.data.materials['character-hair-procedural']
 deps=bpy.context.evaluated_depsgraph_get();surface=shell.evaluated_get(deps);inverse=surface.matrix_world.inverted()
 pose=arm.pose.bones['J_Bip_C_Head'];bone=arm.data.bones['J_Bip_C_Head']
 deform=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted();bind_inverse=deform.inverted()
 def radius(angle,z):
  unit=Vector((math.cos(angle),math.sin(angle),0));origin=Vector((0,.018,z))+unit*.5
  hit,point,_,_=surface.ray_cast(inverse@origin,inverse.to_3x3()@-unit)
  if hit:
   p=surface.matrix_world@point;return math.hypot(p.x,p.y-.018)
  return .079
 def smooth(t):
  t=max(0.,min(1.,t));return t*t*(3-2*t)
 hidden=[]
 for ob in col.objects:
  if ob.name.startswith('back-hair-refined-'):ob.hide_render=True;ob.hide_set(True);hidden.append(ob.name)
 names=[]
 for layer in range(2):
  count=13 if layer==0 else 9
  for k in range(count):
   mid=(k+.5+.17*layer)*math.pi/count;phase=math.sin(k*2.41+layer*1.72)
   top=1.56+.006*math.sin(k*1.6+layer);bottom=1.341+.010*math.sin(k*2.07+layer)+.006*math.sin(k*3.77)
   width=(math.pi/count)*(.76+.12*math.sin(k*1.3));rows=34;columns=7;vs=[];fs=[]
   for j in range(rows):
    t=j/(rows-1);z=top*(1-t)+bottom*t
    w=width*(1-.92*smooth((t-.78)/.22));sweep=.04*phase*t*t
    for i in range(columns):
     u=2*i/(columns-1)-1;a=min(math.pi-.01,max(.01,mid+w*u+sweep))
     # Start inside the shell; only emerge as the locks reach the lower head.
     reveal=smooth((t-(.38+.07*math.sin(k*1.8)))/.34)
     r=radius(a,max(1.455,z))-.010+(.012+layer*.0012)*reveal
     if z<1.455:r*=1-.06*min(1.,(1.455-z)/.12)
     r+=.002*phase*smooth((t-.80)/.2)
     p=Vector((r*math.cos(a),.018+r*math.sin(a),z-.002*(1-u*u)*smooth((t-.80)/.2)))
     vs.append(tuple(bind_inverse@p))
   for j in range(rows-1):
    for i in range(columns-1):
     n=j*columns+i;fs.append((n,n+1,n+columns+1,n+columns))
   name='hair-nested-%s-%02d'%(layer,k);mesh=bpy.data.meshes.new(name);mesh.from_pydata(vs,[],fs);mesh.update()
   ob=bpy.data.objects.new(name,mesh);col.objects.link(ob);ob.data.materials.append(mat)
   for poly in mesh.polygons:poly.use_smooth=True
   grp=ob.vertex_groups.new(name='J_Bip_C_Head');grp.add(list(range(len(vs))),1.,'REPLACE')
   mod=ob.modifiers.new('Head follow','ARMATURE');mod.object=arm
   mod=ob.modifiers.new('Hair thickness','SOLIDIFY');mod.thickness=.00035;names.append(name)
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,direction in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(direction)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':man['files'][source.name],
  'hair_collection':col.name,'new_hair_objects':names,'hidden_original_strands':hidden,'binding':'100% head bone',
  'limitations':['Procedurally inferred hair; appearance requires review','No motion, collision or export test']},indent=2),encoding='utf8')
