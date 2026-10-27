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
expected={v['destination']:v for v in json.loads((out.parent/'packed-blend-verification.json').read_text(encoding='utf8'))}
for name in ['leFH18-high.blend','leFH18-editable.blend']:
 tick=time.monotonic()
 bpy.ops.wm.open_mainfile(filepath=str(root/name),load_ui=False,use_scripts=False)
 current=fingerprint()
 assert current==expected[name]['inventory'],name
 assert not bpy.data.libraries
 images=[]
 for im in bpy.data.images:
  if im.type in {'RENDER_RESULT','COMPOSITING'}: continue
  target=Path(bpy.path.abspath(im.filepath)).resolve()
  assert target.is_relative_to(root.resolve()) and target.is_file(),(name,im.name,target)
  assert im.packed_file and hashlib.sha256(target.read_bytes()).hexdigest()==hashlib.sha256(im.packed_file.data).hexdigest(),(name,im.name)
  images.append({'name':im.name,'path':im.filepath,'packed':True,'external_bytes_match':True})
 reports.append({'file':name,'inventory_matches':True,'external_libraries':0,'images':images,'elapsed_seconds':time.monotonic()-tick})
out.write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
print('FINAL_PACKAGE_VERIFIED',json.dumps([{'file':r['file'],'images':len(r['images'])} for r in reports]))
