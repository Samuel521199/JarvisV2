"""Exploratory detachable long hair blockout for the user-provided design."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/face-proportion-design-study-03/candidate.blend'
identity=hashlib.sha256(src.read_bytes()).hexdigest();out=ROOT/'user-data/artifacts/studio3d-character/long-hair-design-study-01'
if out.exists():raise ValueError('Existing study needs inspection')
out.mkdir(parents=True)
def sm(t):
 t=max(0.,min(1.,t));return t*t*(3-2*t)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 old=bpy.data.collections['Hair_SilverHair_Replaceable_01'];old.hide_render=True;old.hide_viewport=True
 new=bpy.data.collections.new('Hair_LongSilver_DesignTrial');bpy.context.scene.collection.children.link(new)
 copied=[]
 for ob in old.objects:
  if ob.name=='headend' or ob.name=='hair-scalp-refined' or ob.name.startswith('bang-refined-'):
   cp=ob.copy();cp.name='long-study-base-'+ob.name;new.objects.link(cp);copied.append(cp.name)
 arm=bpy.data.objects['Armature'];pose=arm.pose.bones['J_Bip_C_Head'];bone=arm.data.bones['J_Bip_C_Head']
 deform=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted();inv=deform.inverted()
 base=bpy.data.materials['character-hair-procedural'];created=[];count=23;rows=50;cols=9
 for k in range(count):
  a=.035+(math.pi-.07)*k/(count-1);p=math.sin(1.91*k+.7);q=math.sin(3.2*k+.3)
  length=.385+.052*(.5+.5*math.sin(k*1.71))
  vs=[];fs=[]
  for j in range(rows):
   t=j/(rows-1);z=1.555-length*t
   rr=.063+.037*sm(t/.20)+.040*sm((t-.22)/.65)
   ry=.040+.037*sm(t/.20)+.018*sm((t-.25)/.70)
   cx=rr*math.cos(a)+.008*p*t*t;cy=.025+ry*math.sin(a)+.012*t
   width=(.007+.006*sm(t/.12))*(1-.98*sm((t-.77)/.23))
   for i in range(cols):
    u=2*i/(cols-1)-1;bulge=(1-u*u)*.0028
    # Ribbon width follows the tangent of the scalp ellipse.
    x=cx-u*math.sin(a)*width;y=cy+u*math.cos(a)*width+bulge
    zz=z-.008*u*math.sin(a)*sm((t-.75)/.25)+.002*q*t
    vs.append(tuple(inv@Vector((x,y,zz))))
  for j in range(rows-1):
   for i in range(cols-1):
    n=j*cols+i;fs.append((n,n+1,n+cols+1,n+cols))
  name='long-hair-clump-%02d'%k;mesh=bpy.data.meshes.new(name);mesh.from_pydata(vs,[],fs);mesh.update();ob=bpy.data.objects.new(name,mesh);new.objects.link(ob);mesh.materials.append(base)
  for poly in mesh.polygons:poly.use_smooth=True
  g=ob.vertex_groups.new(name='J_Bip_C_Head');g.add(list(range(len(vs))),1.,'REPLACE')
  mod=ob.modifiers.new('Follow head','ARMATURE');mod.object=arm
  mod=ob.modifiers.new('Clump thickness','SOLIDIFY');mod.thickness=.0005;created.append(name)
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=24;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO'
 for crop,center,scale in [('head',Vector((0,0,1.43)),.34),('bust',Vector((0,0,1.33)),.57)]:
  cam.data.ortho_scale=scale
  for name,d in [('front',(0,-1,0)),('45-left',(-.7071,-.7071,0)),('left',(-1,0,0)),('rear',(0,1,0))]:
   cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
   sc.render.filepath=str(out/(crop+'-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY',crop,name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,'old_hair_collection':old.name,'old_hair_hidden':True,'trial_hair_collection':new.name,'copied_base_objects':copied,'new_clumps':created,'binding':'clumps 100% head bone','limits':['Procedural exploratory blockout','No cloth simulation, collision, blink, animation or export validation','Styling and appearance require visual inspection']},indent=2),encoding='utf8')
