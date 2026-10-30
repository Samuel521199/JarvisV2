# SPDX-License-Identifier: GPL-2.0-or-later
"""Add provisional side and rear hair to the known v4 character only.

All existing scalp and fringe objects remain untouched. The source scene is
an editable local copy; this procedure modifies no model-selected path.
"""
import math

VERSION='0.1.0'


def apply():
    import bpy
    from mathutils import Vector
    scene=bpy.context.scene
    names={o.name for o in scene.objects}
    if not {'Body','Face','headend','hair-scalp-refined','bang-refined-center'}<=names:
        raise ValueError('Unexpected character v4 source')
    if any(n.startswith('hair-hybrid-') for n in names):
        raise ValueError('Hair candidate already applied')
    material=bpy.data.materials.get('character-hair-procedural')
    if not material:raise ValueError('Expected character hair material')
    created=[]

    def blend(a,b,c,d,t):
        return a*((1-t)**3)+b*(3*(1-t)**2*t)+c*(3*(1-t)*t*t)+d*(t**3)

    def strand(name, controls, width, axis, steps=18):
        pts=[Vector(v) for v in controls];cross=Vector(axis).normalized();cols=7;verts=[]
        normal=Vector((-cross.y,cross.x,0));thickness=.0012
        for layer in (0,1):
            for i in range(steps+1):
                t=i/steps;center=blend(*pts,t)
                w=width*(.7+.3*math.sin(math.pi*t))*((1-t)**.7)+.0003
                for j in range(cols):
                    u=2*j/(cols-1)-1
                    v=center+cross*(u*w)+normal*((1-u*u)*w*.12+layer*thickness)
                    verts.append(tuple(v))
        row=cols*(steps+1);faces=[]
        for layer in (0,1):
            off=row*layer
            for i in range(steps):
                for j in range(cols-1):
                    n=off+i*cols+j;f=(n,n+1,n+1+cols,n+cols)
                    faces.append(f if not layer else tuple(reversed(f)))
        for i in range(steps):
            for j in (0,cols-1):
                a=i*cols+j;b=(i+1)*cols+j;faces.append((a,b,b+row,a+row))
        for i in (0,steps):
            for j in range(cols-1):
                a=i*cols+j;b=a+1;faces.append((a,a+row,b+row,b))
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
        ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob);ob.data.materials.append(material)
        for poly in mesh.polygons:poly.use_smooth=True
        created.append(name)

    # Only four side panels per side; their diagonal cross section makes them
    # visible from both front and side rather than turning into hairline wires.
    for sign,label in ((-1,'r'),(1,'l')):
        for k in range(4):
            y=-.040+k*.023;tipz=1.365+(k%2)*.009
            strand('hair-hybrid-side-%s-%d'%(label,k),[(sign*.053,y+.012,1.535),
                (sign*.074,y,1.510),(sign*.089,y-.003,1.414),
                (sign*(.087+.002*k),y+.008,tipz)],.009,(sign*.7,.7,0))
    # Staggered rear tips begin under the original hair cap, preserving it.
    for k in range(9):
        x=(k-4)*.011
        strand('hair-hybrid-back-%02d'%k,[(x*.7,.060,1.53),(x*.9,.103,1.49),
             (x,.126,1.41),(x*1.16,.113,1.352+(k%3)*.009)],.008,(1,0,0))
    return {'version':VERSION,'scope':'added side and back hair only','existing_hair_removed':False,
            'created_hair_objects':created,'bound_to_rig':False,'user_approval':False}
