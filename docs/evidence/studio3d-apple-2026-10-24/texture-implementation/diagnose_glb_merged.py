import bpy,json,sys
from pathlib import Path
root=Path('D:/Jarvis');out=root/'docs/evidence/studio3d-apple-2026-10-24/texture-implementation'
bpy.ops.wm.open_mainfile(filepath=str(root/'user-data/artifacts/studio3d/417ecb2c747f4435b32a8bb7d478320e/model.blend'),load_ui=False,use_scripts=False)
for obj in list(bpy.context.scene.objects):
    if obj.type not in ('LIGHT','CAMERA') and obj.name!='Studio floor':bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(root/'user-data/artifacts/studio3d/417ecb2c747f4435b32a8bb7d478320e/model.glb'),merge_vertices=True)
parts=[o for o in bpy.context.selected_objects if o.type=='MESH'];materials=set(m for o in parts for m in o.data.materials)
nodes={m.name:{'nodes':[(n.name,n.type) for n in m.node_tree.nodes],'links':[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in m.node_tree.links]} for m in materials}
(out/'glb-material-nodes-merged.json').write_text(json.dumps(nodes,indent=2))
s=bpy.context.scene;s.cycles.samples=16;s.render.resolution_x=s.render.resolution_y=640
for mode in ('pbr','no-normal','base'):
    for m in materials:
        n=m.node_tree.nodes;links=m.node_tree.links;p=next(x for x in n if x.type=='BSDF_PRINCIPLED')
        if mode=='no-normal':
            for link in list(p.inputs['Normal'].links):links.remove(link)
        if mode=='base':
            emit=n.new('ShaderNodeEmission');links.new(p.inputs['Base Color'].links[0].from_socket,emit.inputs['Color']);output=next(x for x in n if x.type=='OUTPUT_MATERIAL');links.new(emit.outputs[0],output.inputs['Surface'])
    s.render.filepath=str(out/('diagnose-merged-'+mode+'.png'));bpy.ops.render.render(write_still=True)
