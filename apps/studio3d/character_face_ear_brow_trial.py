"""Reversible ear and brow study on the mature-face experiment."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from control.studio3d_lane import render_lane
src=ROOT/'user-data/artifacts/studio3d-character/face-proportion-design-study-01/candidate.blend';identity=hashlib.sha256(src.read_bytes()).hexdigest()
out=ROOT/'user-data/artifacts/studio3d-character/face-proportion-design-study-02'
if out.exists():raise ValueError('Existing candidate')
out.mkdir(parents=True)
def sm(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
with render_lane(out):
 bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 face=bpy.data.objects['Face'];hair=bpy.data.collections['Hair_SilverHair_Replaceable_01']
 key=face.shape_key_add(name='DesignEarAndNoseStudy',from_mix=False);m=face.matrix_world;inv=m.inverted();n=0
 for v in key.data:
  p=m@v.co;x=abs(p.x);sgn=1 if p.x>=0 else -1
  # Reduce peripheral ear mass gently towards the head without shrinking eye area.
  ear=sm(.075,.096,x)*sm(1.405,1.425,p.z)*(1-sm(1.467,1.486,p.z))*sm(-.040,-.015,p.y)
  p.x-=sgn*.005*ear;p.z=1.445+(p.z-1.445)*(1-.12*ear)
  # A small reduction in nose-tip projection; avoid broad facial movement.
  nose=(1-sm(.006,.018,x))*sm(1.394,1.405,p.z)*(1-sm(1.415,1.427,p.z))*(1-sm(-.083,-.070,p.y))
  p.y+=.0012*nose
  if ear+nose>1e-7:v.co=inv@p;n+=1
 key.value=1.
 idx=next(i for i,mat in enumerate(face.data.materials) if 'FaceBrow_00_FACE'.lower() in mat.name.lower())
 mat=face.data.materials[idx].copy();mat.name='reference-soft-ash-brow-trial';face.data.materials[idx]=mat
 shader=next(node for node in mat.node_tree.nodes if node.type=='BSDF_PRINCIPLED')
 link=shader.inputs['Base Color'].links[0].from_socket
 color=mat.node_tree.nodes.new('ShaderNodeHueSaturation');color.inputs['Saturation'].default_value=.16;color.inputs['Value'].default_value=.85
 mat.node_tree.links.new(link,color.inputs['Color']);mat.node_tree.links.new(color.outputs['Color'],shader.inputs['Base Color'])
 bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(out/'candidate.blend'),check_existing=False)
 sc=bpy.context.scene;cam=sc.camera;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=24;sc.cycles.use_denoising=True
 sc.render.resolution_x=sc.render.resolution_y=768;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG'
 cam.data.type='ORTHO';cam.data.ortho_scale=.34;center=Vector((0,0,1.43))
 for mode in ('bald','hair'):
  hair.hide_render=mode=='bald'
  for name,d in [('front',(0,-1,0)),('45-left',(-.7071,-.7071,0)),('left',(-1,0,0))]:
   cam.location=center+Vector(d)*5;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
   sc.render.filepath=str(out/(mode+'-'+name+'.png'));bpy.ops.render.render(write_still=True);print('RENDER_READY',mode,name,flush=True)
 hair.hide_render=False
 (out/'report.json').write_text(json.dumps({'status':'EXPERIMENTAL_NOT_ACCEPTED','source_sha256':identity,'shape_key':key.name,'affected_vertices':n,'brow_material':mat.name,'limitations':['Approximate sculpt, not user-approved','Static renders only','Eyelid and blink deformation not tested']},indent=2),encoding='utf8')
