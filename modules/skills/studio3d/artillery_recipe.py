"""PaK38 exterior game-art recipe using reusable deterministic surface tools.

Art proportions use a nominal wheel diameter of one. Not measured dimensions,
not a functional weapon simulation. Model choices are bounded parameter data.
"""
import math
from modules.skills.studio3d.assembly_geometry import Mesh, panel, add, sub, mul, norm
from modules.skills.studio3d.contract import validate

VERSION='1.7.0'
# value, lower, upper, semantic group, explanation exposed to the planner
PARAMETERS={
 'wheel_form':(0,0,4,'wheels','integer variant: 0 round ribs, 1 pill ridges, 2 broad pressed flutes, 3 shallower pressed flutes and fine dense shoulder marks, 4 continuous dished pressed wheel plate with shallow tapered ribs and seated face fasteners'),
 'spade_detail':(0,0,3,'trails','integer variant: 0 plain blade, 1 pivot seat, 2 flared ground blade/catches, 3 more upright dished shoe with rounded lower corners'),
 'spade_orientation':(0,0,1,'trails','integer variant: 0 world-aligned end fittings, 1 complete spade assembly aligned to its tubular trail frame'),
 'trail_fittings':(0,0,1,'trails','integer variant: 0 plain tube collars, 1 collar-mounted edge bands, top pads, side tabs and seated fasteners'),
 'shield_profile':(0,0,1,'shield','integer variant: 0 plain crest, 1 sloped outer shoulder silhouette and rounded central clearance bridge'),
 'breech_detail':(0,0,1,'breech','integer variant: 0 simple box cover, 1 shaped compact exterior housing and layered attachment details'),
 'assembly_detail':(0,0,1,'cradle','integer variant: 0 simple cheeks, 1 contoured support cheeks, layered saddles and attached fasteners'),
 'control_detail':(0,0,2,'controls','integer variant: 0 plain support, 1 concentric connected handwheel shaft and sight mount, 2 additional seated castings, cover rings and support for the control assembly'),
 'rear_detail':(0,0,3,'breech','integer variant: 0 box exterior, 1 C-profile shell, 2 shallow C-profile face and perforated side guard, 3 adds seated rear face rings, exterior cover plates and attached details'),
 'shield_hardware':(0,0,1,'shield','integer variant: 0 plain lower edge, 1 stepped lower corners and seated two-level hinge tabs'),
 'cradle_front':(0,0,1,'cradle','integer variant: 0 plain trough front, 1 layered end cover, collar and attached lower cover'),
 'finish_detail':(0,0,2,'finish','integer variant: 0 EEVEE, 1 Cycles grain/curvature wear, 2 restrained coating with capped wear, fine shallow grain and low mottle contrast'),
 'track':(1.95,1.65,2.3,'wheels','distance between wheel centers, wheel diameter fixed at 1'),
 'tire_width':(.145,.09,.24,'wheels','axial tyre width, not radial rubber band'),
 'tire_band':(.05,.025,.09,'wheels','radial rubber thickness, radius is 0.5'),
 'wheel_ribs':(8,6,12,'wheels','integer count of broad pressed-disc stiffening ribs'),
 'barrel_length':(2.25,1.8,2.7,'barrel','muzzle exterior distance ahead of axle'),
 'barrel_height':(1.15,.95,1.38,'barrel','horizontal exterior tube center height'),
 'barrel_radius':(.047,.035,.07,'barrel','slender visible outer tube radius'),
 'shield_width':(1.78,1.4,2.15,'shield','total width of curved protective plates'),
 'shield_top':(1.43,1.2,1.65,'shield','highest shield edge'),
 'shield_bottom':(.53,.42,.72,'shield','lower edge above axle'),
 'shield_rake':(.36,.12,.55,'shield','top rearward displacement relative to bottom'),
 'shield_curve':(.15,.06,.3,'shield','outer tips rearward plan curvature'),
 'shield_gap':(.035,.022,.055,'shield','visible separation of paired sheets'),
 'trail_length':(2.85,2.3,3.3,'trails','rearward projected length of round trails'),
 'trail_spread':(1.30,1.0,1.65,'trails','half-width at each spade'),
 'trail_radius':(.078,.058,.10,'trails','round tubular trail radius'),
 'breech_length':(.40,.28,.55,'breech','compact external rear cover length'),
 'breech_width':(.25,.19,.34,'breech','compact external rear cover width'),
 'breech_height':(.32,.24,.42,'breech','compact external rear cover height'),
 'control_radius':(.115,.085,.16,'controls','visible left handwheel radius'),
 'paint_value':(62,38,85,'finish','neutral dark gray paint sRGB value; not fixed highlights'),
 'roughness':(.53,.32,.75,'finish','intact coating roughness'),
 'wear':(.13,0,.32,'finish','sparse coating wear, not stone texture'),
 'exposure':(-.35,-1.2,.5,'lighting','studio exposure compensation'),
}
VARIANTS={'wheel_form','spade_detail','spade_orientation','trail_fittings','shield_profile','breech_detail','assembly_detail','control_detail','rear_detail','shield_hardware','cradle_front','finish_detail'}


def shield_crest(p, y):
    """One surface definition for the shield edge AND its attached fasteners."""
    half=p['shield_width']/2;u=max(0,min(1,(abs(y)-.105)/(half-.105)))
    shoulder=.19*max(0,(u-.65)/.35) if p['shield_profile'] else .085*u**3
    return p['shield_top']-shoulder


def parameters(values=None):
    values=values or {}
    if not isinstance(values,dict) or set(values)-set(PARAMETERS):raise ValueError('Unknown recipe parameter')
    out={k:v[0] for k,v in PARAMETERS.items()};out.update(values)
    for k,v in out.items():
        spec=PARAMETERS[k]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not spec[1]<=v<=spec[2]:raise ValueError('Parameter outside range: '+k)
        if k in VARIANTS|{'wheel_ribs','paint_value'} and type(v) is not int:raise ValueError('Integer parameter: '+k)
    if out['shield_top']-out['shield_bottom']<.55:raise ValueError('Collapsed shield span')
    if out['shield_top']<out['barrel_height']+.12:raise ValueError('Shield must clear visible barrel')
    return out


def describe():
    return {k:{'current_default':v[0],'min':v[1],'max':v[2],'group':v[3],'meaning':v[4]} for k,v in PARAMETERS.items()}



def pressed_wheel_plate(y, w, rad, count):
    """Closed continuous sheet with sculpted, shallow radial pressings.

    A single connected surface replaces the separate rib islands. Axial depth is
    analytic at all radii; fasteners use the same function to contact the sheet.
    Nominal visual geometry, not a reconstruction of wheel manufacturing.
    """
    rings=[rad*x for x in (.15,.22,.30,.40,.51,.62,.73,.84,.94,1.0)]
    n=96
    def depth(r,t):
        ratio=r/rad
        dish=w*(.245+.175*ratio**2)
        inner=max(0,min(1,(ratio-.22)/.16))
        outer=max(0,min(1,(.99-ratio)/.12))
        rib=max(0,math.cos(count*t))**1.25
        return dish+.018*inner*outer*rib
    vertices=[];faces=[]
    for side in (-1,1):
        offset=len(vertices)
        for r in rings:
            for i in range(n):
                t=math.tau*i/n
                vertices.append([r*math.sin(t),y+side*depth(r,t),.5+r*math.cos(t)])
        for j in range(len(rings)-1):
            for i in range(n):
                a=offset+j*n+i;k=offset+j*n+(i+1)%n
                faces.append([a,k,k+n,a+n])
    side_size=len(rings)*n
    for edge in (0,len(rings)-1):
        for i in range(n):
            a=edge*n+i;k=edge*n+(i+1)%n
            faces.append([a,k,side_size+k,side_size+a])
    m=Mesh();m.append(vertices,faces)
    return m,depth


def build(values=None, quality='preview'):
    p=parameters(values);obs=[];groups={};owners={};b=p['barrel_height'];track=p['track'];w=p['tire_width'];rad=.5-p['tire_band']
    gray='#'+format(p['paint_value'],'02x')*3
    mats=[{'id':'paint','color':gray,'roughness':p['roughness'],'metallic':0,'detail':'weathered_paint','micro_scale':650,'roughness_variation':.08,'streak_strength':p['wear']},
          {'id':'steel','color':'#777a7c','roughness':.32,'metallic':1,'detail':'none'},
          {'id':'rubber','color':'#202122','roughness':.8,'metallic':0,'detail':'none'},
          {'id':'dark','color':'#17191b','roughness':.64,'metallic':.12,'detail':'none'}]
    if p['finish_detail']:
        mats[0].update(micro_scale=230,roughness_variation=.14)
        mats[1].update(detail='steel');mats[2].update(detail='rubber')
    if p['finish_detail']==2:
        mats[0].update(micro_scale=800,roughness_variation=.06,mottle_contrast=.12,speckle_strength=.14,bump_distance=.000035)
        mats[1].update(detail='none',roughness=.40)
    def put(o, group, owner=None):
        obs.append(o);groups[o['id']]=group;owners[o['id']]=owner or group;return o
    def box(name,size,pos,group='carriage',mat='paint',bevel=.004,rot=None,visible=True):
        o={'id':name,'kind':'box','material':mat,'params':{'size':size},'position':pos,'shading':'flat','visible':visible,'modifiers':{'bevel':bevel,'bevel_segments':5}}
        if rot:o['rotation']=rot
        return put(o,group)
    def lathe(name,profile,pos,group='carriage',mat='paint',rotation=None,segments=96,caps=True):
        return put({'id':name,'kind':'lathe','material':mat,'params':{'profile':profile,'segments':segments,'caps':caps},'position':pos,'rotation':rotation or [0,0,0],'shading':'smooth'},group)
    def mesh(name,m,group,mat='paint',bevel=0,smooth=True,owner=None):return put(m.object(name,mat,bevel=bevel,smooth=smooth),group,owner)
    def path(name,pts,r,group,mat='paint'):
        return put({'id':name,'kind':'curve','material':mat,'params':{'points':pts,'radius':r},'shading':'smooth'},group)
    fasteners={};seams={}
    def bolt(pos,axis,group,r=.013):
        m=fasteners.setdefault(group,Mesh());a=add(pos,mul(axis,-.003));c=add(pos,mul(axis,.012))
        m.tube(a,c,r,segments=6,rounded=False)
    # Wheel pairs: a real dished closed disc, raised broad ribs, tyre shoulders and longitudinal tread grooves.
    for s,label in ((1,'left'),(-1,'right')):
        group='wheel-'+label;y=s*track/2
        tireprofile=[[rad,-w*.48],[.474,-w*.51],[.495,-w*.40],[.5,-w*.30],[.5,-w*.18],[.496,-w*.17],[.496,-w*.10],[.5,-w*.09],[.5,w*.09],[.496,w*.10],[.496,w*.17],[.5,w*.18],[.5,w*.30],[.495,w*.40],[.474,w*.51],[rad,w*.48],[rad,-w*.48]]
        lathe('tire-'+label,tireprofile,[0,y,.5],group,'rubber',[90,0,0],128,False)
        if p['wheel_form']==4:
            disc,disc_depth=pressed_wheel_plate(y,w,rad,p['wheel_ribs'])
            mesh('disc-'+label,disc,group)
            # Face fasteners are based on the same continuous sheet depth;
            # one ring per visible face, never free-floating bolt instances.
            for side in (-1,1):
                for i in range(count := p['wheel_ribs']):
                    t=(i+.5)*math.tau/count;r=rad*.39
                    bolt([r*math.sin(t),y+side*(disc_depth(r,t)+.001),.5+r*math.cos(t)],[0,side,0],group,.009)
        else:
            profile=[[.002,-w*.33],[.14,-w*.33],[.25,-w*.18],[rad-.025,-w*.43],[rad,-w*.45],[rad+.008,-w*.38],[rad+.008,w*.38],[rad,w*.45],[rad-.025,w*.43],[.25,w*.18],[.14,w*.33],[.002,w*.33]]
            lathe('disc-'+label,profile,[0,y,.5],group,rotation=[90,0,0])
            ribs=Mesh();count=p['wheel_ribs']
            for side in (-1,1):
                for i in range(count):
                    t=i*math.tau/count;start=[.16*math.sin(t),y+side*w*.34,.5+.16*math.cos(t)];end=[(rad-.065)*math.sin(t),y+side*w*.40,.5+(rad-.065)*math.cos(t)]
                    # Broad raised rib rooted in disc, not thin disconnected spokes.
                    ribs.tube(start,end,.025,segments=12,end_radius=.043)
                    bolt(end,[0,side,0],group,.011)
            if p['wheel_form']:
                ribs=Mesh()
                rings=[.135,.16,.19,.24,.30,.36,rad-.045,rad-.02];n=128
                if p['wheel_form']>=2:rings=[.09,.115,.14,.17,.22,.28,.34,rad-.055,rad-.030,rad-.012];n=96
                for side in (-1,1):
                    verts=[];faces=[]
                    for r in rings:
                        for i in range(n):
                            t=i*math.tau/n
                            envelope=max(0,math.sin(math.pi*(r-rings[0])/(rings[-1]-rings[0])))
                            wave=((1+math.cos(t*count))/2)**3
                            depth=w*.21+.016*(r/rad)**2+.032*wave*envelope
                            if p['wheel_form']>=2:
                                # Broad tapered pressed ridges extend nearly to the rim.
                                wave=max(0,math.cos(t*count))**.65
                                envelope=min(1,max(0,(r-.105)/.055))*min(1,max(0,(rad-.015-r)/.035))
                                depth=w*.20+.028*(r/rad)**3+(.025 if p['wheel_form']==3 else .038)*wave*envelope
                            verts.append([r*math.sin(t),y+side*depth,.5+r*math.cos(t)])
                    for j in range(len(rings)-1):
                        for i in range(n):
                            a=j*n+i;k=j*n+(i+1)%n;faces.append([a,k,k+n,a+n])
                    ribs.append(verts,faces)
            mesh('ribs-'+label,ribs,group)
        if p['wheel_form']>=2:
            rims=Mesh()
            for side in (-1,1):
                for radius,depth,tube in ((rad-.012,w*.43,.008),(.115,w*.37,.008),(.069,w*.72,.006)):
                    rims.ring([0,y+side*depth,.5],[0,1,0],radius,tube,64 if radius>.3 else 32,6)
            mesh('rim-steps-'+label,rims,group,'paint' if p['wheel_form']==4 else 'steel')
        hubprofile=[[.002,-.13],[.082,-.13],[.12,-.10],[.13,-.075],[.13,.075],[.12,.10],[.082,.13],[.002,.13]]
        if p['wheel_form']:hubprofile=[[.002,-.12],[.047,-.12],[.055,-.113],[.055,-.10],[.087,-.095],[.10,-.08],[.10,.08],[.087,.095],[.055,.10],[.055,.113],[.047,.12],[.002,.12]]
        lathe('hub-'+label,hubprofile,[0,y,.5],group,'paint',[90,0,0],48 if p['wheel_form']>=2 else 64)
        for i in range(6):
            t=i*math.tau/6;bolt([.085*math.sin(t),y+s*.11,.5+.085*math.cos(t)],[0,s,0],group,.012)
        tread=Mesh()
        tread_count=32 if p['wheel_form']==2 else 64
        for i in range(tread_count):
            t=i*math.tau/tread_count
            for side in (-1,1):
                a=[.497*math.sin(t),y+side*w*.33,.5+.497*math.cos(t)];c=[.491*math.sin(t+.018),y+side*w*.46,.5+.491*math.cos(t+.018)]
                tread.tube(a,c,.002 if p['wheel_form']>=3 else .004,segments=6,rounded=p['wheel_form']<3)
        mesh('tread-'+label,tread,group,'rubber')
    axle=Mesh();axle.tube([0,-track/2,.50],[0,track/2,.50],.087,48);mesh('axle',axle,'carriage')
    box('axle-saddle',[.35,.66,.20],[-.06,0,.50]);box('central-pedestal',[.37,.45,.27],[-.03,0,.69],bevel=.025)
    for s in (-1,1):
        side='left' if s==1 else 'right';m=Mesh()
        m.tube([0,s*.64,.50],[0,s*(track/2-.12),.50],.12,48)
        mesh('axle-collar-'+side,m,'carriage')
        for dx in (-.12,.12):bolt([dx,s*.27,.61],[0,0,1],'carriage',.018)
    # Trail geometry follows one visible welded tube per side; details are seated on the same centerline.
    for s,label in ((1,'left'),(-1,'right')):
        group='trail-'+label;a=[-.20,s*.35,.49];end=[-p['trail_length'],s*p['trail_spread'],.20];axis=norm(sub(end,a));r=p['trail_radius']
        trail=Mesh();trail.tube(a,end,r,48,end_radius=r*.88);mesh('trail-tube-'+label,trail,group)
        collars=Mesh()
        for t in (.025,.27,.64,.90):
            center=add(a,mul(sub(end,a),t));collars.tube(add(center,mul(axis,-.018)),add(center,mul(axis,.018)),r*1.13,32)
            bolt(add(center,[0,0,r*1.1]),[0,0,1],group,.013)
        mesh('trail-collars-'+label,collars,group)
        if p['trail_fittings']:
            from modules.skills.studio3d.trail_details import add_trail_fittings
            add_trail_fittings(a,end,r,label,mesh,bolt)
        for j,t in enumerate((.18,.48,.78)):
            c=add(a,mul(sub(end,a),t));pts=[add(c,[.05,0,r*.85]),add(c,[.05,0,r+.065]),add(c,[-.05,0,r+.065]),add(c,[-.05,0,r*.85])]
            path('trail-handle-'+label+'-'+str(j),pts,.011,group)
        spade_start=len(obs);bolt_start=len(fasteners[group].vertices)
        c=end;box('spade-seat-'+label,[.28,.25,.045],add(c,[-.06,0,.012]),group,bevel=.012)
        grid=[]
        for i in range(9):
            t=i/8;x=c[0]-.05-.18*t+.05*math.sin(t*math.pi);z=.19-.18*t
            if p['spade_detail']:x=c[0]-.08+.085*math.sin(t*math.pi*.8);z=.26-.25*t
            if p['spade_detail']>=2:
                # Concave sheet descends from the seat and flares toward its contact edge.
                x=c[0]-.10-.16*t+.06*math.sin(math.pi*t);z=.25-.24*t
            if p['spade_detail']==3:
                x=c[0]-.10-.07*t+.045*math.sin(math.pi*t);z=.25-.24*t
            samples=(-1,-.75,-.5,-.25,0,.25,.5,.75,1) if p['spade_detail']==3 else (-1,-.5,0,.5,1)
            grid.append([[x+(.015*u*u if p['spade_detail']==3 else 0),c[1]+u*((.145+.055*t) if p['spade_detail']>=2 else (.19 if p['spade_detail'] else .16)),z+(.018*u*u*t**6 if p['spade_detail']==3 else 0)] for u in samples])
        put(panel('spade-blade-'+label,'paint',grid,.018),group)
        pts=[add(c,[.07,0,.06]),add(c,[-.09,0,.12]),add(c,[-.30,0,.40]),add(c,[-.48,0,.43])]
        if p['spade_detail']>=2:pts=[add(c,[.04,0,.06]),add(c,[-.07,s*.025,.08]),add(c,[-.20,s*.14,.32]),add(c,[-.34,s*.19,.35])]
        path('spade-lever-'+label,pts,.025,group)
        for dx in (-.15,.04):
            for dy in (-.09,.09):bolt(add(c,[dx,dy,.04]),[0,0,1],group,.014)
        bracket=Mesh();bracket.tube(add(a,[0,0,-.1]),add(a,[0,0,.1]),.10,32);mesh('trail-pivot-'+label,bracket,group)
        if p['spade_detail']:
            support=Mesh();support.tube(add(c,[0,-.135,.015]),add(c,[0,.135,.015]),.085,48)
            support.box(add(c,[-.025,0,.055]),[.30,.27,.04])
            for sy in (-1,1):
                support.tube(add(c,[.09,sy*.115,.065]),add(c,[-.075,sy*.115,-.07]),.018,16)
                bolt(add(c,[.06,sy*.12,.08]),[0,0,1],group,.017)
            mesh('spade-pivot-seat-'+label,support,group,bevel=.004)
            path('spade-retainer-'+label,[add(c,[.075,-.11,.09]),add(c,[-.12,-.11,.09]),add(c,[-.15,.11,.09]),add(c,[.075,.11,.09])],.009,group,'steel')
            if p['spade_detail']>=2:
                hardware=Mesh()
                for sy in (-1,1):
                    hardware.tube(add(c,[-.02,sy*.135,-.015]),add(c,[-.02,sy*.155,-.015]),.055,32)
                    hardware.box(add(c,[-.08,sy*.13,.065]),[.14,.04,.05])
                    hardware.tube(add(c,[.015,sy*.15,-.025]),add(c,[-.13,sy*.15,.04]),.012,16)
                hardware.ring(add(c,[0,0,.02]),[-1,0,0] if p['spade_orientation'] else axis,.103,.009,48,8)
                mesh('spade-catches-'+label,hardware,group,bevel=.003)
        if p['spade_orientation']:
            from modules.skills.studio3d.assembly_frames import orient_z,rotate_point
            yaw=-s*math.atan2(p['trail_spread']-.35,p['trail_length']-.20)
            orient_z([o for o in obs[spade_start:] if o['id'].startswith('spade-')],end,yaw)
            attached=fasteners[group]
            attached.vertices[bolt_start:]=[rotate_point(v,end,yaw) for v in attached.vertices[bolt_start:]]
    # Low double curved shield: split around tube and one sight slot on weapon-left only.
    width=p['shield_width'];top=p['shield_top'];bottom=p['shield_bottom']
    slot=box('sight-cut',[.9,.095,.24],[.0,width*.30,top-.31],'shield',bevel=0,visible=False)
    def shield_x(y,z): return .36-p['shield_rake']*(z-bottom)/(top-bottom)-p['shield_curve']*(abs(y)/(width/2))**1.4
    for layer in range(2):
        for s,label in ((1,'left'),(-1,'right')):
            grid=[]
            for k in range(9):
                t=k/8;row=[]
                for j in range(14):
                    u=j/13;y=s*(.105+(width/2-.105)*u);z=bottom+(shield_crest(p,y)-bottom)*t
                    row.append([shield_x(y,z)-layer*p['shield_gap'],y,z])
                grid.append(row)
            o=panel('shield-'+label+'-'+str(layer),'paint',grid,.012)
            if s==1:o['modifiers']['difference']=['sight-cut']
            put(o,'shield')
    # Thin upper bridge and lower apron, with gap retained around barrel.
    if not p['shield_profile']:box('shield-upper-bridge',[.025,.22,.095],[shield_x(0,top-.05),0,top-.05],'shield',bevel=.008,rot=[0,-20,0])
    else:
        bridge=[]
        for k in range(3):
            row=[]
            for j in range(17):
                y=(j/16-.5)*.24;lower=top-.22+math.sqrt(max(0,.12**2-y*y));z=lower+(top-lower)*(k/2)
                row.append([shield_x(y,z),y,z])
            bridge.append(row)
        put(panel('shield-upper-bridge','paint',bridge,.018),'shield')
    box('shield-lower-apron',[.024,.58,.18],[.37,0,.51],'shield',bevel=.008,rot=[0,-14,0])
    edge=Mesh()
    for s in (-1,1):
        for j in range(6):
            y=s*(.16+j*(width/2-.20)/5);z=shield_crest(p,y)-.035
            bolt([shield_x(y,z)+.008,y,z],[1,0,0],'shield',.012)
        y=s*(width/2-.035)
        for z in (bottom+.08,(bottom+top)/2,shield_crest(p,y)-.06):
            bolt([shield_x(y,z)+.008,y,z],[1,0,0],'shield',.012)
        edge.tube([-.06,s*.67,.65],[-.40,s*.36,.74],.021,24)
    mesh('shield-struts',edge,'shield')
    # Horizontal tapered visible barrel and a purely visual dark recessed bore.
    length=p['barrel_length'];br=p['barrel_radius']
    profile=[[br*1.65,-.57],[br*1.65,-.35],[br*1.30,-.30],[br*1.30,.23],[br*1.10,.28],[br*1.10,length-.29],[br,length-.25],[br,length-.20],[br*.64,length-.20],[br*.64,length-.8],[.0005,length-.83]]
    lathe('barrel',profile,[0,0,b],'barrel','paint',[0,90,0],128,False)
    for i,x in enumerate((-.33,.25,length-.27)):
        lathe('barrel-band-'+str(i),[[br*1.33,-.016],[br*1.42,-.010],[br*1.42,.010],[br*1.33,.016]],[x,0,b],'barrel','steel',[0,90,0],64)
    for i,x in enumerate((length-.145,length-.035)):
        box('brake-port-'+str(i),[.073,.30,.072],[x,0,b],'barrel',bevel=.009,visible=False)
    bore=put({'id':'muzzle-opening','kind':'cylinder','material':'dark','params':{'radius':br*.65,'depth':.42,'segments':64},'position':[length-.05,0,b],'rotation':[0,90,0],'visible':False},'barrel')
    brake=lathe('muzzle-brake',[[br*1.1,-.25],[br*1.6,-.21],[br*1.72,-.18],[br*1.72,.02],[br*1.55,.05]],[length,0,b],'barrel','paint',[0,90,0],96)
    brake['modifiers']={'difference':['brake-port-0','brake-port-1','muzzle-opening'],'bevel':.003,'bevel_segments':4}
    # Layered external cradle and compact rear casing; no invented rearward tube.
    box('cradle-trough',[1.46,.23,.13],[.08,0,b-.19],'cradle',bevel=.018)
    rails=Mesh()
    for s in (-1,1):
        rails.tube([-.60,s*.15,b-.13],[.77,s*.15,b-.13],.027,32)
        rails.tube([-.20,s*.19,.85],[-.20,s*.19,b+.07],.06,32)
        for x in (-.52,-.15,.25,.66):bolt([x,s*.13,b-.21],[0,s,0],'cradle',.012)
    mesh('cradle-rails',rails,'cradle')
    rear=-.59;box('breech-casing',[p['breech_length'],p['breech_width'],p['breech_height']],[rear,0,b-.015],'breech',bevel=.03)
    box('breech-top-cover',[p['breech_length']*.75,p['breech_width']*.9,.028],[rear,0,b+p['breech_height']/2],'breech',bevel=.008)
    # Cosmetic rear visible C-form face, recess not a functional ammunition chamber.
    x=rear-p['breech_length']/2-.008
    box('breech-face-upper',[.025,p['breech_width']*.95,.075],[x,0,b+.10],'breech',bevel=.012)
    box('breech-face-lower',[.025,p['breech_width']*.95,.075],[x,0,b-.12],'breech',bevel=.012)
    lathe('breech-recess',[[.001,-.003],[.052,-.003],[.061,0],[.061,.008]],[x-.015,0,b-.015],'breech','dark',[0,90,0],48)
    path('breech-top-grip',[[rear-.05,-.055,b+.18],[rear-.05,-.055,b+.25],[rear-.05,.055,b+.25],[rear-.05,.055,b+.18]],.012,'breech')
    cheeks=Mesh()
    for s in (-1,1):
        cheeks.box([-.30,s*.22,b-.22],[.49,.04,.40])
        cheeks.tube([-.15,s*.19,b-.05],[-.15,s*.29,b-.05],.10,48)
        for z in (b-.35,b-.04):bolt([-.33,s*.245,z],[0,s,0],'cradle',.018)
    mesh('cradle-cheeks',cheeks,'cradle',bevel=.012,smooth=False)
    # Connected control assembly concentrated on weapon-left, simpler opposite support.
    controls=Mesh();controls.tube([-.39,.24,.82],[-.39,.47,.82],.055,32);controls.box([-.39,.29,.80],[.15,.13,.18]);controls.tube([-.51,.32,.80],[-.51,.32,1.17],.025,32)
    mesh('control-support',controls,'controls',bevel=.004)
    c=[-.40,.49,.90];wheel=Mesh();wheel.ring(c,[0,1,0],p['control_radius'],.012,64,10)
    for i in range(4):
        t=i*math.tau/4;wheel.tube(c,add(c,[math.cos(t)*p['control_radius'],0,math.sin(t)*p['control_radius']]),.008,12)
    wheel.tube(add(c,[0,-.03,0]),add(c,[0,.022,0]),.026,24)
    wheel.tube(add(c,[p['control_radius']*.72,0,p['control_radius']*.7]),add(c,[p['control_radius']*.72,.06,p['control_radius']*.7]),.012,16)
    mesh('handwheel-left',wheel,'controls','steel',owner='handwheel-left')
    sight=Mesh();sight.tube([-.51,.32,1.15],[-.51,.32,1.29],.02,24);sight.box([-.51,.32,1.29],[.12,.055,.045]);mesh('sight-exterior',sight,'controls',bevel=.004)
    # Distinct perforated exterior side arm from the reference, supported at its root.
    for i in range(3):
        put({'id':'arm-hole-'+str(i),'kind':'cylinder','material':'paint','params':{'radius':.032,'depth':.15,'segments':32},'position':[-.67-i*.095,.15,b-.04],'rotation':[90,0,0],'visible':False},'breech')
    arm=box('external-arm',[.46,.035,.105],[-.76,.15,b-.04],'breech',bevel=.025)
    arm['modifiers']['difference']=['arm-hole-'+str(i) for i in range(3)]
    if p['breech_detail']:
        casing=next(o for o in obs if o['id']=='breech-casing');casing['modifiers']['bevel']=.055
        covers=Mesh()
        for s in (-1,1):
            covers.tube([rear-.02,s*.13,b-.02],[rear-.02,s*.19,b-.02],.08,40)
            covers.box([rear+.10,s*.135,b-.02],[.07,.035,.30])
            for dx in (-.10,.10):bolt([rear+dx,s*.13,b+.12],[0,s,0],'breech',.012)
        covers.box([rear-.02,0,b-.23],[.22,.18,.13]);mesh('breech-layered-covers',covers,'breech',bevel=.01)
    if any(p[k] for k in ('assembly_detail','control_detail','rear_detail','shield_hardware','cradle_front')):
        from modules.skills.studio3d.exterior_details import refine
        refine(p,obs,groups,owners,put,mesh,box,lathe,path,bolt)
    # Consolidate small attached fasteners per semantic ownership, not one object per bolt.
    for group,m in fasteners.items():mesh('fasteners-'+group,m,group,'steel',bevel=.001,smooth=False)
    scene=validate({'schema':'jarvis.studio3d.v1','units':'m','title':'PaK38 · exterior high-detail candidate','materials':mats,'objects':obs,
      'render':{'engine':'CYCLES' if p['finish_detail'] else 'BLENDER_EEVEE_NEXT','quality':quality,'view':'rear','camera_direction':[-1.2,1.8,.9],'five_views':True,'exposure':p['exposure'],'floor_color':'#999999','world_color':'#b9b9b9','world_strength':.40,'lights':[{'position':[1,1.4,2.2],'power':220,'size':1.5,'color':'#fff8ef'},{'position':[-1,-1,1.2],'power':110,'size':1.3,'color':'#e7efff'},{'position':[-1.5,1,1.7],'power':170,'size':1.0,'color':'#ffffff'}]},
      'unfulfilled':['Candidate exterior proportions are artistic estimates, not measured historical geometry.','Reference images contain conflicts; one consistent exterior is prioritized using recorded policy.','High-poly user approval pending; no low-poly, baking or LOD.','GLB base PBR lacks procedural coating microdetail retained in Blender.','Motion ownership is declared; pivots and animation are not yet certified.']})
    return scene,{'recipe':'pak38-exterior','version':VERSION,'parameters':p,'groups':groups,'motion_owners':owners,'historical_certification':False}
