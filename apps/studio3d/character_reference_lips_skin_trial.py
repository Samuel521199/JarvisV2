"""Skin-attached procedural lip color study; no floating lip mesh."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/reference-iris-study-03/candidate.blend';out=ROOT/'user-data/artifacts/studio3d-character/reference-lips-skin-study-01'
if out.exists():raise ValueError('Existing study requires inspection')
identity=hashlib.sha256(src.read_bytes()).hexdigest();out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01'];dg=bpy.context.evaluated_depsgraph_get();ev=face.evaluated_get(dg);me=ev.to_mesh();pts=[ev.matrix_world@v.co for v in me.vertices];ev.to_mesh_clear()
 if len(pts)!=len(face.data.vertices):raise ValueError('Cannot map evaluated topology')
 if face.data.uv_layers.get('ReferenceLipsProjection'):raise ValueError('Projection exists')
 uv=face.data.uv_layers.new(name='ReferenceLipsProjection')
 for poly in face.data.polygons:
  for li in poly.loop_indices:
   p=pts[face.data.loops[li].vertex_index];uv.data[li].uv=(.5+p.x/.040,.5+(p.z-1.3788)/.025)
 idx=next(i for i,m in enumerate(face.data.materials) if m and 'Face_00_SKIN' in m.name)
 mat=face.data.materials[idx].copy();mat.name='reference-soft-lips-skin-study';face.data.materials[idx]=mat;nodes=mat.node_tree.nodes;links=mat.node_tree.links
 shader=next(n for n in nodes if n.type=='BSDF_PRINCIPLED');previous=shader.inputs['Base Color'].links[0].from_socket
 uvnode=nodes.new('ShaderNodeUVMap');uvnode.uv_map='ReferenceLipsProjection';sep=nodes.new('ShaderNodeSeparateXYZ');links.new(uvnode.outputs['UV'],sep.inputs[0])
 def M(op,a,b=None):
  n=nodes.new('ShaderNodeMath');n.operation=op
  for i,x in enumerate((a,b)):
   if x is None:continue
   if hasattr(x,'node'):links.new(x,n.inputs[i])
   else:n.inputs[i].default_value=x
  return n.outputs[0]
 def remap(x,a,b,c,d):
  n=nodes.new('ShaderNodeMapRange');n.clamp=True;links.new(x,n.inputs['Value']);
  for key,value in [('From Min',a),('From Max',b),('To Min',c),('To Max',d)]:n.inputs[key].default_value=value
  return n.outputs['Result']
 def gauss(x,center,width):
  z=M('DIVIDE',M('SUBTRACT',x,center),width);return M('EXPONENT',M('MULTIPLY',-1,M('MULTIPLY',z,z)))
 x=M('ABSOLUTE',M('DIVIDE',M('SUBTRACT',sep.outputs['X'],.5),.36));edge=remap(x,.65,1.,1.,0.)
 bow=M('SUBTRACT',M('MULTIPLY',.027,gauss(x,.38,.22)),M('MULTIPLY',.018,x));v=M('SUBTRACT',M('SUBTRACT',sep.outputs['Y'],.5),bow)
 upper=M('MULTIPLY',M('MULTIPLY',gauss(v,.035,.065),edge),.30);lower=M('MULTIPLY',M('MULTIPLY',gauss(v,-.04,.075),edge),.16)
 lip=nodes.new('ShaderNodeMixRGB');lip.blend_type='MIX';links.new(M('ADD',upper,lower),lip.inputs[0]);links.new(previous,lip.inputs[1]);lip.inputs[2].default_value=(.64,.29,.25,1)
 line=M('MULTIPLY',M('MULTIPLY',gauss(v,0.,.009),edge),.60);mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX';links.new(line,mix.inputs[0]);links.new(lip.outputs[0],mix.inputs[1]);mix.inputs[2].default_value=(.30,.095,.075,1);links.new(mix.outputs[0],shader.inputs['Base Color'])
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=32;sc.cycles.use_denoising=True;sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));hair.hide_render=True
 for name,d in [('front',(0,-1,0)),('30-left',(-.5,-.8660254,0)),('side',(-1,0,0)),('side-right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,'new_uv':'ReferenceLipsProjection','material':mat.name,'no_new_lip_mesh':True,'limitations':['Shader trial, not lip retopology','Face shape and lid shape still unapproved','Motion and export not tested']},indent=2),encoding='utf8')
