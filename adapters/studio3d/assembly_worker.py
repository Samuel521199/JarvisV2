# SPDX-License-Identifier: GPL-2.0-or-later
"""Fixed Blender assembly of admitted meshes; geometry/UV/images remain untouched."""
import hashlib,json,math,time
import bpy
from mathutils import Vector
from modules.skills.studio3d.assembly_contract import validate


def bounds(objects):
    points=[o.matrix_world@Vector(v) for o in objects if o.type=='MESH' for v in o.bound_box]
    return Vector([min(v[i] for v in points) for i in range(3)]),Vector([max(v[i] for v in points) for i in range(3)])


def camera_render(folder,name,objects,direction,ortho=True,size=(1200,800)):
    s=bpy.context.scene;lo,hi=bounds(objects);center=(lo+hi)/2;span=max(hi-lo);cam=s.camera
    cam.location=center+Vector(direction).normalized()*span*2.5
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO' if ortho else 'PERSP';cam.data.lens=52;cam.data.sensor_fit='HORIZONTAL'
    bpy.context.view_layer.update();inv=cam.matrix_world.inverted();points=[inv@(o.matrix_world@Vector(v)) for o in objects for v in o.bound_box]
    width=max(p.x for p in points)-min(p.x for p in points);height=max(p.y for p in points)-min(p.y for p in points)
    cam.data.ortho_scale=max(width,height*size[0]/size[1])*1.14;cam.data.clip_start=.001;cam.data.clip_end=1000
    s.render.resolution_x,s.render.resolution_y=size;s.render.filepath=str(folder/(name+'.png'));bpy.ops.render.render(write_still=True)


def lighting(span):
    s=bpy.context.scene;s.world=bpy.data.worlds.new('Assembly studio');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.35,.39,.46,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.5
    for name,pos,power,size in [('Key',(-1.2,-1.8,2.4),1800,1.4),('Fill',(1.8,-.3,1.5),1100,1.8),('Rim',(.2,1.8,2.4),1800,1.2)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power*(span/4)**2;data.shape='DISK';data.size=span*size
        o=bpy.data.objects.new(name,data);s.collection.objects.link(o);o.location=Vector(pos)*span;o.rotation_euler=(Vector((0,0,span*.2))-o.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('Review camera');cam=bpy.data.objects.new('Review camera',data);s.collection.objects.link(cam);s.camera=cam
    available={x.identifier for x in s.render.bl_rna.properties['engine'].enum_items};s.render.engine='BLENDER_EEVEE' if 'BLENDER_EEVEE' in available else 'BLENDER_EEVEE_NEXT';s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA';s.render.film_transparent=False;s.view_settings.view_transform='AgX';s.render.resolution_percentage=100


def main(folder):
    req=json.loads((folder/'request.json').read_text(encoding='utf-8'));cfg=validate(req['contract']);s=bpy.context.scene
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    source_objects={};inventory={};start=time.monotonic()
    for key,info in req['sources'].items():
        p=folder/(key+'.glb')
        if hashlib.sha256(p.read_bytes()).hexdigest()!=info['sha256']:raise ValueError('Source hash mismatch')
        prior=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(p));items=[o for o in set(bpy.data.objects)-prior if o.type=='MESH']
        if not items:raise ValueError('No meshes imported')
        bpy.context.view_layer.update();lo,hi=bounds(items);source_objects[key]=items
        inventory[key]={'bounds':[list(lo),list(hi)],'dimensions':list(hi-lo),'triangles':sum(len(o.data.polygons) for o in items),'vertices':sum(len(o.data.vertices) for o in items),'uv_layers':[len(o.data.uv_layers) for o in items],'images':[]}
        for o in items:o.name=key+'__'+o.name
        print('IMPORTED '+key,flush=True)
    for im in bpy.data.images:
        if im.type=='IMAGE' and im.size[0]:
            for key,items in source_objects.items():
                if any(node.type=='TEX_IMAGE' and node.image==im for o in items for mat in o.data.materials if mat and mat.use_nodes for node in mat.node_tree.nodes):inventory[key]['images'].append({'name':im.name,'size':list(im.size),'colorspace':im.colorspace_settings.name})
    if cfg['mode']=='inspect':
        lighting(1)
        for key,items in source_objects.items():
            for group in source_objects.values():
                for o in group:o.hide_render=True
            for o in items:o.hide_render=False
            for name,d in [('front',(1,-2,1.05)),('rear',(-1,2,1.05))]:camera_render(folder,key+'-'+name,items,d,size=(960,720))
        report={'mode':'inspect','inventory':inventory,'blender':bpy.app.version_string}
    else:
        for group in source_objects.values():
            for o in group:o.hide_render=True;o.hide_set(True)
        groups={};meshes=[];part_report=[]
        for part in cfg['parts']:
            parent=bpy.data.objects.new(part['id'],None);s.collection.objects.link(parent)
            parent.location=part['position'];parent.rotation_euler=[math.radians(x) for x in part['rotation']];parent.scale=part['scale'];groups[part['id']]=parent
            bpy.context.view_layer.update()
            if part['parent']:
                world=parent.matrix_world.copy();parent.parent=groups[part['parent']];parent.matrix_world=world
            children=[]
            for i,src in enumerate(source_objects[part['source']]):
                o=src.copy();o.data=src.data;s.collection.objects.link(o);o.name=part['id']+'__mesh_'+str(i);o.parent=parent;o.matrix_parent_inverse.identity();o.matrix_basis=src.matrix_world.copy();o.hide_render=False;o.hide_set(False);children.append(o);meshes.append(o)
            bpy.context.view_layer.update();lo,hi=bounds(children)
            part_report.append({'id':part['id'],'source':part['source'],'parent':part['parent'],'bounds':[list(lo),list(hi)],'triangles':sum(len(o.data.polygons) for o in children),'matrix_world':[list(r) for r in parent.matrix_world]})
        # Drop only imported staging objects, retain linked mesh datablocks and images.
        for group in source_objects.values():
            for o in group:bpy.data.objects.remove(o,do_unlink=True)
        bpy.context.view_layer.update();lo,hi=bounds(meshes);span=max(hi-lo);lighting(span)
        bpy.ops.mesh.primitive_plane_add(size=span*200,location=(0,0,lo.z-.015));floor=bpy.context.object;floor.name='REVIEW_FLOOR';mat=bpy.data.materials.new('Studio floor');mat.diffuse_color=(.16,.18,.20,1);floor.data.materials.append(mat)
        dirs={'hero':(1.7,-2.2,.85),'rear':(-1,1.9,1.05),'front':(0,-1,0),'back':(0,1,0),'left':(-1,0,0),'right':(1,0,0),'top':(0,0,1)}
        for view in cfg['views']:
            if view=='exploded':
                old={k:o.matrix_world.copy() for k,o in groups.items()}
                for i,(key,o) in enumerate(groups.items()):
                    world=old[key].copy();world.translation.z+=i*.23*span;o.matrix_world=world;bpy.context.view_layer.update()
                camera_render(folder,view,meshes,dirs['hero'],size=(1300,1600))
                for k,matrix in old.items():groups[k].matrix_world=matrix;bpy.context.view_layer.update()
                bpy.context.view_layer.update()
            else:camera_render(folder,view,meshes,dirs[view],size=(1600,1100) if view in ('hero','rear') else (1200,900))
            print('RENDERED '+view,flush=True)
        # Keep the main review view active in the editable native master.
        camera_render(folder,'preview',meshes,dirs['hero'],size=(1600,1100))
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=str(folder/'assembled.blend'),check_existing=False,compress=True)
        bpy.ops.object.select_all(action='DESELECT')
        for o in [*meshes,*groups.values()]:o.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(folder/'assembled.glb'),export_format='GLB',use_selection=True,export_apply=False,export_animations=False,export_tangents=True,export_image_format='AUTO')
        report={'mode':'assemble','blender':bpy.app.version_string,'inventory':inventory,'parts':part_report,'bounds':[list(lo),list(hi)],'triangles':sum(p['triangles'] for p in part_report),'images':[{'name':im.name,'size':list(im.size)} for im in bpy.data.images if im.type=='IMAGE'],'views':cfg['views'],'geometry_retopologized':False,'textures_rebaked':False,'engineering_fit_verified':False,'reference_accuracy':'single-reference art assembly; not measured CAD'}
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(folder/'assembled.glb'));bpy.context.view_layer.update()
        reread=[o for o in bpy.context.scene.objects if o.type=='MESH'];rlo,rhi=bounds(reread)
        error=max(abs(a-b) for v,w in zip((lo,hi),(rlo,rhi)) for a,b in zip(v,w))
        count=sum(len(o.data.polygons) for o in reread)
        report['glb_roundtrip']={'meshes':len(reread),'triangles':count,'bounds_error':error,'uv_layers':[len(o.data.uv_layers) for o in reread],'images':len([im for im in bpy.data.images if im.type=='IMAGE']),'passed':error<.0001 and count==report['triangles'] and len(reread)==len(meshes) and all(o.data.uv_layers for o in reread)}
        if not report['glb_roundtrip']['passed']:raise ValueError('Assembly GLB roundtrip mismatch')
    report['elapsed_seconds']=time.monotonic()-start
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
