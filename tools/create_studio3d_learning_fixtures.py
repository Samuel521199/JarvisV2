# SPDX-License-Identifier: GPL-2.0-or-later
"""Blender-only original diagnostic coupons, NOT the 24 art exercises."""
import json
import sys
from pathlib import Path
import bpy
import bmesh


def material(name, color, metallic):
    mat=bpy.data.materials.new(name); mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Metallic'].default_value=metallic;bsdf.inputs['Roughness'].default_value=.38
    return mat


def box(name, scale, position, mat):
    bpy.ops.mesh.primitive_cube_add(size=1,location=position);o=bpy.context.object;o.name=name;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat)
    return o


def main():
    folder=Path(sys.argv[sys.argv.index('--')+1]).resolve();folder.mkdir(parents=True,exist_ok=True)
    for case in ('plate','flange','unresolved'):
        target=folder/case;target.mkdir(exist_ok=False)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        paint=material('paint',(.11,.16,.13),0);steel=material('steel',(.38,.4,.41),1)
        if case=='flange':
            bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.6,depth=.1)
            plate=bpy.context.object;plate.name='support';plate.data.materials.append(paint)
        else:plate=box('support',(1,.8,.1),(0,0,0),paint)
        bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=.08,depth=.04,location=(.25,.2,.25))
        knob=bpy.context.object;knob.name='attachment';knob.data.materials.append(steel)
        pod=box('rejected-pod',(.15,.15,.32),(-.35,.1,.30),paint)
        child=box('pod-residue',(.1,.1,.06),(-.35,.1,.49),steel);m=child.matrix_world.copy();child.parent=pod;child.matrix_world=m
        box('rejected-pod.001',(.12,.12,.15),(-.18,-.25,.25),paint)
        if case=='unresolved':
            bm=bmesh.new();bm.from_mesh(plate.data)
            face=min(bm.faces,key=lambda f:f.calc_center_median().z)
            bmesh.ops.delete(bm,geom=[face],context='FACES');bm.to_mesh(plate.data);bm.free()
        bpy.ops.export_scene.gltf(filepath=str(target/'source.glb'),export_format='GLB',export_extras=True)
        contract={'schema':'jarvis.studio3d.learning.v1','asset_id':'diagnostic-'+case,'family':'hard_surface',
            'parts':[{'id':'support','node':'support','motion_owner':'support','motion':'fixed','closed_surface':True},
                     {'id':'attachment','node':'attachment','motion_owner':'support','motion':'coupled','closed_surface':True}],
            'attachments':[{'part':'attachment','support':'support','max_gap':.002,'target_position':[.25,.2,.07]}],
            'rejected':['rejected-pod'],'symptoms':['rejected_parts','floating_attachment'],'reference_policy':{'shield':'none'}}
        (target/'contract.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
    (folder/'scope.json').write_text(json.dumps({'kind':'authored-defect diagnostic coupons','formal_art_practice_count':0,'purpose':'fixed-tool behavior and export evidence only'}),encoding='utf-8')


if __name__=='__main__':main()
