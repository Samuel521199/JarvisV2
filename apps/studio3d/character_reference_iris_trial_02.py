"""Reference-inspired procedural iris material; independent reversible trial."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/face-studio-adapter-test-01/draft.blend';expected='118d2ca638af3b02fa0d56467aeb4c81f7a624c453f2349559a0b7c0b75a7f17'
if hashlib.sha256(src.read_bytes()).hexdigest()!=expected:raise RuntimeError('Source changed')
out=ROOT/'user-data/artifacts/studio3d-character/reference-iris-study-02'
if out.exists():raise RuntimeError('Study already exists')
out.mkdir(parents=True)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 old=bpy.data.collections['Face_EyeDetails_Trial'];new=bpy.data.collections['Face_EyelinerLash_DesignTrial']
 old.hide_render=False;old.hide_viewport=False;new.hide_render=True;new.hide_viewport=True
 idx=next(i for i,m in enumerate(face.data.materials) if m and m.name=='reference-blue-iris-trial')
 mat=face.data.materials[idx].copy();mat.name='reference-iris-blue-gradient-study';face.data.materials[idx]=mat;nodes=mat.node_tree.nodes;links=mat.node_tree.links
 shader=next(n for n in nodes if n.type=='BSDF_PRINCIPLED');uv=nodes.new('ShaderNodeUVMap');uv.uv_map='JarvisAtlasUV';sep=nodes.new('ShaderNodeSeparateXYZ');links.new(uv.outputs['UV'],sep.inputs[0])
 def mathnode(op,a,b=None):
  n=nodes.new('ShaderNodeMath');n.operation=op
  for i,x in enumerate((a,b)):
   if x is None:continue
   if hasattr(x,'node'):links.new(x,n.inputs[i])
   else:n.inputs[i].default_value=x
  return n.outputs[0]
 def remap(x,a,b,c,d):
  n=nodes.new('ShaderNodeMapRange');n.clamp=True;links.new(x,n.inputs['Value']);n.inputs['From Min'].default_value=a;n.inputs['From Max'].default_value=b;n.inputs['To Min'].default_value=c;n.inputs['To Max'].default_value=d;return n.outputs['Result']
 u,v=sep.outputs['X'],sep.outputs['Y'];dl=mathnode('ABSOLUTE',mathnode('SUBTRACT',u,.3132));dr=mathnode('ABSOLUTE',mathnode('SUBTRACT',u,.4375));ux=mathnode('DIVIDE',mathnode('MINIMUM',dl,dr),.02685);vy=mathnode('DIVIDE',mathnode('SUBTRACT',v,.4365),.0305)
 ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1]);a=ramp.color_ramp.elements[0];a.position=0.;a.color=(.20,.65,.93,1)
 for pos,color in [(.30,(.055,.34,.68,1)),(.64,(.014,.14,.38,1)),(1.,(.004,.027,.09,1))]:ramp.color_ramp.elements.new(pos).color=color
 links.new(remap(vy,-1,1,0,1),ramp.inputs['Fac'])
 radius=mathnode('SQRT',mathnode('ADD',mathnode('MULTIPLY',ux,ux),mathnode('MULTIPLY',vy,vy)))
 outline=remap(radius,.80,1.0,0,.95);mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX';links.new(outline,mix.inputs[0]);links.new(ramp.outputs['Color'],mix.inputs[1]);mix.inputs[2].default_value=(.003,.012,.028,1)
 px=mathnode('DIVIDE',ux,.32);py=mathnode('DIVIDE',mathnode('SUBTRACT',vy,.14),.56);pr=mathnode('SQRT',mathnode('ADD',mathnode('MULTIPLY',px,px),mathnode('MULTIPLY',py,py)))
 pupil=remap(pr,.70,1.12,1,0);mix2=nodes.new('ShaderNodeMixRGB');links.new(pupil,mix2.inputs[0]);# Fine radial modulation in the iris; center/edge and pupil remain independent.
 closer=mathnode('LESS_THAN',u,.375);center_u=mathnode('ADD',.4375,mathnode('MULTIPLY',closer,-.1243))
 signed_u=mathnode('DIVIDE',mathnode('SUBTRACT',u,center_u),.02685)
 angle=mathnode('ARCTAN2',vy,signed_u);phase=mathnode('ADD',mathnode('MULTIPLY',angle,24.),mathnode('MULTIPLY',radius,2.))
 rays=mathnode('ADD',.88,mathnode('MULTIPLY',mathnode('SINE',phase),.12))
 rgb=nodes.new('ShaderNodeCombineColor')
 for channel in ('Red','Green','Blue'):links.new(rays,rgb.inputs[channel])
 grain=nodes.new('ShaderNodeMixRGB');grain.blend_type='MULTIPLY';grain.inputs[0].default_value=1.;links.new(mix.outputs[0],grain.inputs[1]);links.new(rgb.outputs[0],grain.inputs[2])
 links.new(grain.outputs[0],mix2.inputs[1]);mix2.inputs[2].default_value=(.002,.008,.022,1)
 # Controlled upper corneal highlight; existing highlight overlay is retained.
 hx=mathnode('DIVIDE',mathnode('ADD',signed_u,.18),.105);hy=mathnode('DIVIDE',mathnode('SUBTRACT',vy,.35),.095)
 hr=mathnode('SQRT',mathnode('ADD',mathnode('MULTIPLY',hx,hx),mathnode('MULTIPLY',hy,hy)))
 glint=remap(hr,.65,1.1,1.,0.);final=nodes.new('ShaderNodeMixRGB');links.new(glint,final.inputs[0]);links.new(mix2.outputs[0],final.inputs[1]);final.inputs[2].default_value=(.95,.98,1.,1)
 links.new(final.outputs[0],shader.inputs['Base Color']);shader.inputs['Roughness'].default_value=.34
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=32;sc.cycles.use_denoising=True;sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43));hair.hide_render=True
 for name,d in [('front',(0,-1,0)),('30-left',(-.5,-.8660254,0)),('side',(-1,0,0)),('side-right',(1,0,0))]:
  cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY '+name,flush=True)
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':expected,'iris_material':mat.name,'original_atlas_preserved':True,'hair_collection':hair.name,'old_lashes_enabled':old.name,'prior_new_lashes_disabled':new.name,'limits':['Procedural iris is approximate and UV dependent','Face, eyelids, nose and lips remain unapproved','No blink, eye rotation, export or rig animation test']},indent=2),encoding='utf8')
