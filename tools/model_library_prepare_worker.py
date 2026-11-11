# SPDX-License-Identifier: GPL-2.0-or-later
"""Fixed library extraction/preview recipe. Originals are never saved over."""
import bpy,json,hashlib,sys,math,time
from pathlib import Path
from mathutils import Vector

def main(folder):
 req=json.loads((folder/'request.json').read_text());rows=[];start=time.monotonic()
 def check(path,sha):
  path=Path(path)
  if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('Library source changed')
  return path
 def select(obs):
  bpy.ops.object.select_all(action='DESELECT')
  for o in obs:o.hide_set(False);o.select_set(True)
  bpy.context.view_layer.objects.active=obs[0]
 def export(path,obs):
  select(obs);bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_cameras=False,export_lights=False)
 def count(obs):
  for ob in obs:ob.data.calc_loop_triangles()
  return sum(len(o.data.loop_triangles) for o in obs)
 def cover(name,obs):
  from adapters.studio3d.assembly_worker import lighting,camera_render
  for ob in bpy.context.scene.objects:
   if ob.type=='MESH':ob.hide_render=ob not in obs
  lighting(5);camera_render(folder,name,obs,(1,-2,1.1),size=(640,480))
 def preview(name,obs,budget):
  total=count(obs);copied=[]
  for ob in obs:
   clone=ob.copy();clone.data=ob.data.copy();bpy.context.scene.collection.objects.link(clone);clone.name='Library preview '+ob.name;clone.hide_render=False;clone.hide_set(False);select([clone]);n=count([clone]);target=max(24,int(budget*n/total))
   if n>target:
    mod=clone.modifiers.new('Library display approximation','DECIMATE');mod.ratio=target/n;mod.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=mod.name)
   copied.append(clone)
  export(folder/(name+'.glb'),copied);cover(name,copied);rows.append({'id':name,'triangles':count(copied),'source_triangles':total,'kind':'display preview, original UV approximated; not game-certified'})
  for ob in copied:bpy.data.objects.remove(ob,do_unlink=True)
 for source in req['sources']:
  path=check(source['path'],source['sha256']);bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
  if source['id']=='tank':
   groups={name:[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith(name+'__mesh_')] for name in ['hull','turret','gun','mantlet','track_left','headlamp']}
   if any(not x for x in groups.values()):raise ValueError('Expected tank component inventory missing')
   all_parts=[o for o in bpy.context.scene.objects if o.type=='MESH' and '__mesh_' in o.name and not o.hide_render]
   for name,obs in groups.items():export(folder/('tank-'+name+'-original.glb'),obs)
   for i,im in enumerate(list(bpy.data.images)):
    if im.type=='IMAGE' and im.size[0] and max(im.size)>1024:
     im.scale(1024,1024);im.filepath_raw=str(folder/('display-image-'+str(i)+'.png'));im.file_format='PNG';im.save();im.pack()
   preview('tank-display',all_parts,200000)
   for name,obs in groups.items():preview('tank-'+name,obs,80000 if count(obs)>80000 else count(obs))
  elif source['id']=='pak':
   for name in ['wheel-left','shield','barrel','trail-left']:
    ob=bpy.data.objects.get(name)
    if ob is None or ob.type!='MESH':raise ValueError('Expected current PaK38 mapped group missing')
    export(folder/('pak-'+name+'.glb'),[ob]);cover('pak-'+name,[ob]);rows.append({'id':'pak-'+name,'triangles':count([ob]),'kind':'unchanged current high group extracted, original transform retained'})
  if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Original unexpectedly changed')
 (folder/'report.json').write_text(json.dumps({'outputs':rows,'sources_unchanged':True,'model_calls':0,'api_usd':0,'elapsed_seconds':time.monotonic()-start,'limits':'Preview decimation is for browsing only; original geometry, rigs and files remain available. No new game acceptance.'},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
 from control.studio3d_lane import render_lane
 folder=Path(sys.argv[-1])
 with render_lane(folder):main(folder)
