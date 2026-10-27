import bpy,json,sys,hashlib,array,time
from pathlib import Path
root=Path(sys.argv[sys.argv.index('--')+1]);out=Path(sys.argv[sys.argv.index('--')+2])
def fingerprint():
 rows=[]
 for obj in sorted(bpy.context.scene.objects,key=lambda o:o.name):
  row={'name':obj.name,'type':obj.type,'parent':obj.parent.name if obj.parent else None,'matrix':[list(r) for r in obj.matrix_world]}
  if obj.type=='MESH':
   a=array.array('f',[0])*len(obj.data.vertices)*3;obj.data.vertices.foreach_get('co',a)
   row['vertices']=hashlib.sha256(a.tobytes()).hexdigest();row['faces']=hashlib.sha256(json.dumps([list(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()
   row['materials']=[m.name if m else None for m in obj.data.materials]
   row['uv']={}
   for uv in obj.data.uv_layers:
    a=array.array('f',[0])*len(uv.data)*2;uv.data.foreach_get('uv',a);row['uv'][uv.name]=hashlib.sha256(a.tobytes()).hexdigest()
  rows.append(row)
 actions=[{'name':a.name,'range':list(a.frame_range)} for a in bpy.data.actions]
 return {'scene':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),'actions':actions,'mesh_objects':sum(o.type=='MESH' for o in bpy.context.scene.objects)}
reports=[]
for source,dest,author in [('model.blend','leFH18-editable.blend',True),('model-pbr.blend','leFH18-high.blend',False)]:
 tick=time.monotonic()
 bpy.ops.wm.open_mainfile(filepath=str(root/'delivery/high-r7'/source),load_ui=False,use_scripts=False)
 before=fingerprint();assert not bpy.data.libraries
 image_before={im.name:hashlib.sha256(im.packed_file.data).hexdigest() for im in bpy.data.images if im.packed_file}
 for im in bpy.data.images:
  if im.type in {'RENDER_RESULT','COMPOSITING'}:continue
  assert im.packed_file,('Unpacked image',im.name)
  if author:
   relative=Path('textures/source')/Path(im.filepath).name;target=root/relative;target.parent.mkdir(exist_ok=True)
   target.write_bytes(im.packed_file.data)
  else:
   matches=list((root/'textures').glob(im.name+'.*'));assert len(matches)==1,(im.name,matches);relative=matches[0].relative_to(root)
  im.filepath='//'+relative.as_posix()
 bpy.context.scene.render.filepath='//renders/leFH18-'
 bpy.context.preferences.filepaths.save_version=0
 bpy.ops.file.pack_all()
 bpy.ops.wm.save_as_mainfile(filepath=str(root/dest),compress=True,relative_remap=False)
 bpy.ops.wm.open_mainfile(filepath=str(root/dest),load_ui=False,use_scripts=False)
 after=fingerprint();assert before==after,(source,before,after)
 assert image_before=={im.name:hashlib.sha256(im.packed_file.data).hexdigest() for im in bpy.data.images if im.packed_file}
 images=[{'name':im.name,'packed':bool(im.packed_file),'relative_path':im.filepath,'external_exists':Path(bpy.path.abspath(im.filepath)).is_file()} for im in bpy.data.images if im.type not in {'RENDER_RESULT','COMPOSITING'}]
 print('IMAGE_CHECK',json.dumps(images),flush=True)
 assert all(x['packed'] and x['relative_path'].replace(chr(92),'/').startswith('//textures/') and x['external_exists'] for x in images)
 reports.append({'source':source,'destination':dest,'elapsed_seconds':time.monotonic()-tick,'geometry_uv_hierarchy_unchanged':before==after,'packed_image_bytes_unchanged':True,'inventory':after,'images':images,'sha256':hashlib.sha256((root/dest).read_bytes()).hexdigest()})
out.write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
