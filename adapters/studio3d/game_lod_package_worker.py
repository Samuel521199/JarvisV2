from sdk.blender_api import require_blender
# SPDX-License-Identifier: GPL-2.0-or-later
import json,hashlib,sys
from pathlib import Path
bpy = require_blender().bpy
Vector = require_blender().mathutils.Vector
def main():
 folder=Path(sys.argv[-1]);request=json.loads((folder/'request.json').read_text());rows=request['levels']
 if [r['level'] for r in rows]!=list(range(4)):raise ValueError('Four explicit LOD levels required')
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;report=[]
 for row in rows:
  path=folder/('lod'+str(row['level'])+'.glb')
  if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('LOD file changed')
  bpy.ops.import_scene.gltf(filepath=str(path));members=list(bpy.context.selected_objects);collection=bpy.data.collections.new('LOD'+str(row['level']));scene.collection.children.link(collection)
  meshes=[o for o in members if o.type=='MESH']
  for obj in members:
   for old in list(obj.users_collection):old.objects.unlink(obj)
   collection.objects.link(obj)
   obj.name='LOD'+str(row['level'])+'__'+obj.name
  for obj in meshes:obj.data.calc_loop_triangles()
  count=sum(len(o.data.loop_triangles) for o in meshes)
  if count!=row['triangles'] or len(meshes)!=row.get('parts',11):raise ValueError('Package geometry differs')
  if any(len(p.vertices)!=3 for ob in meshes for p in ob.data.polygons):raise ValueError('Package must contain only triangles')
  collection.hide_render=row['level']!=0;collection.hide_viewport=row['level']!=0
  report.append({'level':row['level'],'triangles':count,'objects':len(meshes),'sha256':row['sha256']})
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':area.spaces.active.region_3d.view_distance=9;area.spaces.active.region_3d.view_location=Vector((0,0,.5))
 scene['PaK38_LOD_README']='Four independent triangle-only game LOD collections. LOD0 visible; enable exactly one collection at a time. See level reports for projection or silhouette bake method, and evidence/authorization.json for the preserved high source. No new rig or engine performance certification.'
 bpy.ops.wm.save_as_mainfile(filepath=str(folder/'PaK38_Game_LOD0-3.blend'),compress=True,check_existing=False)
 bpy.ops.wm.open_mainfile(filepath=str(folder/'PaK38_Game_LOD0-3.blend'),load_ui=False,use_scripts=False)
 combined=[o for o in bpy.context.scene.objects if o.type=='MESH']
 if any(len(p.vertices)!=3 for o in combined for p in o.data.polygons):raise ValueError('Saved combined BLEND contains a non-triangle')
 if sum(len(o.data.polygons) for o in combined)!=sum(r['triangles'] for r in rows):raise ValueError('Saved combined BLEND triangle count differs')
 saved_levels=[]
 if request.get('clean_level_blends'):
  for row in rows:
   bpy.ops.wm.read_factory_settings(use_empty=True)
   bpy.ops.import_scene.gltf(filepath=str(folder/('lod'+str(row['level'])+'.glb')))
   meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
   if any(len(p.vertices)!=3 for o in meshes for p in o.data.polygons):raise ValueError('Clean single-level BLEND contains a non-triangle')
   if sum(len(o.data.polygons) for o in meshes)!=row['triangles']:raise ValueError('Clean single-level triangle count mismatch')
   bpy.ops.wm.save_as_mainfile(filepath=str(folder/('LOD'+str(row['level'])+'.blend')),compress=True,check_existing=False)
   bpy.ops.wm.open_mainfile(filepath=str(folder/('LOD'+str(row['level'])+'.blend')),load_ui=False,use_scripts=False)
   loaded=[o for o in bpy.context.scene.objects if o.type=='MESH']
   if any(len(p.vertices)!=3 for o in loaded for p in o.data.polygons) or sum(len(o.data.polygons) for o in loaded)!=row['triangles']:raise ValueError('Saved clean BLEND is not triangle-only')
   saved_levels.append({'level':row['level'],'triangle_polygons':sum(len(o.data.polygons) for o in loaded),'quad_polygons':0,'ngons':0})
 (folder/'report.json').write_text(json.dumps({'levels':report,'active_level':0,'shared_geometry_mutation':False,'actual_saved_triangle_polygons_checked':True,'saved_total_triangles':sum(r['triangles'] for r in rows),'saved_clean_levels':saved_levels},indent=2))
