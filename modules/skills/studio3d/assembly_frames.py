"""Rigid art-assembly placement in a declared parent frame, as scene data.

Rotates the whole assembly, not individual details toward the camera. Keeping
attached items in one local frame prevents world-axis orphan attachments.
"""
import math


def rotate_point(point,pivot,angle):
    c=math.cos(angle);s=math.sin(angle);x=point[0]-pivot[0];y=point[1]-pivot[1]
    return [pivot[0]+c*x-s*y,pivot[1]+s*x+c*y,point[2]]


def orient_z(objects,pivot,angle):
    if not math.isfinite(angle) or abs(angle)>math.pi/2:raise ValueError('Assembly yaw outside visual placement range')
    for obj in objects:
        obj['position']=rotate_point(obj.get('position',[0,0,0]),pivot,angle)
        rotation=list(obj.get('rotation',[0,0,0]));rotation[2]+=math.degrees(angle);obj['rotation']=rotation
    return {'count':len(objects),'pivot':list(pivot),'yaw_degrees':math.degrees(angle),'scope':'shared rigid exterior frame, not a physical joint model'}
