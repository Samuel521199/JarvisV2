"""Restore declared rigid game-prop motion after texture atlas joining.

Only local, authored mesh membership and translations are used. No scripts,
drivers, constraints or physical/functional mechanism are generated.
"""
import json
import bpy


def restore_visual_slide(scene):
    raw = scene.get("game_breech_animation")
    if not raw:
        return []
    spec = json.loads(raw)
    members = [bpy.data.objects[name] for name in spec["members"]]
    assert all(obj.type == "MESH" for obj in members)
    root = bpy.data.objects.new("Game_Breech_Slide", None)
    scene.collection.objects.link(root)
    root["game_animation_role"] = "Simplified visual opening"
    for obj in members:
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world
        obj["game_animation_group"] = "breech_slide"
    for frame, offset in zip(spec["frames"], spec["offsets"]):
        root.location = [value * offset for value in spec["translation"]]
        root.keyframe_insert(data_path="location", frame=frame)
    root.animation_data.action.name = spec["name"]
    scene.frame_start = spec["frames"][0]
    scene.frame_end = spec["frames"][-1]
    scene.render.fps = 30
    scene.frame_set(scene.frame_start)
    bpy.context.view_layer.update()
    return [root]
