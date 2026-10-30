"""Optional reference-inspired exterior detail for a visual trail tube.

The collars, pads and bolt heads are visual art, not measured historical
geometry or a functional connection. The caller must assign a rigid owner and
review the resulting render; this module never creates operational mechanics.
"""
import math
from modules.skills.studio3d.assembly_geometry import Mesh, add, sub, mul, cross, norm


def _oriented_box(mesh, center, along, across, up, size):
    vertices=[]
    for x,y,z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)):
        point=center
        for axis,sign,length in ((along,x,size[0]),(across,y,size[1]),(up,z,size[2])):
            point=add(point,mul(axis,sign*length/2))
        vertices.append(point)
    mesh.append(vertices,[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]])


def add_trail_fittings(a, end, radius, label, mesh, bolt):
    """Add three seat-attached strap details to one existing trail group.

    `a`, `end` and `radius` must be those used by the host tube; existing
    collar centers are at 0.27, 0.64 and 0.90 of that same axis. `mesh` and
    `bolt` are the recipe's existing bounded data callbacks. Objects are
    batched into one extra mesh and the existing group fastener batch.
    """
    if label not in ('left','right') or not isinstance(radius,(int,float)) or isinstance(radius,bool) or not math.isfinite(radius) or not .058<=radius<=.10:
        raise ValueError('Invalid trail fittings input')
    if any(not isinstance(p,(tuple,list)) or len(p)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in p) for p in (a,end)):
        raise ValueError('Invalid trail axis')
    direction=sub(end,a);length=math.sqrt(sum(v*v for v in direction))
    if not 1.5<=length<=4.0:raise ValueError('Trail axis outside art bounds')
    along=norm(direction);across=norm(cross([0,0,1],along));up=norm(cross(along,across))
    group='trail-'+label;hardware=Mesh()
    collar_radius=radius*1.13
    for t in (.27,.64,.90):
        center=add(a,mul(direction,t))
        # Two fine raised edges sit against the pre-existing collar sleeve.
        for offset in (-.016,.016):
            # The edge bead is only 3.5 mm in these nominal units. Its tiny
            # cross-section does not need the long tube's surface resolution;
            # compact sampling keeps the combined recipe within its input cap.
            hardware.ring(add(center,mul(along,offset)),along,collar_radius+.001,.0035,16,4)
        # Top mounting pad overlaps the sleeve; bolt bases are seated on it.
        pad=add(center,mul(up,collar_radius+.004))
        _oriented_box(hardware,pad,along,across,up,[.065,.055,.018])
        for x in (-.020,.020):
            pos=add(add(pad,mul(along,x)),mul(up,.009))
            bolt(pos,up,group,.008)
        # Opposed side tabs touch the same collar, instead of floating nearby.
        for sign in (-1,1):
            side=add(center,mul(across,sign*(collar_radius+.003)))
            _oriented_box(hardware,side,along,across,up,[.046,.014,.036])
            bolt(add(side,mul(across,sign*.007)),mul(across,sign),group,.008)
    mesh('trail-strap-details-'+label,hardware,group,bevel=.001,smooth=False)
    return {'group':group,'collar_fractions':[.27,.64,.90],'visual_only':True}
