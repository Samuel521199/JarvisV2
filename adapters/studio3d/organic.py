# SPDX-License-Identifier: GPL-2.0-or-later
"""Original bounded radial geometry and procedural fruit/bark materials.

Parameters come from the scene contract. Appearance is inferred, not scanned.
"""
import math

def sweep(p):
    """Catmull-Rom centreline, linear radii, parallel-transport ring frames."""
    points=p['points'];steps=p['steps'];count=p['segments'];centers=[];radii=[]
    def unit(v):
        length=math.sqrt(sum(x*x for x in v))
        if length<1e-10:raise ValueError('Sweep tangent collapsed')
        return tuple(x/length for x in v)
    def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    for i in range(len(points)-1):
        a,b,c,d=points[max(0,i-1)],points[i],points[i+1],points[min(len(points)-1,i+2)]
        for k in range(steps):
            t=k/steps;centers.append(tuple(.5*(2*b[j]+(-a[j]+c[j])*t+(2*a[j]-5*b[j]+4*c[j]-d[j])*t*t+(-a[j]+3*b[j]-3*c[j]+d[j])*t*t*t) for j in range(3)))
            radii.append(p['radii'][i]*(1-t)+p['radii'][i+1]*t)
    centers.append(tuple(points[-1]));radii.append(p['radii'][-1]);verts=[];normal=None
    for i,(center,radius) in enumerate(zip(centers,radii)):
        tangent=unit(tuple(centers[min(i+1,len(centers)-1)][j]-centers[max(0,i-1)][j] for j in range(3)))
        if normal is None:
            axis=min(range(3),key=lambda j:abs(tangent[j]));normal=unit(cross(tangent,tuple(int(j==axis) for j in range(3))))
        else:
            dot=sum(normal[j]*tangent[j] for j in range(3));normal=unit(tuple(normal[j]-dot*tangent[j] for j in range(3)))
        other=cross(tangent,normal)
        for k in range(count):
            a=k*math.tau/count;u=i/(len(centers)-1);amount=p.get('end_irregularity',0)*(u**12+(1-u)**12)
            r=radius*(1+amount*(.6*math.sin(3*a)+.3*math.sin(7*a)+.1*math.sin(11*a)))
            verts.append(tuple(center[j]+r*(math.cos(a)*normal[j]+p.get('oval',1)*math.sin(a)*other[j])+tangent[j]*radius*amount*.6*math.sin(5*a) for j in range(3)))
    faces=[(i*count+k,i*count+(k+1)%count,(i+1)*count+(k+1)%count,(i+1)*count+k) for i in range(len(centers)-1) for k in range(count)]
    faces.extend([tuple(reversed(range(count))),tuple(range((len(centers)-1)*count,len(centers)*count))])
    return verts,faces

def radial(p):
    count=p['segments'];profile=p['profile'];lo=min(z for r,z in profile);height=max(z for r,z in profile)-lo
    verts=[]
    for r,z in profile:
        h=(z-lo)/max(height,1e-9)
        for i in range(count):
            t=i*math.tau/count
            lobes=p.get('lobes',0);wave=math.cos(lobes*t+.4) if lobes else 0
            strength=p.get('lobe_depth',0)*(.18+.82*abs(2*h-1)**2)
            rr=r*(1+strength*wave+p.get('asymmetry',0)*math.cos(t+.7)*math.sin(math.pi*h))
            zz=z+height*strength*.18*wave*math.sin(math.pi*h)
            verts.append((rr*math.cos(t),rr*math.sin(t),zz))
    faces=[(j*count+i,j*count+(i+1)%count,(j+1)*count+(i+1)%count,(j+1)*count+i) for j in range(len(profile)-1) for i in range(count)]
    if p.get('caps'):
        bottom=len(verts);verts.append((0,0,profile[0][1]));top=len(verts);verts.append((0,0,profile[-1][1]));start=(len(profile)-1)*count
        faces.extend((bottom,(i+1)%count,i) for i in range(count))
        faces.extend((top,start+i,start+(i+1)%count) for i in range(count))
    return verts,faces

def retopo_lathe(params,budget):
    """Bounded ring mesh; final vertices are projected to the high by caller."""
    profile=params['profile'];segments=max(8,min(64,int(math.sqrt(budget/1.5))));rings=max(3,min(64,budget//(2*segments)))
    length=[0.0]
    for a,b in zip(profile,profile[1:]):length.append(length[-1]+math.hypot(b[0]-a[0],b[1]-a[1]))
    sampled=[];j=0
    for i in range(rings):
        distance=length[-1]*i/(rings-1)
        while j<len(profile)-2 and length[j+1]<distance:j+=1
        t=(distance-length[j])/max(length[j+1]-length[j],1e-12);sampled.append([profile[j][k]*(1-t)+profile[j+1][k]*t for k in range(2)])
    return radial({**params,'profile':sampled,'segments':segments})

def lathe_uv(params,faces):
    """Arc length along the meridian avoids stretching over a flat crown."""
    profile=params['profile'];segments=params.get('segments',64);length=[0.0]
    for a,b in zip(profile,profile[1:]):length.append(length[-1]+math.hypot(b[0]-a[0],b[1]-a[1]))
    total=max(length[-1],1e-12);result=[];rings=len(profile)*segments
    for face in faces:
        coords=[]
        for index in face:
            if index>=rings:coords.append([.5,0.0 if index==rings else 1.0])
            else:coords.append([(index%segments)/segments,length[index//segments]/total])
        if max(v[0] for v in coords)-min(v[0] for v in coords)>.5:
            for uv in coords:
                if uv[0]<.5:uv[0]+=1
        result.append(coords)
    return result

def surface(mat,row,albedo=None,rotation=0,mapping='cylindrical'):
    n=mat.node_tree.nodes;links=mat.node_tree.links;p=n.get('Principled BSDF')
    def node(kind):return n.new('ShaderNode'+kind)
    def link(a,b):links.new(a,b)
    def color(hex):
        c=[int(hex[i:i+2],16)/255 for i in (1,3,5)]
        return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c)+(1,)
    def ramp(source,stops):
        r=node('ValToRGB');cr=r.color_ramp
        for i,(position,c) in enumerate(stops):
            e=cr.elements[i] if i<2 else cr.elements.new(position);e.position=position;e.color=c
        link(source,r.inputs[0]);return r.outputs['Color']
    def noise(vector,scale,detail=3):
        a=node('TexNoise');a.inputs['Scale'].default_value=scale;a.inputs['Detail'].default_value=detail;link(vector,a.inputs['Vector']);return a
    def scaled(vector,values):
        a=node('VectorMath');a.operation='MULTIPLY';a.inputs[1].default_value=values;link(vector,a.inputs[0]);return a.outputs['Vector']
    def mix(fac,a,b):
        m=node('MixRGB');link(fac,m.inputs[0])
        for value,socket in ((a,m.inputs[1]),(b,m.inputs[2])):
            if hasattr(value,'node'):link(value,socket)
            else:socket.default_value=value
        return m.outputs[0]
    coord=node('TexCoord');v=coord.outputs['Generated'];base=color(row['color']);secondary=color(row.get('secondary_color','#d9a648'))
    if row['detail']=='bark':
        secondary=color(row.get('secondary_color',row['color']))
        grain=noise(scaled(v,(20,20,1.3)),row.get('micro_scale',80)/20,3);contrast=row.get('mottle_contrast',.7)
        c=ramp(grain.outputs['Fac'],[(.25,tuple(x*(1-contrast) for x in base[:3])+(1,)),(.75,tuple(min(1,x*(1+contrast*.85)) for x in secondary[:3])+(1,))]);link(c,p.inputs['Base Color'])
        variation=row.get('roughness_variation',0)
        rough=ramp(grain.outputs['Fac'],[(.2,(max(.03,row['roughness']-variation),)*3+(1,)),(.8,(min(1,row['roughness']+variation),)*3+(1,))]);link(rough,p.inputs['Roughness'])
        bump=node('Bump');bump.inputs['Distance'].default_value=row.get('bump_distance',.00012);bump.inputs['Strength'].default_value=.4;link(grain.outputs['Fac'],bump.inputs['Height']);link(bump.outputs[0],p.inputs['Normal']);return
    distort=noise(v,5,3);offset=scaled(distort.outputs['Color'],(row.get('streak_distortion',0),)*3)
    warped=node('VectorMath');warped.operation='ADD';link(v,warped.inputs[0]);link(offset,warped.inputs[1])
    stripe=noise(scaled(warped.outputs['Vector'],row.get('streak_scale',(9,9,.65))),4.5,4)
    cover=row.get('streak_strength',.55)
    mask=ramp(stripe.outputs['Fac'],[(.48+(1-cover)*.12,(0,0,0,1)),(.68+(1-cover)*.06,(1,1,1,1))])
    mottled=noise(v,22,3)
    contrast=row.get('mottle_contrast',.58)
    red=ramp(mottled.outputs['Fac'],[(.25,tuple(x*(1-contrast) for x in base[:3])+(1,)),(.75,tuple(min(1,x*(1+contrast*.38)) for x in base[:3])+(1,))])
    pigments=mix(mask,red,tuple(c*.65 for c in secondary[:3])+(1,))
    if albedo is not None:
        # One local host-verified PNG. Angular mapping wraps around local Z;
        # Generated coordinates are anchored before the projection proxy joins.
        centered=node('VectorMath');centered.operation='SUBTRACT';link(v,centered.inputs[0]);centered.inputs[1].default_value=(.5,.5,0)
        components=node('SeparateXYZ');link(centered.outputs[0],components.inputs[0])
        angle=node('Math');angle.operation='ARCTAN2';link(components.outputs['Y'],angle.inputs[0]);link(components.outputs['X'],angle.inputs[1])
        u=node('Math');u.operation='MULTIPLY_ADD';link(angle.outputs[0],u.inputs[0]);u.inputs[1].default_value=1/(2*math.pi);u.inputs[2].default_value=.5+rotation/360
        uv=node('CombineXYZ');link(u.outputs[0],uv.inputs['X']);link(components.outputs['Z'],uv.inputs['Y'])
        tex=node('TexImage');tex.image=albedo;tex.extension='REPEAT';tex.interpolation='Linear';link(uv.outputs[0],tex.inputs['Vector']);pigments=tex.outputs['Color']
        if mapping=='lathe':
            coords=node('UVMap');coords.uv_map='SurfaceUV';shift=node('VectorMath');shift.operation='ADD';link(coords.outputs[0],shift.inputs[0]);shift.inputs[1].default_value=(rotation/360,0,0);link(shift.outputs[0],tex.inputs['Vector'])
    # Mild russeting in the stem basin, with rougher skin at the crown.
    xyz=node('SeparateXYZ');link(v,xyz.inputs[0]);xy=node('CombineXYZ');link(xyz.outputs['X'],xy.inputs['X']);link(xyz.outputs['Y'],xy.inputs['Y'])
    radial=node('VectorMath');radial.operation='DISTANCE';link(xy.outputs[0],radial.inputs[0]);radial.inputs[1].default_value=(.5,.5,0)
    basin_radius=row.get('basin_radius',.31)
    center=ramp(radial.outputs['Value'],[(max(.00001,basin_radius*.23),(1,1,1,1)),(max(.00002,basin_radius),(0,0,0,1))])
    top=ramp(xyz.outputs['Z'],[(.50 if albedo is not None else .72,(0,0,0,1)),(.78 if albedo is not None else .90,(1,1,1,1))])
    basin=node('Math');basin.operation='MULTIPLY';link(center,basin.inputs[0]);link(top,basin.inputs[1])
    pigments=mix(basin.outputs[0],pigments,color(row.get('basin_color','#786135')))
    lent=node('TexVoronoi');lent.distance='EUCLIDEAN';lent.feature='F1';lent.inputs['Scale'].default_value=row.get('speckle_density',100);link(v,lent.inputs['Vector'])
    size=row.get('speckle_size',.11);strength=row.get('speckle_strength',.7)
    dots=ramp(lent.outputs['Distance'],[(size*.27,(strength,)*3+(1,)),(size,(0,0,0,1))])
    final=pigments if albedo is not None else mix(dots,pigments,color(row.get('speckle_color','#dcb884')))
    micro=noise(v,row.get('micro_scale',220),2);variation=row.get('roughness_variation',.15)
    rough=ramp(micro.outputs['Fac'],[(.15,(max(.03,row['roughness']-variation*.4),)*3+(1,)),(.85,(min(1,row['roughness']+variation),)*3+(1,))]);rough=mix(basin.outputs[0],rough,(.62,.62,.62,1))
    for region in row.get('regions',[]):
        delta=node('VectorMath');delta.operation='SUBTRACT';link(v,delta.inputs[0]);delta.inputs[1].default_value=region['center']
        normalized=scaled(delta.outputs['Vector'],tuple(1/x for x in region['radius']))
        length=node('VectorMath');length.operation='LENGTH';link(normalized,length.inputs[0])
        mask=ramp(length.outputs['Value'],[(.15,(region['opacity'],)*3+(1,)),(1,(0,0,0,1))])
        final=mix(mask,final,color(region['color']));rough=mix(mask,rough,(region['roughness'],)*3+(1,))
    link(final,p.inputs['Base Color']);link(rough,p.inputs['Roughness'])
    bump=node('Bump');bump.inputs['Distance'].default_value=row.get('bump_distance',.000035);bump.inputs['Strength'].default_value=.23;link(micro.outputs['Fac'],bump.inputs['Height']);link(bump.outputs[0],p.inputs['Normal'])
