import bpy,json,sys,hashlib
from pathlib import Path
root=Path(sys.argv[sys.argv.index('--')+1]);output=Path(sys.argv[sys.argv.index('--')+2]);report=[]
for name in ('model.blend','model-pbr.blend'):
 path=root/'delivery/high-r7'/name
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
 images=[]
 for im in bpy.data.images:
  if im.type in {'RENDER_RESULT','COMPOSITING'}:continue
  filepath=bpy.path.abspath(im.filepath) if im.filepath else None
  images.append({'name':im.name,'source':im.source,'packed':bool(im.packed_file or im.packed_files),'path':filepath,'exists':bool(filepath and Path(filepath).is_file()),'size':list(im.size),'users':im.users})
 report.append({'file':name,'images':images,'libraries':[l.filepath for l in bpy.data.libraries],'fonts':[f.filepath for f in bpy.data.fonts if f.filepath!='<builtin>'],'mesh_objects':sum(o.type=='MESH' for o in bpy.context.scene.objects),'actions':[a.name for a in bpy.data.actions]})
output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
