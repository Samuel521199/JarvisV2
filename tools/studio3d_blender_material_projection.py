"""Make world-position image projection independent of mesh joining/transforms.

Blender's image BOX projection selects an axis in object space. Feeding it
world positions while later joining to a rotated active mesh changes that
selection, collapsing a planar surface to a texture line. Explicit world
normal weights and three flat projections keep authoring and baking consistent.
Run inside Blender. Does not modify the source image pixels.
"""


def replace_world_box_projection(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    changed = []
    for source in list(nodes):
        if source.type != "TEX_IMAGE" or source.projection != "BOX":
            continue
        if not source.inputs["Vector"].is_linked:
            raise ValueError("World projection requires explicit coordinates")
        coordinate = source.inputs["Vector"].links[0].from_socket
        consumers = [(link.to_socket, link.from_socket.name) for link in source.outputs["Color"].links]
        if source.outputs["Alpha"].is_linked:
            raise ValueError("Alpha BOX projection is not supported by this opaque asset adapter")
        geo = nodes.new("ShaderNodeNewGeometry")
        geo.label = "Stable world normal for coating projection"
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(coordinate, sep.inputs[0])
        normal = nodes.new("ShaderNodeSeparateXYZ")
        links.new(geo.outputs["Normal"], normal.inputs[0])
        weights = []
        for axis in "XYZ":
            absolute = nodes.new("ShaderNodeMath")
            absolute.operation = "ABSOLUTE"
            links.new(normal.outputs[axis], absolute.inputs[0])
            power = nodes.new("ShaderNodeMath")
            power.operation = "POWER"
            power.inputs[1].default_value = 8
            links.new(absolute.outputs[0], power.inputs[0])
            weights.append(power.outputs[0])
        add1 = nodes.new("ShaderNodeMath")
        add1.operation = "ADD"
        links.new(weights[0], add1.inputs[0])
        links.new(weights[1], add1.inputs[1])
        total = nodes.new("ShaderNodeMath")
        total.operation = "ADD"
        links.new(add1.outputs[0], total.inputs[0])
        links.new(weights[2], total.inputs[1])
        projected = []
        for index, axes in enumerate(("YZ", "XZ", "XY")):
            vector = nodes.new("ShaderNodeCombineXYZ")
            links.new(sep.outputs[axes[0]], vector.inputs["X"])
            links.new(sep.outputs[axes[1]], vector.inputs["Y"])
            tex = nodes.new("ShaderNodeTexImage")
            tex.image = source.image
            tex.projection = "FLAT"
            tex.extension = source.extension
            tex.interpolation = source.interpolation
            tex.label = source.label + " world " + axes
            links.new(vector.outputs[0], tex.inputs[0])
            divide = nodes.new("ShaderNodeMath")
            divide.operation = "DIVIDE"
            links.new(weights[index], divide.inputs[0])
            links.new(total.outputs[0], divide.inputs[1])
            scale = nodes.new("ShaderNodeVectorMath")
            scale.operation = "SCALE"
            links.new(tex.outputs["Color"], scale.inputs[0])
            links.new(divide.outputs[0], scale.inputs["Scale"])
            projected.append(scale.outputs[0])
        sum1 = nodes.new("ShaderNodeVectorMath")
        sum1.operation = "ADD"
        links.new(projected[0], sum1.inputs[0])
        links.new(projected[1], sum1.inputs[1])
        sum2 = nodes.new("ShaderNodeVectorMath")
        sum2.operation = "ADD"
        links.new(sum1.outputs[0], sum2.inputs[0])
        links.new(projected[2], sum2.inputs[1])
        for consumer, _ in consumers:
            links.new(sum2.outputs[0], consumer)
        changed.append(source.label or source.name)
        nodes.remove(source)
    return changed
