"""Optional visual assemblies for the bounded PaK38 recipe.

Original exterior art approximations in nominal wheel units. These are not
mechanical specifications. Every detail has a visible mounting surface and an
explicit rigid ownership; no invented operational internals are generated.
"""
import math
from modules.skills.studio3d.assembly_geometry import Mesh, panel


def refine(p, objects, groups, owners, put, mesh, box, lathe, path, bolt):
    b=p['barrel_height']
    def remove(*names):
        objects[:]=[o for o in objects if o['id'] not in names]
        for name in names:groups.pop(name,None);owners.pop(name,None)
    if p['shield_hardware']:
        remove('shield-lower-apron')
        width=p['shield_width'];bottom=p['shield_bottom'];top=p['shield_top']
        def sx(y,z):return .36-p['shield_rake']*(z-bottom)/(top-bottom)-p['shield_curve']*(abs(y)/(width/2))**1.4
        tabs=Mesh()
        for s in (-1,1):
            grid=[]
            for k in range(3):
                row=[]
                for j in range(6):
                    u=j/5;y=s*(.12+(width/2-.17)*u);z=bottom-.12+(k/2)*.13+.04*u
                    row.append([sx(y,z)-.008,y,z])
                grid.append(row)
            put(panel('shield-lower-flap-'+str(s),'paint',grid,.014),'shield')
            y=s*width*.35
            for z in (bottom+.08,bottom-.045):
                x=sx(y,z)
                tabs.box([x+.022,y,z],[.038,.085,.095])
                tabs.tube([x+.037,y-.047,z],[x+.037,y+.047,z],.017,16)
                for dy in (-.026,.026):bolt([x+.045,y+dy,z+.03],[1,0,0],'shield',.010)
        mesh('shield-seated-tabs',tabs,'shield',bevel=.003)
    if p['cradle_front']:
        caps=Mesh();x=.82
        caps.box([x,0,b-.19],[.065,.23,.14])
        caps.tube([x+.02,0,b-.18],[x+.065,0,b-.18],.065,32)
        caps.tube([x+.060,0,b-.18],[x+.078,0,b-.18],.035,24)
        for y in (-.087,.087):
            for z in (b-.235,b-.145):bolt([x+.035,y,z],[1,0,0],'cradle',.010)
        caps.box([.14,0,.56],[.09,.15,.26])
        for z in (.47,.64):bolt([.19,0,z],[1,0,0],'cradle',.017)
        mesh('layered-cradle-front',caps,'cradle',bevel=.006,smooth=False)
    if p['assembly_detail']:
        remove('cradle-cheeks','central-pedestal','axle-saddle')
        cheeks=Mesh()
        outline=[[-.69,b-.29],[-.65,b+.02],[-.48,b+.15],[-.36,b+.16],[-.31,b+.03],
                 [-.06,b-.01],[.08,b-.18],[.04,b-.42],[-.20,b-.52],[-.49,b-.48]]
        for s in (-1,1):
            cheeks.extrude(outline,1,s*.245-.026,s*.245+.026)
            cheeks.tube([-.19,s*.24,b-.10],[-.19,s*.30,b-.10],.095,48)
            cheeks.tube([-.19,s*.298,b-.10],[-.19,s*.32,b-.10],.055,40)
            for x,z in ((-.54,b-.24),(-.55,b-.03),(-.16,b-.39),(-.38,b-.41)):
                bolt([x,s*.275,z],[0,s,0],'cradle',.014)
        mesh('contoured-cheeks',cheeks,'cradle',bevel=.012,smooth=False)
        saddle=Mesh()
        saddle.extrude([[-.32,.43],[.12,.43],[.16,.54],[.09,.63],[-.23,.63],[-.36,.56]],1,-.34,.34)
        saddle.tube([-.10,0,.56],[-.10,0,.70],.20,64)
        saddle.tube([-.10,0,.69],[-.10,0,.74],.24,64)
        for s in (-1,1):
            saddle.tube([0,s*.36,.50],[0,s*.59,.50],.115,40)
            saddle.tube([0,s*.57,.50],[0,s*.60,.50],.133,40)
            saddle.box([-.10,s*.40,.59],[.21,.19,.035])
            for x in (-.17,-.025):bolt([x,s*.42,.612],[0,0,1],'carriage',.017)
        mesh('layered-saddle',saddle,'carriage',bevel=.008,smooth=False)
        front=Mesh()
        front.tube([.07,0,.54],[.19,0,.54],.087,48)
        for i in range(6):
            t=i*math.tau/6;bolt([.19,.067*math.cos(t),.54+.067*math.sin(t)],[1,0,0],'carriage',.012)
        mesh('saddle-face',front,'carriage',bevel=.003)
    if p['control_detail']:
        remove('control-support','sight-exterior')
        control=Mesh()
        # Shared centerline reaches from its cheek seat through housing to hub.
        c=[-.40,.49,.90]
        control.tube([c[0],.24,c[2]],[c[0],.50,c[2]],.028,40)
        control.tube([c[0],.29,c[2]],[c[0],.405,c[2]],.077,48)
        control.tube([c[0],.398,c[2]],[c[0],.421,c[2]],.087,48)
        control.tube([-.50,.32,.76],[-.50,.32,1.21],.037,32)
        control.tube([-.50,.32,.79],[-.50,.32,.92],.065,40)
        control.tube([-.50,.32,1.055],[-.50,.32,1.11],.053,40)
        control.tube([-.50,.32,1.19],[-.50,.32,1.24],.048,40)
        control.box([-.49,.285,.77],[.16,.13,.055])
        for i in range(5):
            t=i*math.tau/5;bolt([c[0]+.063*math.cos(t),.423,c[2]+.063*math.sin(t)],[0,1,0],'controls',.010)
        mesh('connected-control-housing',control,'controls',bevel=.003)
        sight=Mesh();sight.tube([-.57,.32,1.25],[-.44,.32,1.25],.025,32)
        sight.tube([-.50,.32,1.20],[-.50,.32,1.25],.023,24)
        sight.box([-.50,.32,1.18],[.12,.08,.035])
        mesh('sight-mounted',sight,'controls',bevel=.003)
        if p['control_detail']==2:
            # Exterior visual art, based on the left/rear silhouettes only.
            # One continuous pedestal joins the existing base and the wheel
            # shaft housing; the additional collars are seated on this body.
            body=Mesh()
            body.box([-.49,.325,.81],[.18,.12,.13])
            body.tube([-.49,.375,.81],[-.49,.415,.81],.055,40)
            body.tube([-.49,.413,.81],[-.49,.424,.81],.047,40)
            # The sight's existing upright is supported by the same pedestal.
            # This small casting overlaps that upright and the rear of the box.
            body.tube([-.50,.32,.86],[-.50,.32,.99],.044,32)
            body.box([-.515,.32,1.13],[.095,.10,.07])
            body.tube([-.515,.32,1.15],[-.515,.32,1.205],.042,32)
            mesh('control-seated-castings',body,'controls',bevel=.003)
            trim=Mesh()
            trim.ring([-.49,.425,.81],[0,1,0],.035,.004,32,6)
            trim.tube([-.49,.424,.81],[-.49,.437,.81],.017,24)
            trim.ring([-.50,.32,1.02],[0,0,1],.038,.004,32,6)
            # This diagonal brace terminates inside the upper casting and base.
            trim.tube([-.545,.31,.79],[-.50,.31,1.12],.008,16)
            mesh('control-seated-trim',trim,'controls','steel')
            for x,z in ((-.545,.77),(-.435,.77),(-.545,.85),(-.435,.85)):
                bolt([x,.386,z],[0,1,0],'controls',.008)
    if p['rear_detail']:
        remove('breech-casing','breech-face-upper','breech-face-lower','breech-layered-covers')
        length=p['breech_length'];width=p['breech_width'];height=p['breech_height'];rear=-.59;face=rear-length/2
        shell=Mesh()
        outline=[[-width/2,b-height/2],[width/2,b-height/2],[width/2,b-.075],
                 [.015,b-.07],[-.045,b-.035],[-.045,b+.035],[.015,b+.07],
                 [width/2,b+.075],[width/2,b+height/2],[-width/2,b+height/2]]
        shell.extrude(outline,0,face,face+.055 if p['rear_detail']>=2 else rear+length/2)
        mesh('shaped-rear-cover',shell,'breech',bevel=.012,smooth=False)
        if p['rear_detail']>=2:
            # A shallow cosmetic relief on a closed exterior housing avoids the
            # through-open side tunnel of variant1. No operational internals.
            box('rear-cover-body',[length-.045,width,height],[rear+.027,0,b],'breech',bevel=.025)
            remove('external-arm')
            arm=Mesh();cx=-.96;z=b-.04;radius=.0525
            outline=[[-.53,z-radius],[-.53,z+radius]]+[[cx+radius*math.cos(a),z+radius*math.sin(a)] for a in [math.pi/2+i*math.pi/12 for i in range(13)]]
            arm.extrude(outline,1,.1325,.1675)
            o=mesh('external-arm',arm,'breech',bevel=.004,smooth=False)
            o['modifiers']['difference']=['arm-hole-'+str(i) for i in range(3)]
        collars=Mesh()
        for s in (-1,1):
            collars.tube([rear+.10,s*width/2,b],[rear+.10,s*(width/2+.055),b],.075,48)
            collars.box([rear+.12,s*(width/2+.01),b-.04],[.055,.035,.23])
            bolt([face-.003,s*(width/2-.028),b+.115],[-1,0,0],'breech',.012)
            bolt([face-.003,s*(width/2-.028),b-.115],[-1,0,0],'breech',.012)
        collars.extrude([[-.10,b-.14],[.10,b-.14],[.065,b-.34],[-.065,b-.34]],0,rear-.09,rear+.10)
        mesh('rear-cover-mounts',collars,'breech',bevel=.01,smooth=False)
        for o in objects:
            if o['id'].startswith('arm-hole-'):o['params']['radius']=.039
        path('rear-upper-latch',[[rear-.04,.09,b+height/2],[rear+.08,.09,b+height/2+.015],[rear+.12,.02,b+height/2+.015]],.010,'breech','steel')
        if p['rear_detail']==3:
            # Cosmetic external details read from the rear/side reference: an
            # inset circular border, a short face lever, and seated side covers.
            # The circular face remains closed; this is NOT a chamber or action.
            # Every decorative piece meets the existing closed cover or a plate.
            detail=Mesh();face_z=b-.015
            detail.ring([face-.004,0,face_z],[1,0,0],.060,.005,32,6)
            # The lever root touches the bezel and the tip rests on the face;
            # no separate loose handle, hidden rods or mechanical claim.
            detail.tube([face-.013,-.044,face_z-.016],[face-.013,-width*.37,face_z-.055],.009,16)
            detail.tube([face-.018,-width*.37,face_z-.055],[face+.006,-width*.37,face_z-.055],.018,24)
            # Both cover plates overlap the casing sides and have rounded caps.
            for s in (-1,1):
                y=s*(width/2+.005)
                detail.box([rear+.035,y,b+.025],[length*.37,.022,height*.39])
                detail.tube([rear+.08,s*(width/2),b+.025],[rear+.08,s*(width/2+.022),b+.025],.043,24)
            mesh('rear-seated-cosmetic-fittings',detail,'breech',bevel=.002)
            # Small rear-facing screws sit on the actual outer face on both
            # sides of the open silhouette rather than on the notch itself.
            for sy in (-1,1):
                for dz in (-.105,.105):bolt([face-.002,sy*(width/2-.025),b+dz],[-1,0,0],'breech',.009)
