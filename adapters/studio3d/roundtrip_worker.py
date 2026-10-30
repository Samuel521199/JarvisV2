# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only, receipt-bound comparison of BLEND and its actual GLB export."""
import hashlib,json,sys,time
from pathlib import Path
import bpy
from adapters.studio3d.inspection_worker import render_scene
from modules.skills.studio3d.render_inspection import validate


def geometry(objects):
    deps=bpy.context.evaluated_depsgraph_get();result={}
    for name,obj in objects.items():
        evaluated=obj.evaluated_get(deps);mesh=bpy.data.meshes.new_from_object(evaluated,depsgraph=deps)
        points=[obj.matrix_world@v.co for v in mesh.vertices];mesh.calc_loop_triangles()
        result[name]={'bounds':[[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]],
                      'triangles':len(mesh.loop_triangles),'materials':[slot.material.name if slot.material else None for slot in obj.material_slots]}
        bpy.data.meshes.remove(mesh)
    return result


def main():
    folder=Path(sys.argv[sys.argv.index('--')+1]);request=json.loads((folder/'request.json').read_text(encoding='utf-8'));start=time.monotonic()
    for name,key in [('source.blend','source_sha256'),('source.glb','source_glb_sha256')]:
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=request[key]:raise ValueError('Source changed')
    c=validate(request['contract'],request['visible_names'])
    bpy.ops.wm.open_mainfile(filepath=str(folder/'source.blend'),load_ui=False,use_scripts=False)
    original={n:bpy.data.objects.get(n) for n in request['visible_names']}
    if any(o is None or o.type not in ('MESH','CURVE') for o in original.values()):raise ValueError('Source inventory changed')
    before=geometry(original);native=render_scene(folder,c,original,prefix='native')
    for name,obj in original.items():obj.name='roundtrip-original-'+name;obj.hide_render=True
    existing=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(folder/'source.glb'))
    imported={o.name:o for o in set(bpy.data.objects)-existing if o.type=='MESH'}
    if set(imported)!=set(original):raise ValueError('Reimport object identities differ from native inventory')
    after=geometry(imported)
    errors={n:max(abs(before[n]['bounds'][j][i]-after[n]['bounds'][j][i]) for i in range(3) for j in range(2)) for n in original}
    triangle_changes={n:[before[n]['triangles'],after[n]['triangles']] for n in original if before[n]['triangles']!=after[n]['triangles']}
    glb=render_scene(folder,c,imported,prefix='glb')
    passed=max(errors.values())<=1e-5 and not triangle_changes
    report={'version':'1.0.0','source_sha256':request['source_sha256'],'source_glb_sha256':request['source_glb_sha256'],
            'source_operation':request['source_operation'],'source_job':request['source_job'],'native':native,'glb':glb,
            'geometry_checks':{'passed':passed,'matched_objects':len(imported),'maximum_bounds_error':max(errors.values()),'per_object_bounds_error':errors,'triangle_changes':triangle_changes},
            'before_inventory':before,'after_inventory':after,'source_unchanged':all(hashlib.sha256((folder/name).read_bytes()).hexdigest()==request[key] for name,key in [('source.blend','source_sha256'),('source.glb','source_glb_sha256')]),
            'render_comparison':'AWAITING_VISUAL_REVIEW','full_material_equivalence':False,'collision_and_animation':'NOT_TESTED','user_approval':False,'lod_authorized':False,'elapsed_seconds':time.monotonic()-start}
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if not passed:raise ValueError('GLB reimport geometry differs; retained report and images')


if __name__=='__main__':main()
