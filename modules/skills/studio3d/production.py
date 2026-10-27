"""Reusable hard-surface production briefs and original visual master studies."""
import math
from modules.skills.studio3d.contract import validate
from modules.skills.studio3d.tracked_vehicle import panzer2

PROFILES={
 'organic':{'name':'果实与有机道具','low_triangles':1000,'reference_checks':['图片真实送入视觉模型','果实比例、凹窝和果柄','果皮色斑与粗糙度'],'preserve':['外轮廓','顶部和底部凹陷','果柄剪影'],'bake':['果皮微孔','细条纹','浅表面凹凸']},
 'vehicle':{'name':'车辆与履带车辆','low_triangles':30000,'reference_checks':['车型/年代一致','轮廓、轮距、轮数与装甲角度','工具/车灯/格栅/舱盖位置','涂装与裸金属分区'],'preserve':['外轮廓','轮胎/履带接地轮廓','开口和厚度','炮塔、车轮、车门的原点'],'bake':['细螺栓','焊缝','浅槽','铸造和漆面微细节']},
 'machine':{'name':'机械与工业设备','low_triangles':20000,'reference_checks':['部件配对和开口','壳体/轴/法兰比例','金属/橡胶/涂层分区'],'preserve':['接口轮廓','主要管线','活动件原点'],'bake':['浅槽','紧固件顶面','磨痕','铭牌底板']},
 'prop':{'name':'硬表面道具','low_triangles':10000,'reference_checks':['比例与轮廓','材质和使用痕迹'],'preserve':['可见剪影','主要凹陷','握把轮廓'],'bake':['小凹凸','表面颗粒','浅浮雕']},
}

VEHICLE_BRIEF='''现有坦克是低模草稿，不是高模。制作顺序：同一车型实车照片与来源登记 → 按照片修正高模母版与分件材质 → 检查高模轮廓/细节 → 根据目标镜头重建或分件减面得到游戏低模 → 清理退化面、孔洞和法线 → UV/三角化/高低模匹配 → 分件防串射烘焙 → PBR与不同光照对照 → 各级LOD → 游戏引擎验收。
高模约50万至200万三角面是容量参考，不是质量门槛，不准通过无效细分凑数；当前Worker实际高模预算为150万。低模目标2万至4万三角面，按部件和屏幕轮廓误差分配。优先简化履带不可见内侧、销钉/花纹、轮子、炮管、工具柄和小车灯的周向段数；保留明显剪影、开孔、厚度、承重外形与活动件原点。圆柱/圆锥应按曲率与镜头距离重建，不只做全局Decimate。法线和高度贴图不能代替轮廓、真正开孔和近景遮挡。
油漆、橡胶、玻璃、木材、锈和裸钢分开；BaseColor无固定光照，Normal记录高模细节，Roughness体现材质与使用痕迹，Metallic区分金属/非金属，AO单独。高度/视差只在目标渲染器支持时作为可选补充。严格区分真实照片、生成参考和推测区域；照片未覆盖不标为已验证。交付高模/低模源、PBR贴图、LOD、来源、三角面/纹理/材质/绘制预算和真实检查报告，不自动授予AAA评分。'''

BRIEF='通用流程：登记同一对象参考及推测区域 → 分析轮廓、关键附件、材质色区和光照 → 高模母版 → 实际渲染与参考图对照 → 按具体差异局部修改并复核 → 通过当前视角的美术检查后制作低模 → UV/高低模投射 → PBR和各级LOD视觉验收。面数与格式检查不代表相似度或AAA。单轮对照修正最多一次改模和两次视觉调用，最终仍有差异必须如实记录；不得自动无界重试。颜色不包含固定高光，粗糙度、法线和灯光分别控制。未见背面与单图无法分离的材质/灯光标为推测；不冒充扫描。各类别预算和保留/烘焙项以PROFILES为准。'
CATEGORY_GUIDANCE={'vehicle':VEHICLE_BRIEF,'organic':'先检查果实不规则轮廓、凹窝和果柄剪影，再处理大色区、条纹、皮孔和微凹凸；果柄使用渐细曲线及独立断面材质；参考和渲染同时对照，换光照检查材质。低于千面时先保住轮廓和果柄，微细节烘焙；额外LOD必须单独视觉验收。'}



def projection_coupon():
    """Known raised detail absent from low mesh: native projection control."""
    return validate({'schema':'jarvis.studio3d.v1','units':'m','title':'硬表面投射校准板','materials':[{'id':'paint','color':'#28525a','roughness':.6,'metallic':0},{'id':'steel','color':'#898d90','metallic':1,'roughness':.3}],
      'objects':[{'id':'plate','kind':'box','material':'paint','params':{'size':[1,.7,.08]},'modifiers':{'bevel':.003,'bevel_segments':8},'position':[0,0,.10],'shading':'flat'},
      {'id':'rivet','bake_target':'plate','kind':'lathe','material':'steel','params':{'profile':[[.035,-.006],[.05,-.003],[.055,.003],[.05,.006],[.001,.006]],'segments':64},'position':[-.2,0,.145],'shading':'smooth'},
      {'id':'seam','bake_target':'plate','kind':'curve','material':'steel','params':{'points':[[.05,-.20,.142],[.08,0,.142],[.05,.20,.142]],'radius':.008}}],
      'render':{'engine':'CYCLES','quality':'preview','view':'front','exposure':-1},'unfulfilled':['投射校准用平板；非成品资产或AAA认证。']})


def master_study():
    """Photo-informed revision. Unmeasured geometry remains explicitly unverified."""
    scene=panzer2();scene['title']='二号坦克 · 高模母版候选 r2'
    scene['description']='参考Bovington同一Ausf.F前左/后右实车照片修正外形；新增前装甲双观察窗、车首舱盖、八处指挥塔开口、后储物箱和翼子板防滑纹。尚非逐部件照片验收或扫描资产。先交付高模候选，再生成游戏低模。'
    remove={'driver-hood','visor-dark-slit','driver-visor','exhaust-guard-slats'}|{'cupola-port-'+str(i) for i in range(6)}
    scene['objects']=[o for o in scene['objects'] if o['id'] not in remove]
    lookup={o['id']:o for o in scene['objects']}
    def box(name,size,pos,mat='paint',rotation=None,bevel=.004):
        o={'id':name,'kind':'box','material':mat,'position':pos,'params':{'size':size},'shading':'flat','modifiers':{'bevel':bevel,'bevel_segments':6}}
        if rotation:o['rotation']=rotation
        scene['objects'].append(o)
    # Flat full-width upper front, replacing the erroneous narrow hood.
    upper=lookup['upper-casemate']
    upper['params']['rings']=[[[x,-.76,1.04],[x,.76,1.04],[x,.76,z],[x,-.76,z]] for x,z in [(-1.89,1.36),(-.65,1.36),(-.49,1.49),(1.47,1.49)]]
    for side in (-1,1):box('front-visor-'+str(side).replace('-','n'),[.065,.43,.15],[1.51,side*.35,1.34],rotation=[0,-8,0],bevel=.007)
    box('bow-access-hatch',[.49,.70,.018],[1.76,0,1.10],rotation=[0,18,0],bevel=.018)
    box('rear-turret-bin',[.23,.78,.27],[-.65,.16,1.73],rotation=[0,-12,0],bevel=.012)
    for i in range(8):
        t=i*math.tau/8;box('cupola-window-'+str(i),[.088,.018,.034],[-.23+.212*math.cos(t),.16+.212*math.sin(t),2.01],'dark',[0,0,math.degrees(t)-90],.002)
    # Crosshatch strips are real high geometry and can transfer into normals.
    vertices=[];faces=[]
    for side in (-1,1):
        for x in [1.93+i*.035 for i in range(8)]:
            for y in [side*.96-.12+j*.04 for j in range(7)]:
                for angle in (-.65,.65):
                    start=len(vertices);c,s=math.cos(angle),math.sin(angle)
                    for a,b,z in [(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]:
                        dx,dy=a*.023,b*.0018;vertices.append([x+c*dx-s*dy,y+s*dx+c*dy,1.104+z*.0025])
                    faces.extend([[start+k for k in f] for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]])
    half=len(vertices)//2
    for i,suffix in enumerate(('right','left')):
        start=i*half
        scene['objects'].append({'id':'fender-antislip-'+suffix,'bake_target':'fender-'+suffix,'kind':'mesh','material':'paint','params':{'vertices':vertices[start:start+half],'faces':[[k-start for k in f] for f in faces if start<=f[0]<start+half]},'shading':'flat','modifiers':{'bevel':.0007,'bevel_segments':4}})
    for o in scene['objects']:
        p=o['params'];kind=o['kind'];mod=o.setdefault('modifiers',{})
        if kind=='lathe':p['segments']=128
        if kind=='cylinder':p['segments']=128
        if kind in ('mesh','box','loft','cylinder') and o['material']!='rubber':
            mod.setdefault('bevel',.002 if o['id'].startswith('track-') else .003)
            mod.setdefault('bevel_segments',8)
        if kind=='lathe':o['shading']='smooth'
        if o['id'].startswith(('track-grousers-','track-pins-')):o['bake_target']='track-shoes-'+('left' if o['id'].endswith('left') else 'right')
        if o['id'].startswith('drive-spokes-'):
            side=1 if o['id'].endswith('left') else -1
            o.update(kind='cylinder',params={'radius':.30,'depth':.10,'segments':128},position=[1.97,side*.965,.56],rotation=[90,0,0],shading='flat')
    for mat in scene['materials']:
        if mat['id'] in ('paint','edge'):mat.update(metallic=0,roughness=.65,detail='painted')
        elif mat['id'] in ('rust','wood','rubber','dark','glass'):mat['metallic']=0;mat['detail']='none'
        elif mat['id']=='steel':mat.update(metallic=1,roughness=.43)
        elif mat['id']=='track':mat.update(metallic=.9,roughness=.72)
    scene['render'].update(five_views=True,quality='preview',exposure=-2.2)
    scene['unfulfilled']=['高模候选尚未严格逐部件匹配照片；顶部/底部/隐藏结构缺少充分照片。','照片来自Morio，Wikimedia Commons CC BY-SA 4.0，仅视觉参考，未采样为贴图。','没有靠细分凑50万面；以实际有效结构和渲染检查为准。','模型不含可发射武器机构或制造数据；无真实动力学。','未完成目标游戏性能、真实重拓扑、精确UV和AAA美术验收。']
    return validate(scene)
