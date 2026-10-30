"""Authored head detail for the reference study; no generated code or textures.

Coordinate convention: X forward, Y left, Z up.  Returns scene-contract data
only, for use with the existing pinned Blender worker.  The shapes are a
manually authored approximation, not a claim of reference reconstruction.
"""
import math
from modules.skills.studio3d.character_contract import validate_parameters

VERSION='0.4.0'


def head_objects(params):
    p=validate_parameters(params);s=p['height']/1.68;out=[]
    def vec(x):return [round(v*s,7) for v in x]
    def mesh(name,vertices,faces,mat):
        out.append({'id':name,'kind':'mesh','material':mat,
                    'params':{'vertices':[vec(v) for v in vertices],'faces':faces},'shading':'smooth'})
    def line(name,points,radius,mat):
        out.append({'id':name,'kind':'curve','material':mat,
                    'params':{'points':[vec(v) for v in points], 'radius':radius*s,'closed':False}})
    def loft(name,rings,mat,subdivision=1):
        out.append({'id':name,'kind':'loft','material':mat,
                    'params':{'rings':[[vec(pt) for pt in row] for row in rings], 'closed':True,'caps':True},
                    'modifiers':{'subdivision':subdivision}})
    def ribbon(name,centers,widths,mat):
        rings=[]
        for (x,y,z),w in zip(centers,widths):
            thick=max(.001,w*.08)
            rings.append([(x-thick,y-w,z),(x+thick,y-w,z),(x+thick,y+w,z),(x-thick,y+w,z)])
        loft(name,rings,mat,2)
    def eye_shape(name,sign,material,scale=1):
        # Almond, with both ends directed slightly upward at the outer corner.
        verts=[(.0835,sign*.034,1.507)]
        for i in range(24):
            t=2*math.pi*i/24
            yy=sign*(.034+math.cos(t)*.020*scale)
            zz=1.507+math.sin(t)*(.010 if math.sin(t)>0 else .007)*scale+(.002*math.cos(t))
            x=.0835-.004*(abs(yy)/.065)**2
            verts.append((x,yy,zz))
        mesh(name,verts,[[0,i+1,(i+1)%24+1] for i in range(24)],material)
    def disk(name,sign,center,ry,rz,material,depth):
        y,z=center;verts=[(.0855+depth,sign*y,z)]
        for i in range(20):
            a=math.tau*i/20;verts.append((.0855+depth,sign*(y+ry*math.cos(a)),z+rz*math.sin(a)))
        mesh(name,verts,[[0,i+1,(i+1)%20+1] for i in range(20)],material)
    # Wide cap: the lower front edge stays behind the face and eye elements.
    rings=[]
    for j in range(10):
        t=j/9;z=1.652-.107*t
        r=math.sqrt(max(.0003,1-((z-1.535)/.117)**2))
        rings.append([(-.018+(.110*p['hair_volume'])*r*math.cos(i*math.tau/32),
                       (.085*p['hair_volume'])*r*math.sin(i*math.tau/32),
                       z-.035*(j/9)*max(0,-math.cos(i*math.tau/32))) for i in range(32)])
    loft('hair-scalp-refined',rings,'hair',2)
    # Tapered overlapping panels produce separated tips instead of a hard,
    # perfectly horizontal curtain; back coverage remains editable panels.
    for k in range(13):
        y=(k-6)*.0115; tip=y*1.13
        ztip=1.368+(k%4)*.005-(p['hair_length']-1)*.045
        ribbon('back-hair-refined-'+str(k),[(-.060,y*.72,1.575),(-.078,y*.9,1.505),
                (-.073,y,1.445),(-.058,tip,ztip)],[.012,.013,.011,.001],'hair')
    # A swept central fringe closes the small gap left between paired locks.
    ribbon('bang-refined-center',[(.081,-.005,1.625),(.091,-.003,1.585),
           (.096,.004,1.548),(.090,.020,1.503)],[.019,.022,.016,.001],'hair')
    # Offset narrow tapered sheets form a layered, broken fringe rather than tubes.
    for sign,label in [(-1,'r'),(1,'l')]:
        for k in range(3):
            yy=.009+k*.017+(0.002 if sign>0 else -.001);end=.022+k*.018
            tip=([1.506,1.496,1.519] if sign<0 else [1.500,1.515,1.509])[k]
            ribbon('bang-refined-'+label+str(k),[(.082,sign*(yy*.65),1.614-k*.002),(.094,sign*yy,1.574-k*.003),
                   (.095,sign*(yy+.006),1.536-k*.002),(.089,sign*end,tip)],
                   [.019,.018,.012,.001],'hair')
        # Broad side locks frame face, taper and curl outward at the shoulders.
        for k in range(4):
            y=sign*(.057+k*.009)
            ribbon('side-hair-refined-'+label+str(k),[(.005,y,1.574),(.004,sign*(.070+k*.009),1.50),
                   (.012,sign*(.075+k*.009),1.43),(.025,sign*(.079+k*.011),1.366+(.012,.027,.003,.020)[k])],
                   [.011,.012,.009,.001],'hair')
        eye_shape('eye-almond-'+label,sign,'eye',p['eye_scale'])
        disk('iris-refined-'+label,sign,(.034,1.508),.0085*p['eye_scale'],.009*p['eye_scale'],'iris',.002)
        disk('pupil-refined-'+label,sign,(.034,1.508),.0036,.0065,'pupil',.003)
        disk('eye-glint-'+label,sign,(.0315,1.511),.0018,.002,'eye',.004)
        upper=[(.087-.003*abs(y)/.06,sign*y,z) for y,z in ((.014,1.507),(.020,1.516),(.033,1.519),(.044,1.518),(.054,1.512))]
        lower=[(.086-.003*abs(y)/.06,sign*y,z) for y,z in ((.015,1.507),(.023,1.500),(.034,1.498),(.047,1.502),(.054,1.512))]
        line('upper-lid-refined-'+label,upper,.0015,'pupil')
        line('lower-lid-refined-'+label,lower,.001,'brow')
        line('brow-refined-'+label,[(.082,sign*.017,1.529),(.084,sign*.032,1.532),(.081,sign*.050,1.527)],.0012,'brow')
    # Delicate nose and closed mouth: bounded geometry, no face texture.
    line('nose-refined',[(.084,-.002,1.486),(.092,0,1.478),(.084,.002,1.477)],.0011,'skin')
    line('mouth-refined',[(.078,-.011,1.458),(.081,0,1.456),(.078,.011,1.458)],.0011,'brow')
    return out
