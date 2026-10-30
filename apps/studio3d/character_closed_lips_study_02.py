"""Reference-guided closed-lip patch trial: editable, non-destructive copy."""
import hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/face-nose-lips-study-02/candidate.blend';identity=hashlib.sha256(src.read_bytes()).hexdigest()
out=ROOT/'user-data/artifacts/studio3d-character/closed-lips-design-study-02'
if out.exists():raise ValueError('Existing trial requires review')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];arm=bpy.data.objects['Armature'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 previous=bpy.data.collections['Face_Lips_Trial'];previous.hide_render=True;previous.hide_viewport=True
 col=bpy.data.collections.new('Face_ClosedLips_DesignTrial');bpy.context.scene.collection.children.link(col)
 bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();ev=face.evaluated_get(deps);im=ev.matrix_world.inverted();mesh=ev.to_mesh();uv=mesh.uv_layers['JarvisAtlasUV'].data
 pose=arm.pose.bones['J_Bip_C_Head'];bone=arm.data.bones['J_Bip_C_Head'];deform=arm.matrix_world@pose.matrix@bone.matrix_local.inverted()@arm.matrix_world.inverted();bind_inverse=deform.inverted()
 def sample(x,z):
  hit,p,_,idx=ev.ray_cast(im@Vector((x,-.30,z)),im.to_3x3()@Vector((0,1,0)))
  if not hit:raise RuntimeError('Face ray missed')
  poly=mesh.polygons[idx]
  if poly.material_index!=3 or len(poly.loop_indices)!=3:raise RuntimeError('Unexpected skin topology')
  loops=list(poly.loop_indices);v=[mesh.vertices[mesh.loops[i].vertex_index].co for i in loops]
  u=[Vector((uv[i].uv.x,uv[i].uv.y,0)) for i in loops]
  tex=barycentric_transform(p,*v,*u)
  return ev.matrix_world@p,Vector((tex.x,tex.y))
 cols=49;rows=13;width=.0142;seam_z=1.3788;verts=[];uvs=[];faces=[];anchors=[]
 for i in range(cols):
  u=2*i/(cols-1)-1;x=width*u;edge=max(.0001,1-u*u)**.55
  upper,ut=sample(x,seam_z+.0045*edge);lower,lt=sample(x,seam_z-.0045*edge)
  anchors.append((u,x,edge,upper,lower,ut,lt))
 for j in range(rows):
  t=j/(rows-1)
  for u,x,edge,upper,lower,ut,lt in anchors:
   p=upper.lerp(lower,t);p.y-=.00055*math.sin(math.pi*t)+.00008
   verts.append(tuple(bind_inverse@p));uvs.append(tuple(ut.lerp(lt,t)))
 for j in range(rows-1):
  for i in range(cols-1):
   n=j*cols+i;faces.append((n,n+1,n+cols+1,n+cols))
 patch=bpy.data.meshes.new('closed-lip-skin-bridge');patch.from_pydata(verts,[],faces);patch.update();ob=bpy.data.objects.new('closed-lip-skin-bridge',patch);col.objects.link(ob);patch.materials.append(face.data.materials[3]);layer=patch.uv_layers.new(name='JarvisAtlasUV')
 for poly in patch.polygons:
  poly.use_smooth=True
  for li in poly.loop_indices:layer.data[li].uv=uvs[patch.loops[li].vertex_index]
 def bind(o):
  g=o.vertex_groups.new(name='J_Bip_C_Head');g.add(list(range(len(o.data.vertices))),1.,'REPLACE');mod=o.modifiers.new('Head follow','ARMATURE');mod.object=arm
 bind(ob)
 # Subtle tonal lip surface with per-vertex transparency fading to the skin.
 lipmesh=patch.copy();lipmesh.name='closed-lip-soft-color';lip=bpy.data.objects.new('closed-lip-soft-color',lipmesh);col.objects.link(lip);lipmesh.materials.clear()
 color=lipmesh.color_attributes.new(name='LipFade',type='FLOAT_COLOR',domain='CORNER')
 for poly in lipmesh.polygons:
  for li in poly.loop_indices:
   vi=lipmesh.loops[li].vertex_index;j=vi//cols;i=vi%cols;u=2*i/(cols-1)-1;t=j/(rows-1)
   alpha=.10*(max(0.,1-u*u)**1.2)*(max(0.,math.sin(math.pi*t))**1.2)
   color.data[li].color=(alpha,alpha,alpha,1)
 for v in lipmesh.vertices:v.co.y-=.00008
 mat=bpy.data.materials.new('closed-lip-rose-soft-trial');mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear()
 output=nodes.new('ShaderNodeOutputMaterial');mix=nodes.new('ShaderNodeMixShader');trans=nodes.new('ShaderNodeBsdfTransparent');shader=nodes.new('ShaderNodeBsdfPrincipled');attr=nodes.new('ShaderNodeVertexColor');attr.layer_name='LipFade'
 shader.inputs['Base Color'].default_value=(.65,.32,.29,1);shader.inputs['Roughness'].default_value=.66
 links=mat.node_tree.links;links.new(attr.outputs['Color'],mix.inputs[0]);links.new(trans.outputs['BSDF'],mix.inputs[1]);links.new(shader.outputs['BSDF'],mix.inputs[2]);links.new(mix.outputs[0],output.inputs['Surface']);lipmesh.materials.append(mat);bind(lip)
 # Narrow softly tapered line: shallow cupid bow with lower outer corners.
 seam_mat=bpy.data.materials.new('closed-lip-line-trial');seam_mat.diffuse_color=(.34,.13,.12,1);seam_mat.use_nodes=True;p=next(n for n in seam_mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');p.inputs['Base Color'].default_value=(.34,.13,.12,1);p.inputs['Roughness'].default_value=.7
 curve=bpy.data.curves.new('closed-lip-line','CURVE');curve.dimensions='3D';curve.resolution_u=12;curve.bevel_depth=.00012;curve.bevel_resolution=3;spline=curve.splines.new('POLY');spline.points.add(cols-1)
 for i,(u,x,edge,upper,lower,ut,lt) in enumerate(anchors):
  bow=.00042*math.exp(-((abs(u)-.38)/.25)**2)-.00030*abs(u)**1.5
  t=max(0.,min(1.,.5-bow/(.009*edge))) if edge>.001 else .5
  q=upper.lerp(lower,t);q.y-=.00068;q=bind_inverse@q;spline.points[i].co=(*q,1);spline.points[i].radius=max(.05,edge)
 curve.materials.append(seam_mat);line=bpy.data.objects.new('closed-lip-line',curve);col.objects.link(line)
 bpy.ops.object.select_all(action='DESELECT');line.select_set(True);bpy.context.view_layer.objects.active=line;bpy.ops.object.convert(target='MESH');line=bpy.context.object;bind(line)
 ev.to_mesh_clear();bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=40;sc.cycles.use_denoising=True;sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));hair.hide_render=True
 for name,d in [('front',(0,-1,0)),('30-left',(-.5,-.8660254,0)),('side',(-1,0,0)),('side-right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,'old_lips_hidden':previous.name,'trial_collection':col.name,'elements':[ob.name,lip.name,line.name],'limits':['Surface bridge and accents, not full mouth topology','Static view only','Lip closure, face animation, speaking and export unverified']},indent=2),encoding='utf8')
