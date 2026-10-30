"""Restore a user-provided FBX atlas on an isolated character copy.

Materials are copied before editing; procedural face accents are hidden, not
deleted.  A renderer must visually validate alpha, UVs and face overlap.
"""
from pathlib import Path


def apply(atlas_path, include_body_texture=False):
    import bpy

    atlas_path = Path(atlas_path)
    if not atlas_path.is_file():
        raise FileNotFoundError(atlas_path)
    body = bpy.data.objects.get('Body')
    face = bpy.data.objects.get('Face')
    if not body or not face or len(body.data.vertices) != 6578 or len(face.data.vertices) != 4709:
        raise ValueError('Unexpected character mesh identity')
    if any(not o.data.uv_layers.get('UVMap') for o in (body, face)):
        raise ValueError('Expected FBX UVMap missing')
    image = bpy.data.images.load(str(atlas_path), check_existing=False)
    image.name = 'user-character-female-atlas'
    image.colorspace_settings.name = 'sRGB'
    image.pack()
    # The source FBX stores each material's UVs over a full texture, while the
    # provided 4096 atlas packs those textures into different rectangular tiles.
    # These coordinates are experimental and must be verified by renders.
    tiles = {
        'body_00_skin': (0, .5, .5, .5),
        'face_00_skin': (0, .25, .25, .25),
        'faceMouth_00_face': (0, .125, .125, .125),
        'eyeiris_00_eye': (.25, .375, .25, .125),
        'eyehighlight_00_eye': (.5, .375, .25, .125),
        'eyewhite_00_eye': (.75, .375, .25, .125),
        'facebrow_00_face': (.25, .3125, .25, .0625),
        'faceeyelash_00_face': (.5, .3125, .25, .0625),
        'faceeyeline_00_face': (.5, .3125, .25, .0625),
    }
    tiles = {k.lower(): v for k, v in tiles.items()}
    changed = []
    # The reference has simplified body surfaces; retain a plain skin shader by
    # default, and allow the source's more detailed body atlas only explicitly.
    for obj in ((body, face) if include_body_texture else (face,)):
        source_uv = obj.data.uv_layers['UVMap']
        if obj.data.uv_layers.get('JarvisAtlasUV'):
            raise ValueError('Atlas UV already applied to this mesh')
        atlas_uv = obj.data.uv_layers.new(name='JarvisAtlasUV')
        tile_for_slot = {}
        for i, old in enumerate(obj.data.materials):
            matches = [v for k, v in tiles.items() if old and k in old.name.lower()]
            if len(matches) != 1:
                raise ValueError('No unambiguous atlas tile in slot ' + str(i))
            tile_for_slot[i] = matches[0]
        for polygon in obj.data.polygons:
            x, y, sx, sy = tile_for_slot[polygon.material_index]
            for index in polygon.loop_indices:
                u, v = source_uv.data[index].uv
                atlas_uv.data[index].uv = (x + u * sx, y + v * sy)
        obj.data.uv_layers.active = atlas_uv
        atlas_uv.active_render = True
        for i, old in enumerate(list(obj.data.materials)):
            if not old:
                continue
            mat = old.copy()
            mat.name = 'atlas-trial-' + old.name
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            nodes.clear()
            links = mat.node_tree.links
            output = nodes.new('ShaderNodeOutputMaterial')
            shader = nodes.new('ShaderNodeBsdfPrincipled')
            shader.inputs['Roughness'].default_value = .65
            texture = nodes.new('ShaderNodeTexImage')
            texture.image = image
            texture.interpolation = 'Linear'
            uv = nodes.new('ShaderNodeUVMap')
            uv.uv_map = 'JarvisAtlasUV'
            links.new(uv.outputs['UV'], texture.inputs['Vector'])
            links.new(texture.outputs['Color'], shader.inputs['Base Color'])
            links.new(texture.outputs['Alpha'], shader.inputs['Alpha'])
            links.new(shader.outputs['BSDF'], output.inputs['Surface'])
            if hasattr(mat, 'surface_render_method'):
                mat.surface_render_method = 'DITHERED'
            obj.data.materials[i] = mat
            changed.append({'object': obj.name, 'slot': i, 'source_material': old.name, 'candidate_material': mat.name})
    if not include_body_texture:
        old = body.data.materials[0]
        skin = old.copy(); skin.name = 'atlas-trial-body-simplified'
        skin.use_nodes = True
        nodes = skin.node_tree.nodes; nodes.clear()
        output = nodes.new('ShaderNodeOutputMaterial'); shader = nodes.new('ShaderNodeBsdfPrincipled')
        shader.inputs['Base Color'].default_value = (.83, .69, .63, 1)
        shader.inputs['Roughness'].default_value = .65
        skin.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
        skin.diffuse_color = (.81, .74, .71, 1)
        body.data.materials[0] = skin
        changed.append({'object': body.name, 'slot': 0, 'source_material': old.name, 'candidate_material': skin.name})
    hidden = []
    for obj in bpy.context.scene.objects:
        if obj.name.startswith(('eye-iris-', 'eye-pupil-', 'eye-glint-', 'eye-upper-lid-', 'eye-brow-')):
            obj.hide_render = True
            obj.hide_set(True)
            hidden.append(obj.name)
    hair = bpy.data.materials.get('character-hair-procedural')
    if hair and hair.use_nodes:
        shader = next((n for n in hair.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if shader:
            shader.inputs['Base Color'].default_value = (.46, .44, .51, 1)
            shader.inputs['Roughness'].default_value = .65
            hair.diffuse_color = (.70, .69, .75, 1)
    return {'atlas': str(atlas_path), 'packed': bool(image.packed_file),
            'changed_materials': changed, 'hidden_procedural_face_parts': hidden,
            'hair_color': 'approximate flat silver-lavender', 'body_atlas_enabled': include_body_texture,
            'limitations': ['No normal map applied', 'UV and alpha need visual validation',
                            'Hair texture and strand geometry remain incomplete']}
