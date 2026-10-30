"""Reference-guided, reversible individual back locks with tapered roots."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
srcdir=ROOT/'3DModels/SilverHairCharacter/user-fbx-face-study-01';source=srcdir/'candidate.blend'
manifest=json.loads((srcdir/'manifest.json').read_text(encoding='utf8'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['files'][source.name]:raise ValueError('Source changed')
out=ROOT/'user-data/artifacts/studio3d-character/hair-flow-study-01'
if out.exists():raise ValueError('Existing trial needs inspection')
out.mkdir(parents=True)
def smooth(t):
 t=max(0.,min(1.,t));return t*t*(3-2*t)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
 col=bpy.data.collections['Hair_SilverHair_Replaceable_01'];arm=bpy.data.objects['Armature'];shell=bpy.data.objects['headend']
 base=bpy.data.materials['character-hair-procedural'];mat=base.copy();mat.name='hair-flow-root-fade'
 mat.use_nodes=True;nodes=mat.node_tree.nodes;shader=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
 uv=nodes.new('ShaderNodeUVMap');uv.uv_map='HairFlowUV'
 sep=nodes.new('ShaderNodeSeparateXYZ');ramp=nodes.new('ShaderNodeMapRange');ramp.clamp=True
 ramp.inputs['From Min'].default_value=.04;ramp.inputs['From Max'].default_value=.34
 ramp.inputs['To Min'].default_value=0.;ramp.inputs['To Max'].default_value=1.
 mat.node_tree.links.new(uv.outputs['UV'],sep.inputs['Vector']);mat.node_tree.links.new(sep.outputs['Y'],ramp.inputs['Value'])
 mat.node_tree.links.new(ramp.outputs['Result'],shader.inputs['Alpha'])
 if hasattr(mat,'surface_render_method'):mat.surface_render_method='DITHERED'
 deps=bpy.context.evaluated_depsgraph_get();surface=shell.evaluated_get(deps);inv=surface.matrix_world.inverted()
 pose=arm.pose.bones['J_Bip_C_Head'];bone=arm.data.bones['J_Bip_C_Head']
 deform=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted();bind_inverse=deform.inverted()
 def radius(a,z):
  unit=Vector((math.cos(a),math.sin(a),0));origin=Vector((0,.018,z))+unit*.5
  hit,p,_,_=surface.ray_cast(inv@origin,inv.to_3x3()@-unit)
  if hit:
   q=surface.matrix_world@p;return math.hypot(q.x,q.y-.018)
  return .081
 hidden=[]
 for o in col.objects:
  if o.name.startswith('back-hair-refined-'):o.hide_render=True;o.hide_set(True);hidden.append(o.name)
 created=[];count=17;rows=40;cols=9
 for k in range(count):
  phase=math.sin(k*2.07+.3);mid=(k+.5)*math.pi/count
  top=1.562+.010*math.sin(k*1.33);bottom=1.331+.011*math.sin(k*1.89)+.005*math.sin(k*4.43)
  half=(math.pi/count)*(.92+.14*math.sin(k*2.13));vs=[];fs=[]
  for j in range(rows):
   t=j/(rows-1);z=top*(1-t)+bottom*t
   taper=(.06+.94*smooth(t/.20))*(1-.94*smooth((t-.78)/.22));shift=.035*phase*t*t
   for i in range(cols):
    u=2*i/(cols-1)-1;a=max(.005,min(math.pi-.005,mid+u*half*taper+shift))
    shell_z=max(1.445,z);r=radius(a,shell_z)+.0007+.0011*(1-u*u)
    if z<1.445:r*=1-.05*min(1.,(1.445-z)/.12)
    r+=.0025*phase*smooth((t-.78)/.22)
    world=Vector((r*math.cos(a),.018+r*math.sin(a),z-.002*(1-u*u)*smooth((t-.78)/.22)))
    vs.append(tuple(bind_inverse@world))
  for j in range(rows-1):
   for i in range(cols-1):
    n=j*cols+i;fs.append((n,n+1,n+cols+1,n+cols))
  name='hair-flow-lock-%02d'%k;mesh=bpy.data.meshes.new(name);mesh.from_pydata(vs,[],fs);mesh.update()
  ob=bpy.data.objects.new(name,mesh);col.objects.link(ob);mesh.materials.append(mat)
  uvdata=mesh.uv_layers.new(name='HairFlowUV')
  for poly in mesh.polygons:
   poly.use_smooth=True
   for li in poly.loop_indices:
    vi=mesh.loops[li].vertex_index;uvdata.data[li].uv=((vi%cols)/(cols-1),(vi//cols)/(rows-1))
  group=ob.vertex_groups.new(name='J_Bip_C_Head');group.add(list(range(len(vs))),1.,'REPLACE')
  mod=ob.modifiers.new('Head follow','ARMATURE');mod.object=arm
  mod=ob.modifiers.new('Lock thickness','SOLIDIFY');mod.thickness=.00035;created.append(name)
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=20;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for name,d in [('front',(0,-1,0)),('rear',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
  sc.render.filepath=str(out/('head-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':manifest['files'][source.name],
  'new_locks':created,'hidden_previous_locks':hidden,'collection':col.name,'binding':'100% J_Bip_C_Head',
  'limitations':['Procedural reconstruction','Transparency and visual intersections require review','No animation or export validation']},indent=2),encoding='utf8')
