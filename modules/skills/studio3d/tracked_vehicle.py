"""Original bounded visual reconstruction. No weapon/vehicle engineering simulation."""
import math
from modules.skills.studio3d.contract import validate,SCHEMA

def panzer2():
    objects=[]
    def add(name,kind,mat,params,pos=None,rot=None,mod=None):
        o={'id':name,'kind':kind,'material':mat,'params':params}
        if kind in ('mesh','loft'):o['shading']='flat'
        if pos:o['position']=pos
        if rot:o['rotation']=rot
        if mod:o['modifiers']=mod
        objects.append(o)
    def box(name,mat,size,pos,rot=None,bevel=.006):add(name,'box',mat,{'size':size},pos,rot,{'bevel':bevel} if bevel else None)
    def mesh(name,mat,vertices,faces):add(name,'mesh',mat,{'vertices':vertices,'faces':faces})
    def prism(name,mat,rings):add(name,'loft',mat,{'rings':rings,'closed':True,'caps':True},mod={'bevel':.006})
    def polygon(z,front,rear,width,chamfer=.12):return [[front-chamfer,-width,z],[front,-width+chamfer,z],[front,width-chamfer,z],[front-chamfer,width,z],[rear+chamfer,width,z],[rear,width-chamfer,z],[rear,-width+chamfer,z],[rear+chamfer,-width,z]]
    # Closed, angled armor surfaces, with actual geometric side profiles.
    prism('lower-hull','paint',[polygon(.43,1.8,-1.85,.62),polygon(.92,2.12,-2.11,.77),polygon(1.10,1.76,-1.98,.77)])
    prism('upper-casemate','paint',[polygon(1.02,1.76,-1.95,.77),polygon(1.35,1.34,-1.85,.69)])
    box('engine-deck','paint',[1.31,1.31,.08],[-1.16,0,1.38])
    prism('driver-hood','paint',[polygon(1.32,1.43,.69,.47),polygon(1.53,1.19,.72,.43)])
    box('driver-visor','edge',[.055,.29,.12],[1.285,.24,1.45],[0,-16,0],.012)
    box('visor-dark-slit','dark',[.02,.24,.022],[1.318,.24,1.46],[0,-16,0],.003)
    # Turret offset toward the vehicle left, eight-sided taper and cupola.
    cx,cy=.10,.16
    ring=lambda z,r:[[cx+r*math.cos(i*math.tau/8+math.pi/8),cy+r*.84*math.sin(i*math.tau/8+math.pi/8),z] for i in range(8)]
    prism('turret-shell','paint',[ring(1.40,.77),ring(1.82,.63),ring(1.86,.61)])
    add('turret-race','cylinder','edge',{'radius':.57,'depth':.055},[cx,cy,1.40])
    box('mantlet','edge',[.12,.54,.24],[.82,cy,1.66],bevel=.025)
    # Exterior display geometry only; no internal mechanism or functional firing.
    add('main-display-barrel','lathe','steel',{'profile':[[.052,0],[.052,.17],[.029,.21],[.025,.77],[.031,.80],[.031,.86],[.018,.86],[.018,.80]],'segments':32},[.88,cy+.10,1.69],[0,90,0])
    add('coaxial-display-barrel','cylinder','steel',{'radius':.015,'depth':.35},[1.05,cy-.13,1.63],[0,90,0])
    add('cupola','lathe','paint',{'profile':[[.23,0],[.23,.08],[.205,.08],[.205,.17],[.225,.18],[.225,.21]],'segments':32},[-.23,cy,1.88])
    add('cupola-lid','cylinder','paint',{'radius':.234,'depth':.035},[-.23,cy,2.108])
    box('turret-roof-hatch','edge',[.43,.37,.025],[.23,cy,1.878],bevel=.035)
    # Batch helpers retain detailed disconnected components as one editable
    # named mesh per semantic group, without exceeding the object budget.
    def cubes(name,mat,cells):
        vertices=[];faces=[]
        for center,size,angle in cells:
            start=len(vertices);c,s=math.cos(angle),math.sin(angle)
            for a,b,d in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]:
                x,z=a*size[0]/2,d*size[2]/2;vertices.append([center[0]+c*x-s*z,center[1]+b*size[1]/2,center[2]+s*x+c*z])
            faces.extend([[start+i for i in f] for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]])
        mesh(name,mat,vertices,faces)
    bolts=[];grilles=[]
    for side in (-1,1):
        suffix='left' if side>0 else 'right';y=side*.965
        box('fender-'+suffix,'paint',[4.81,.36,.04],[0,side*.96,1.08],bevel=.008)
        for x,angle in [(2.26,25),(-2.26,-25)]:box('mudguard-'+suffix+('-front' if x>0 else '-rear'),'paint',[.33,.36,.025],[x,side*.96,1.005],[0,angle,0],.004)
        # Capsule track path around end wheels, with individual shoes/grousers.
        radius=.38;a=1.97;z=.56;n=116;shoes=[];ridges=[];pins=[]
        path=[[-1.5,.025],[1.5,.025]]
        path += [[a+radius*math.cos(t),z+radius*math.sin(t)] for t in [-math.pi/3+j*5*math.pi/6/30 for j in range(31)]]
        path += [[-a+radius*math.cos(t),z+radius*math.sin(t)] for t in [math.pi/2+j*5*math.pi/6/30 for j in range(31)]]
        lengths=[math.dist(path[i],path[(i+1)%len(path)]) for i in range(len(path))];circ=sum(lengths)
        for i in range(n):
            d=(i+.5)*circ/n
            j=0
            while d>lengths[j]:d-=lengths[j];j+=1
            p0,p1=path[j],path[(j+1)%len(path)];f=d/lengths[j];x=p0[0]+f*(p1[0]-p0[0]);zz=p0[1]+f*(p1[1]-p0[1]);angle=math.atan2(p1[1]-p0[1],p1[0]-p0[0])
            shoes.append(([x,y,zz],[circ/n*.92,.29,.045],angle))
            ridges.append(([x+math.sin(angle)*.029,y,zz-math.cos(angle)*.029],[.018,.30,.018],angle))
            pins.append(([x,y+side*.151,zz],[.026,.018,.026],angle))
        cubes('track-shoes-'+suffix,'track',shoes);cubes('track-grousers-'+suffix,'steel',ridges);cubes('track-pins-'+suffix,'rust',pins)
        # Five independent road wheels, four upper return rollers per side.
        for i,x in enumerate([-1.35,-.675,0,.675,1.35]):
            add('road-tire-'+suffix+str(i),'lathe','rubber',{'profile':[[.19,-.11],[.273,-.11],[.285,-.08],[.285,.08],[.273,.11],[.19,.11]],'segments':32},[x,y,.31],[90,0,0])
            add('road-disc-'+suffix+str(i),'lathe','paint',{'profile':[[.01,-.095],[.225,-.095],[.235,-.075],[.235,.075],[.225,.095],[.01,.095]],'segments':32},[x,y,.31],[90,0,0])
            add('road-hub-'+suffix+str(i),'cylinder','edge',{'radius':.073,'depth':.04},[x,y+side*.115,.31],[90,0,0])
            for j in range(6):
                t=j*math.tau/6;bolts.append(([x+.09*math.cos(t),y+side*.14,.31+.09*math.sin(t)],[.018,.015,.018],0))
        for i,x in enumerate([-1.18,-.39,.39,1.18]):
            add('return-'+suffix+str(i),'cylinder','rubber',{'radius':.083,'depth':.18},[x,y,.86],[90,0,0])
        for label,x in [('drive',1.97),('idler',-1.97)]:
            add(label+'-rim-'+suffix,'lathe','edge',{'profile':[[.24,-.08],[.33,-.08],[.355,-.055],[.355,.055],[.33,.08],[.24,.08]],'segments':48},[x,y,.56],[90,0,0])
            add(label+'-hub-'+suffix,'cylinder','paint',{'radius':.10,'depth':.22},[x,y,.56],[90,0,0])
            spokes=[]
            for i in range(8):
                t=i*math.tau/8;spokes.append(([x+.18*math.cos(t),y,.56+.18*math.sin(t)],[.23,.08,.035],t))
            cubes(label+'-spokes-'+suffix,'paint',spokes)
        for i,x in enumerate([-1.45,-.75,-.05,.65,1.35]):box('spring-'+suffix+str(i),'edge',[.50,.06,.07],[x,side*.80,.68],[0,12,0],.005)
        box('stowage-box-'+suffix,'paint',[.72,.23,.17],[-.95,side*.96,1.18],bevel=.012)
        add('tool-handle-'+suffix,'cylinder','wood',{'radius':.018,'depth':1.04},[.40,side*.96,1.14],[0,90,0])
        box('tool-head-'+suffix,'steel',[.22,.14,.025],[.94,side*.96,1.14],bevel=.02)
        for x in (-1.55,-.55,.5,1.5):bolts.append(([x,side*1.08,1.108],[.022,.023,.013],0))
    cubes('wheel-and-fender-fasteners','steel',bolts)
    # Deck louvres and cross braces, external exhaust guard, lights and tow eyes.
    for i in range(17):grilles.append(([-1.25+i*.045,-.25,1.437],[.018,.60,.018],0))
    cubes('engine-vent-slats','dark',grilles)
    add('rear-exhaust','cylinder','rust',{'radius':.105,'depth':.90},[-2.03,0,1.05],[90,0,0])
    guard=[]
    for i in range(20):guard.append(([-2.15,-.46+i*.048,1.06],[.02,.013,.23],0))
    cubes('exhaust-guard-slats','edge',guard)
    for side in (-1,1):
        add('lamp-'+str(side).replace('-','n'),'cylinder','edge',{'radius':.07,'depth':.08},[1.96,side*.91,1.16],[0,90,0])
        add('lamp-glass-'+str(side).replace('-','n'),'cylinder','glass',{'radius':.054,'depth':.012},[2.01,side*.91,1.16],[0,90,0])
    panelbolts=[];panelhinges=[]
    for x in [-1.72+i*.22 for i in range(16)]:
        for side in (-1,1):panelbolts.append(([x,side*.718,1.22],[.018,.014,.018],0))
    for i in range(8):
        t=i*math.tau/8+math.pi/8;panelbolts.append(([cx+.66*math.cos(t),cy+.55*math.sin(t),1.79],[.022,.022,.018],0))
    for x in (-1.60,-.80,.0):
        for y in (-.55,.55):panelhinges.append(([x,y,1.435],[.10,.025,.028],0))
    cubes('armor-panel-fasteners','edge',panelbolts);cubes('engine-deck-hinges','edge',panelhinges)
    for i in range(6):
        t=i*math.tau/6;box('cupola-port-'+str(i),'dark',[.08,.018,.035],[-.23+.211*math.cos(t),cy+.211*math.sin(t),2.01],[0,0,math.degrees(t)-90],.003)
    return validate({'schema':SCHEMA,'units':'m','title':'Panzer II Ausf. F · 五视图外观重建','description':'按先行五视图与博物馆车型识别重建的二号坦克外观。X向前、Y向左、Z向上；五负重轮/四托带轮每侧、分节履带、斜装甲、偏置炮塔、舱盖、格栅和排气罩。非扫描/OEM精确复刻，外观比例需对照检查。','materials':[{'id':'paint','color':'#42494a','metallic':.35,'roughness':.69,'detail':'painted'},{'id':'edge','color':'#535957','metallic':.65,'roughness':.54,'detail':'steel'},{'id':'track','color':'#363330','metallic':.75,'roughness':.77,'detail':'steel'},{'id':'steel','color':'#777871','metallic':.86,'roughness':.50,'detail':'steel'},{'id':'rubber','color':'#171a19','roughness':.85,'detail':'none'},{'id':'dark','color':'#141918','roughness':.95},{'id':'rust','color':'#4a3424','metallic':.45,'roughness':.85,'detail':'painted'},{'id':'wood','color':'#75634c','roughness':.82,'detail':'painted'},{'id':'glass','color':'#bdc6b3','roughness':.32}], 'objects':objects,'render':{'quality':'preview','engine':'CYCLES','view':'front','five_views':True,'exposure':-1.5},'unfulfilled':['五视图为AI视觉参考，不是可制造图纸；细部没有实车测绘。','只建外观，不含可发射武器机构、发动机内部或真实动力学。','履带为静态分节几何，未做履带运动、碰撞与悬挂物理。','没有艺术家级重拓扑、高低模投射或3A引擎认证。']})
