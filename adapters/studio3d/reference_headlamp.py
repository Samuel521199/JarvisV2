# SPDX-License-Identifier: GPL-2.0-or-later
"""Editable reference headlamp, front -Y, foot Z=0; art dimensions, not CAD."""
import math
import bpy


def build():
    pieces=[]
    def mat(name,color,metal,rough,transmission=0):
        m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
        b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*color,1)
        b.inputs['Metallic'].default_value=metal;b.inputs['Roughness'].default_value=rough
        b.inputs['Transmission Weight'].default_value=transmission;b.inputs['IOR'].default_value=1.46
        return m
    paint=mat('Headlamp · sand enamel',(.57,.46,.29),.32,.45)
    steel=mat('Headlamp · steel fasteners',(.18,.19,.18),.85,.31)
    rubber=mat('Headlamp · gasket',(.025,.028,.026),.0,.7)
    reflector=mat('Headlamp · reflector',(.44,.49,.51),.9,.23)
    glass=mat('Headlamp · fluted glass',(.34,.41,.43),.08,.21,.32)
    def finish(o,name,material,smooth=True):
        o.name='headlamp_'+name;o.data.materials.append(material);pieces.append(o)
        for p in o.data.polygons:p.use_smooth=smooth
        return o
    def cyl(name,loc,radius,depth,material,axis='Z',vertices=64):
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=loc)
        o=bpy.context.object
        if axis=='Y':o.rotation_euler.x=math.pi/2
        elif axis=='X':o.rotation_euler.y=math.pi/2
        return finish(o,name,material)
    def cube(name,loc,scale,material,bevel=.004):
        bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.scale=scale
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        mod=o.modifiers.new('Machined edge radius','BEVEL');mod.width=bevel;mod.segments=3
        bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
        return finish(o,name,material,False)
    def lathe(name,profile,material,segments=96):
        # profile pairs are axial Y and radius, each ring around the lamp axis.
        verts=[(r*math.cos(a*math.tau/segments),y,.245+r*math.sin(a*math.tau/segments)) for y,r in profile for a in range(segments)]
        faces=[]
        for j in range(len(profile)-1):
            for i in range(segments):faces.append((j*segments+i,j*segments+(i+1)%segments,(j+1)*segments+(i+1)%segments,(j+1)*segments+i))
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update();uv=mesh.uv_layers.new(name='UVMap')
        for poly in mesh.polygons:
            j=poly.index//segments;i=poly.index%segments
            for loop,co in zip(poly.loop_indices,[(i/segments,j/(len(profile)-1)),((i+1)/segments,j/(len(profile)-1)),((i+1)/segments,(j+1)/(len(profile)-1)),(i/segments,(j+1)/(len(profile)-1))]):uv.data[loop].uv=co
        o=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(o)
        return finish(o,name,material)
    def torus(name,y,radius,thickness,material):
        bpy.ops.mesh.primitive_torus_add(major_segments=96,minor_segments=12,location=(0,y,.245),rotation=(math.pi/2,0,0),major_radius=radius,minor_radius=thickness)
        return finish(bpy.context.object,name,material)
    cube('mounting_foot',(0,.015,.008),(.145,.12,.016),paint)
    cyl('stand',(0,.015,.07),.021,.12,paint)
    cube('cross_yoke',(0,.015,.130),(.26,.035,.022),paint)
    for sign in (-1,1):
        cube('yoke_side_'+str(sign),(sign*.135,.015,.187),(.019,.035,.13),paint)
        cyl('pivot_'+str(sign),(sign*.144,.015,.245),.022,.018,steel,'X',32)
        cyl('foot_bolt_'+str(sign),(sign*.05,.015,.022),.011,.012,steel,vertices=6)
    lathe('rounded_housing',[(.08,.001),(.077,.035),(.065,.075),(.043,.106),(.015,.125),(-.035,.133),(-.061,.133),(-.064,.123),(-.037,.123),(.008,.115),(.035,.094),(.054,.06),(.06,.001)],paint)
    lathe('reflector',[(-.055,.12),(-.042,.10),(-.018,.07),(-.004,.035),(.0,.001)],reflector)
    torus('seal',-.066,.122,.005,rubber)
    torus('bezel',-.069,.131,.008,paint)
    lathe('glass_lens',[(-.068,.001),(-.068,.119),(-.073,.119),(-.077,.10),(-.080,.07),(-.082,.035),(-.083,.001)],glass)
    # Thin molded lens flutes, modelled rather than an emissive placeholder.
    for index in range(-8,9):
        x=index*.012;h=math.sqrt(.113**2-x*x)
        curve=bpy.data.curves.new('glass_flute','CURVE');curve.dimensions='3D';curve.bevel_depth=.00065;curve.bevel_resolution=2
        spline=curve.splines.new('POLY');spline.points.add(12)
        for i,p in enumerate(spline.points):
            z=-h+2*h*i/12;r=math.sqrt(x*x+z*z);y=-.083+.015*(r/.119)**2;p.co=(x,y-.0002,.245+z,1)
        o=bpy.data.objects.new('glass_flute',curve);bpy.context.collection.objects.link(o);bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.convert(target='MESH')
        finish(bpy.context.object,'lens_flute_'+str(index),glass)
    for i in range(6):
        a=math.tau*i/6;x=.131*math.cos(a);z=.245+.131*math.sin(a)
        cyl('bezel_screw_'+str(i),(x,-.078,z),.004,.004,steel,'Y',12)
    for o in pieces:
        if not o.data.uv_layers:
            uv=o.data.uv_layers.new(name='UVMap')
            for p in o.data.polygons:
                for li in p.loop_indices:
                    v=o.data.vertices[o.data.loops[li].vertex_index].co;uv.data[li].uv=(v.x+.5,v.z+.5)
    return pieces
