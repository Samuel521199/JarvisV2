# SPDX-License-Identifier: GPL-2.0-or-later
"""Local, hair-only reference-informed candidate for the FBX character.

Called on a separately opened copy of the reviewed A-pose BLEND. No image,
path, generated code, body, face, material atlas or armature is modified.
The added locks are editable geometry, not evidence of visual acceptance.
"""
import math

VERSION='0.1.0'


def apply():
    import bpy
    from mathutils import Vector
    present={o.name for o in bpy.context.scene.objects}
    if not {'Body','Face','headend','hair-scalp-refined'} <= present:
        raise ValueError('Expected reviewed character v4 objects')
    stale=[o for o in bpy.context.scene.objects if o.name.startswith(('bang-refined','side-hair-refined','back-hair-refined'))]
    if len(stale)<20:raise ValueError('Expected editable original v4 hair locks')
    materials=[m for m in bpy.data.materials if m.name=='character-hair-procedural']
    if len(materials)!=1:raise ValueError('Expected v4 hair material')
    material=materials[0]
    removed=[o.name for o in stale]
    for o in stale:bpy.data.objects.remove(o,do_unlink=True)
    created=[]
    def bezier(a,b,c,d,t):
        return ((1-t)**3)*a+3*((1-t)**2)*t*b+3*(1-t)*t*t*c+t**3*d
    def lock(name,control,width,thickness=.0022,steps=14,side=False):
        points=[Vector(c) for c in control];columns=7;verts=[]
        # The broad region begins below the roots and gradually narrows to a
        # fine tip. Each shell has two surfaces so it remains visible in GLB.
        for back in (0,1):
            for i in range(steps+1):
                t=i/steps
                center=bezier(*points,t)
                factor=(.38+.62*min(1,t*8))*((1-t)**.62)+.015
                for j in range(columns):
                    u=2*j/(columns-1)-1
                    xx=center.x+(back*thickness if side else width*factor*u)
                    yy=center.y+(width*factor*u if side else -(1-u*u)*width*.18+back*thickness)
                    zz=center.z+.0025*u*u
                    verts.append((xx,yy,zz))
        row=columns*(steps+1);faces=[]
        for layer in (0,1):
            off=layer*row
            for i in range(steps):
                for j in range(columns-1):
                    n=off+i*columns+j
                    face=(n,n+1,n+1+columns,n+columns)
                    faces.append(face if not layer else tuple(reversed(face)))
        for i in range(steps):
            for j in (0,columns-1):
                a=i*columns+j;b=(i+1)*columns+j
                faces.append((a,b,b+row,a+row))
        for i in (0,steps):
            for j in range(columns-1):
                a=i*columns+j;b=a+1;faces.append((a,a+row,b+row,b))
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
        obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj)
        obj.data.materials.append(material)
        for f in mesh.polygons:f.use_smooth=True
        created.append(name)
    # Asymmetric fine fringe; roots are behind the cap and emerge gradually.
    # X horizontal, -Y toward the front and Z up in the imported FBX frame.
    fringe=[
      (-.050,-.052,-.058,1.459,.015),(-.039,-.042,-.049,1.452,.014),
      (-.029,-.030,-.035,1.458,.015),(-.018,-.017,-.025,1.449,.014),
      (-.006,-.007,-.008,1.454,.015),(.007,.010,.016,1.466,.014),
      (.020,.025,.029,1.459,.013),(.032,.037,.044,1.472,.013),
      (.043,.050,.059,1.468,.012)]
    for k,(root,mid,tip,zend,w) in enumerate(fringe):
        lock('hair-refine-fringe-%02d'%k,[(root,.008,1.588+(k%3)*.002),(root*.8,-.064,1.568),
              (mid,-.092,1.507),(tip,-.088,zend)],w)
    # Side wisps go past the jaw and spread outward, unlike a vertical curtain.
    for sign,label in ((-1,'r'),(1,'l')):
        for k in range(7):
            root=sign*(.052+.0042*k);tip=sign*(.080+.005*k)
            zend=1.355+(k%3)*.008-(.006 if k in (1,4) else 0)
            y=-.050+.012*k
            lock('hair-refine-side-%s-%02d'%(label,k),[(root,y,1.561),
                 (sign*(.073+.002*k),y-.012,1.50),(sign*(.078+.003*k),y-.008,1.405),
                 (tip,y+.002,zend)],.0095+(k%2)*.001,side=True)
        # Long forward side locks are visible against the neck in the ref.
        lock('hair-refine-long-'+label,[(sign*.056,-.067,1.540),(sign*.072,-.076,1.485),
             (sign*.066,-.085,1.388),(sign*.060,-.086,1.348)],.010,side=True)
    # Layered rear edge in staggered lengths; stay behind face in side views.
    for k in range(15):
        x=(k-7)*.009;tip=x*1.23
        lock('hair-refine-back-%02d'%k,[(x*.7,.020,1.565),(x*.85,.12,1.51),
             (x,.125,1.425),(tip,.105,1.348+(k%4)*.009)],.0105)
    return {'version':VERSION,'removed_hair_objects':removed,
            'created_hair_objects':created,'scope':'hair geometry only; no body, face or pose changes',
            'bound_to_rig':False,'user_approval':False}
