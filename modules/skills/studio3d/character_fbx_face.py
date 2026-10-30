# SPDX-License-Identifier: GPL-2.0-or-later
"""Fixed neutral eye treatment for a copy of the user's Female_01 FBX.

The source lacks several referenced eye textures. This optional Blender-only
helper makes only the affected face materials transparent and adds procedural
eye accents. It never loads or packs the source texture atlas. Call only on a
user-authorized in-memory copy after validating the model identity and frame.
"""

VERSION='0.2.0'


def apply():
    import bpy
    hidden=[]
    for mat in bpy.data.materials:
        name=mat.name.casefold()
        if not any(part in name for part in ('facebrow','faceeyelash','faceeyeline','eyehighlight')):
            continue
        mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear()
        out=nodes.new('ShaderNodeOutputMaterial');transparent=nodes.new('ShaderNodeBsdfTransparent')
        mat.node_tree.links.new(transparent.outputs['BSDF'],out.inputs['Surface'])
        if hasattr(mat,'surface_render_method'):mat.surface_render_method='DITHERED'
        hidden.append(mat.name)
    if not hidden:
        raise ValueError('Expected FBX face overlay materials not found')
    # Missing source alpha leaves the imported iris plane covering the eye.
    # Paint that plane ivory and add separate geometric brown irises, so that
    # the appearance can be carried by standard GLB materials without atlas.
    iris_materials=[]
    for mat in bpy.data.materials:
        if 'eyeiris' not in mat.name.casefold():continue
        mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear();links=mat.node_tree.links
        out=nodes.new('ShaderNodeOutputMaterial');bs=nodes.new('ShaderNodeBsdfPrincipled')
        links.new(bs.outputs['BSDF'],out.inputs['Surface']);bs.inputs['Roughness'].default_value=.55
        bs.inputs['Base Color'].default_value=(.82,.78,.74,1);iris_materials.append(mat.name)
    def material(name,color):
        mat=bpy.data.materials.new(name);mat.diffuse_color=(*color,1);mat.use_nodes=True
        bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=.55
        return mat
    dark=material('character-procedural-eye-dark',(.065,.032,.023))
    iris=material('character-procedural-iris',(.24,.13,.065))
    light=material('character-procedural-eye-glint',(.9,.87,.83))
    def line(name,coords,radius,mat):
        curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.resolution_u=12;curve.bevel_depth=radius;curve.bevel_resolution=3
        spline=curve.splines.new('BEZIER');spline.bezier_points.add(len(coords)-1)
        for point,co in zip(spline.bezier_points,coords):point.co=co;point.handle_left_type='AUTO';point.handle_right_type='AUTO'
        obj=bpy.data.objects.new(name,curve);bpy.context.collection.objects.link(obj);obj.data.materials.append(mat)
    def oval(name,position,scale,mat):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=1,location=position)
        obj=bpy.context.object;obj.name=name;obj.scale=scale;obj.data.materials.append(mat)
        for poly in obj.data.polygons:poly.use_smooth=True
    for sign,label in ((-1,'r'),(1,'l')):
        # FBX frame: X lateral, Y forward negative, Z up, metres.
        oval('eye-iris-'+label,(sign*.034,-.063,1.446),(.010,.0014,.012),iris)
        oval('eye-pupil-'+label,(sign*.034,-.0648,1.446),(.0038,.0015,.0072),dark)
        oval('eye-glint-'+label,(sign*.0315,-.0665,1.450),(.0017,.0010,.0018),light)
        line('eye-upper-lid-'+label,[(sign*.018,-.063,1.445),(sign*.024,-.064,1.455),
             (sign*.038,-.063,1.458),(sign*.052,-.059,1.455),(sign*.061,-.054,1.450)],.0012,dark)
        line('eye-brow-'+label,[(sign*.018,-.065,1.478),(sign*.032,-.063,1.482),
             (sign*.048,-.058,1.479)],.0010,dark)
    return {'hidden_texture_dependent_materials':hidden,'procedural_iris_materials':iris_materials,'atlas_loaded':False,
            'limits':['procedural approximation, not the missing source eye textures','no change to the source FBX']}
