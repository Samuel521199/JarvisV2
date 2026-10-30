# SPDX-License-Identifier: GPL-2.0-or-later
"""Small, reversible shoulder pose trial for the explicitly selected asset."""
import math


def apply():
    import bpy
    from mathutils import Matrix,Vector
    arm=next((o for o in bpy.context.scene.objects if o.type=='ARMATURE'),None)
    if not arm or len(arm.data.bones)!=93:raise ValueError('Expected 93-bone source rig')
    changes=[]
    for name in ('J_Bip_L_UpperArm','J_Bip_R_UpperArm'):
        bone=arm.pose.bones.get(name)
        if bone is None:raise ValueError('Missing upper-arm bone')
        head=arm.matrix_world@bone.head
        axis=arm.matrix_world.to_quaternion().inverted()@Vector((0,1,0))
        angle=math.radians(8)*(1 if head.x>0 else -1)
        pivot=bone.head.copy();prior=[list(r) for r in bone.matrix]
        bone.matrix=Matrix.Translation(pivot)@Matrix.Rotation(angle,4,axis)@Matrix.Translation(-pivot)@bone.matrix
        bpy.context.view_layer.update()
        changes.append({'bone':name,'world_y_rotation_degrees':math.degrees(angle),'previous_matrix':prior})
    return {'scope':'arm pose only; underlying body mesh and weights untouched', 'changes':changes,
            'body_curves':'not modified: reliable reference-aligned measurements not established',
            'status':'candidate; four-view visual and deformation validation required'}
