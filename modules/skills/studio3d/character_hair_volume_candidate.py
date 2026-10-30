"""Experimental character-only rear hair volume; never promoted automatically."""
import math


def apply():
    import bpy
    from mathutils import Vector
    required={'Body','Face','headend','hair-scalp-refined','bang-refined-center'}
    if not required <= {o.name for o in bpy.context.scene.objects}:
        raise ValueError('Unexpected hair source')
    mat=bpy.data.materials.get('character-hair-procedural')
    if not mat:
        raise ValueError('Missing material')
    verts=[]; faces=[]; cols=97; rows=25
    # An arched, continuous rear curtain rather than individual hanging wires.
    # The upper edge is buried beneath the existing scalp shell.
    for j in range(rows):
        t=j/(rows-1)
        for i in range(cols):
            a=math.pi*i/(cols-1)
            ripple=(.0018*math.sin(11*a+2*t)+.0009*math.sin(19*a-3*t))*math.sin(math.pi*t)
            # Slightly uneven ends, with softer broad lobes and small tips.
            end=1.355+.008*math.sin(5*a+.7)+.004*math.sin(13*a+.2)
            z=(1-t)*1.548+t*end
            # Continue the imported ellipsoidal cap at its equator; gradually
            # taper lower hair rather than exposing an abrupt joint.
            q=max(0.,min(1.,(z-1.458)/.142))
            high=math.sqrt(max(0.,1-q*q))
            lower=max(0.,min(1.,(1.458-z)/.103))
            rx=(.0906*high)*(1-.13*lower)+.0005
            ry=(.1096*high)*(1-.10*lower)+.0005
            x=(rx+ripple)*math.cos(a)
            y=.018+(ry+ripple)*math.sin(a)
            verts.append((x,y,z))
    for j in range(rows-1):
        for i in range(cols-1):
            a=j*cols+i;faces.append((a,a+1,a+1+cols,a+cols))
    mesh=bpy.data.meshes.new('hair-volume-curtain');mesh.from_pydata(verts,[],faces);mesh.update()
    ob=bpy.data.objects.new('hair-volume-curtain',mesh);bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    for p in mesh.polygons:p.use_smooth=True
    mod=ob.modifiers.new('hair volume thickness','SOLIDIFY');mod.thickness=.001
    return {'created':['hair-volume-curtain'],'source_retained':True,'scope':'unrigged hair diagnostic','automatic_promotion':False}
