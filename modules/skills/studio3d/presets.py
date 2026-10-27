"""Original visual study assets, no OEM reconstruction or purchased meshes."""
import math
from modules.skills.studio3d.contract import SCHEMA,validate

def materials():return [
 {'id':'paint','color':'#135964','metallic':.65,'roughness':.24,'coat':.85},
 {'id':'alloy','color':'#abb4c0','metallic':.95,'roughness':.22,'detail':'brushed'},
 {'id':'dark','color':'#111820','metallic':.45,'roughness':.3,'detail':'carbon'},
 {'id':'rubber','color':'#15181b','roughness':.7,'detail':'rubber'},
 {'id':'glass','color':'#172f3c','metallic':.1,'roughness':.09,'transmission':.65},
 {'id':'brake','color':'#dc3829','metallic':.45,'roughness':.32},
 {'id':'light','color':'#e5f4ff','metallic':.1,'roughness':.12},
 {'id':'tail','color':'#a91220','metallic':.3,'roughness':.18}]
def object_(name,kind,material,params,position=None,rotation=None,modifiers=None,**kw):
    return {'id':name,'kind':kind,'material':material,'params':params,'position':position or [0,0,0],'rotation':rotation or [0,0,0],'modifiers':modifiers or {},**kw}
def wheel(prefix,position,objects,showcase=False):
    # All lathe profiles use local Z; turn them to axle Y. Continuous curved
    # sidewall/lip/barrel, separate rotor/caliper/spokes/fasteners.
    def add(suffix,kind,mat,params,pos=None,rot=None,mod=None):
        p=[position[i]+(pos or [0,0,0])[i] for i in range(3)]
        objects.append(object_(prefix+'-'+suffix,kind,mat,params,p,rot or [90,0,0],mod))
    add('tyre','lathe','rubber',{'profile':[[.245,-.155],[.292,-.16],[.331,-.135],[.35,-.085],[.354,0],[.35,.085],[.331,.135],[.292,.16],[.245,.155],[.245,-.155]],'segments':96})
    add('rim','lathe','alloy',{'profile':[[.245,-.157],[.259,-.152],[.266,-.138],[.258,-.12],[.254,.12],[.267,.142],[.265,.155],[.248,.159],[.242,.14],[.242,-.14],[.245,-.157]],'segments':96})
    add('rotor','lathe','alloy',{'profile':[[.07,-.07],[.211,-.07],[.211,-.05],[.07,-.05],[.07,-.07]],'segments':64})
    add('hub','cylinder','dark',{'radius':.065,'depth':.22})
    side=-1 if position[1]<0 else 1
    for i in range(10):
        a=i*math.tau/10;x=.15*math.cos(a);z=.15*math.sin(a)
        add('spoke-'+str(i),'box','alloy',{'size':[.213,.034,.025]},[x,side*.124,z],[0,-math.degrees(a),0],{'bevel':.009})
    for i in range(5):
        a=i*math.tau/5;add('nut-'+str(i),'cylinder','alloy',{'radius':.012,'depth':.025},[.044*math.cos(a),side*.14,.044*math.sin(a)])
    add('caliper','box','brake',{'size':[.075,.075,.18]},[.17,0,.03],[0,0,0],{'bevel':.022})
    if showcase:
        # Visible brake drillings as dark insets on both rotor sides.
        for i in range(24):
            a=i*math.tau/24;add('rotor-hole-'+str(i),'cylinder','dark',{'radius':.005,'depth':.022},[.184*math.cos(a),.06,.184*math.sin(a)])

def wheel_study():
    objects=[];wheel('wheel',[0,0,.36],objects,True)
    return validate({'schema':SCHEMA,'units':'m','title':'赛车锻造轮组 · 材质与细节研究','description':'独立制作的可编辑轮胎、轮圈、十辐条、紧固件、制动盘与卡钳。不是特定品牌或制造用 CAD。','materials':materials(),'objects':objects,'render':{'quality':'preview'},'unfulfilled':['制动孔为视觉嵌片，并非贯穿孔。','没有轮胎变形、制动力与疲劳验证。']})

def gt_study():
    objects=[]
    # Closed cutters hide in render/export; retained in BLEND for editing.
    for i,x in enumerate([-1.36,1.36]):objects.append(object_('arch-'+str(i),'cylinder','dark',{'radius':.385,'depth':3},[x,0,.36],[90,0,0],visible=False))
    sections=[[-2.22,.86,.66],[-2.12,.95,.72],[-1.8,1.02,.82],[-1.36,1.04,.86],[-.8,.99,.77],[0,.95,.73],[.65,.96,.75],[1.36,1.02,.84],[1.85,.95,.7],[2.15,.85,.57],[2.22,.79,.53]]
    rings=[]
    for x,w,top in sections:
        # Rounded rectangle with broad bonnet and shaped shoulder, not boxes.
        yz=[[-.84,.28],[-.98,.34],[-1,.48],[-.98,.73],[-.9,.94],[-.65,1],[-.3,1.015],[0,1.02],[.3,1.015],[.65,1],[.9,.94],[.98,.73],[1,.48],[.98,.34],[.84,.28]]
        rings.append([[x,y*w,z*top] for y,z in yz])
    objects.append(object_('body-surface','loft','paint',{'rings':rings,'closed':True,'caps':True},modifiers={'subdivision':2,'difference':['arch-0','arch-1']}))
    canopy=[]
    for x,w,h in [[-.95,.55,.79],[-.72,.66,1.12],[-.42,.66,1.23],[.05,.61,1.25],[.4,.54,1.15],[.82,.61,.77]]:
        canopy.append([[x,-w,.75],[x,-w*.99,h-.16],[x,-w*.72,h-.015],[x,0,h],[x,w*.72,h-.015],[x,w*.99,h-.16],[x,w,.75]])
    objects.append(object_('glass-canopy','loft','glass',{'rings':canopy,'closed':True,'caps':True},modifiers={'subdivision':2}))
    # Painted roof panel sits over the tinted glazed canopy.
    roof=[]
    for x,w,h in [[-.67,.46,1.195],[-.4,.49,1.25],[0,.47,1.27],[.25,.4,1.22]]:
        roof.append([[x,-w,h-.075],[x,-w*.5,h-.046],[x,0,h-.04],[x,w*.5,h-.046],[x,w,h-.075]])
    objects.append(object_('roof-panel','loft','paint',{'rings':roof,'closed':False,'caps':False},modifiers={'subdivision':2,'thickness':.008}))
    for sign in (-1,1):
        objects.append(object_('sill-'+str(sign).replace('-','n'),'curve','dark',{'points':[[-2,sign*.9,.25],[-.8,sign*1.02,.24],[.65,sign*.98,.22],[2,sign*.85,.22]],'radius':.038}))
        objects.append(object_('door-line-'+str(sign).replace('-','n'),'curve','dark',{'points':[[-.82,sign*.98,.7],[-.72,sign*1,.37],[.62,sign*.96,.36],[.75,sign*.94,.7]],'radius':.0025}))
        objects.append(object_('mirror-'+str(sign).replace('-','n'),'sphere','dark',{'radius':.085},[.4,sign*.86,.97],scale=[1.3,.65,.55]))
        objects.append(object_('mirror-arm-'+str(sign).replace('-','n'),'curve','dark',{'points':[[.37,sign*.59,.86],[.38,sign*.72,.92],[.4,sign*.85,.97]],'radius':.016}))
        for i,x in enumerate([-1.36,1.36]):wheel(('left' if sign<0 else 'right')+'-'+str(i),[x,sign*.96,.36],objects)
        # Narrow LED clusters and rear lamps; no logos or donor meshes.
        objects.append(object_('lamp-'+str(sign).replace('-','n'),'curve','light',{'points':[[2.12,sign*.48,.54],[2.1,sign*.66,.59],[1.97,sign*.8,.62]],'radius':.015}))
        objects.append(object_('tail-'+str(sign).replace('-','n'),'curve','tail',{'points':[[-2.17,sign*.43,.63],[-2.12,sign*.68,.67],[-2.01,sign*.84,.69]],'radius':.012}))
        objects.append(object_('wing-stay-'+str(sign).replace('-','n'),'box','dark',{'size':[.09,.04,.56]},[-1.93,sign*.53,.92],[0,16,0],{'bevel':.012}))
    objects.append(object_('front-intake','box','dark',{'size':[.03,1.18,.17]},[2.19,0,.37],modifiers={'bevel':.04}))
    objects.append(object_('splitter','box','dark',{'size':[.52,1.94,.035]},[2.02,0,.21],modifiers={'bevel':.012}))
    wing=[]
    for y in [-1.03,-.95,0,.95,1.03]:wing.append([[-2.17,y,1.17],[-1.95,y,1.23],[-1.72,y,1.2],[-1.85,y,1.18],[-2.17,y,1.17]])
    objects.append(object_('rear-airfoil','loft','dark',{'rings':wing,'caps':True,'closed':True},modifiers={'subdivision':1}))
    for i in range(7):objects.append(object_('diffuser-'+str(i),'box','dark',{'size':[.5,.012,.13]},[-2, -.72+i*.24,.22],[0,-12,0],{'bevel':.003}))
    return validate({'schema':SCHEMA,'units':'m','title':'GT 曲面赛车 · 原创外观研究','description':'带连续车身曲面、布尔轮拱、独立玻璃座舱、锻造轮组、制动、前分流器、后扩散器与尾翼。视觉概念模型，不是具体车型复刻或完整内部总成。','materials':materials(),'objects':objects,'render':{'quality':'preview'},'unfulfilled':['没有 OEM 图纸、真实底盘传动与碰撞动力学。','未达到量产车或 3A 游戏资产验收；尚缺人工拓扑、贴图烘焙、LOD 和引擎性能验收。']})

PRESETS={'gt-study':gt_study,'wheel-study':wheel_study}
from modules.skills.studio3d.tracked_vehicle import panzer2
PRESETS['panzer2-study']=panzer2
from modules.skills.studio3d.production import master_study,projection_coupon
PRESETS['panzer2-master']=master_study
PRESETS['projection-coupon']=projection_coupon
