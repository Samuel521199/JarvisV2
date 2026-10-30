"""Authored stylized-character data recipe; not autonomous reconstruction."""
import math
from modules.skills.studio3d.character_contract import validate_parameters
from modules.skills.studio3d.character_surface import body
from modules.skills.studio3d.contract import validate

VERSION='1.1.0'


def scene(params):
    p=validate_parameters(params);h=p['height']/1.68;objs=[]
    vertices,faces=body(p)
    objs.append({'id':'body-continuous','kind':'mesh','material':'skin','params':{'vertices':vertices,'faces':faces},'modifiers':{'subdivision':1}})
    def ell(name, center, scale, material='skin'):
        rings=[]
        for j in range(11):
            a=-math.pi/2+(j+.03)*math.pi/10.06
            rings.append([[(center[0]+scale[0]*math.cos(a)*math.cos(i*math.tau/20))*h,
                           (center[1]+scale[1]*math.cos(a)*math.sin(i*math.tau/20))*h,
                           (center[2]+scale[2]*math.sin(a))*h] for i in range(20)])
        objs.append({'id':name,'kind':'loft','material':material,'params':{'rings':rings,'closed':True,'caps':True},'modifiers':{'subdivision':1}})
    def strand(name,points,radii,material):
        objs.append({'id':name,'kind':'sweep','material':material,'params':{'points':[[c*h for c in q] for q in points],
                    'radii':[r*h for r in radii],'segments':10,'steps':4,'oval':.7}})
    # Hair elements remain individually editable; variation is authored, not
    # evidence that the reference's unseen topology has been recovered.
    ell('hair-cap',(-.025,0,1.55),(.080*p['hair_volume'],.081*p['hair_volume'],.115),'hair')
    ell('hair-back',(-.055,0,1.46),(.048,.075,.13*p['hair_length']),'hair')
    for sign,label in [(-1,'r'),(1,'l')]:
        ell('eye-white-'+label,(.071,sign*.034,1.507),(.010,.021*p['eye_scale'],.012*p['eye_scale']),'eye')
        ell('iris-'+label,(.080,sign*.034,1.507),(.004,.009*p['eye_scale'],.010*p['eye_scale']),'iris')
        ell('pupil-'+label,(.083,sign*.034,1.507),(.0025,.004,.006),'pupil')
        strand('brow-'+label,[(.077,sign*.018,1.526),(.080,sign*.034,1.530),(.074,sign*.052,1.526)],[.002,.0025,.001],'brow')
        for k in range(5):
            y=sign*(.055+k*.006);x=-.02+(k%3)*.015
            strand('hair-lock-'+label+str(k),[(x,y,1.555),(-.02,y*1.13,1.46),(-.015+k*.005,sign*(.075+k*.006),1.385+(k%2)*.015)],
                   [.019,.015,.002],'hair')
        for k in range(4):
            y=sign*(.010+k*.018)
            strand('fringe-'+label+str(k),[(.040,y,1.595),(.070,y,1.55),(.078,sign*(.016+k*.016),1.525+(k%2)*.009)],
                   [.014,.012,.0015],'hair')
        # Distinct fingers are intentionally simple, unrigged separate parts.
        for k in range(4):
            z=.851-k*.008;y=sign*(.365+k*.004)
            strand('finger-'+label+str(k),[(.015,y,z),(.018,sign*(.393+k*.005),z-.030),(.020,sign*(.414+k*.004),z-.052)],
                   [.0065,.0055,.0035],'skin')
        strand('thumb-'+label,[(.022,sign*.358,.856),(.03,sign*.362,.835),(.035,sign*.374,.825)],[.007,.006,.004],'skin')
    ell('nose',(.077,0,1.48),(.009,.006,.01))
    strand('mouth',[(.076,-.012,1.458),(.078,0,1.456),(.076,.012,1.458)],[.0012,.0015,.0012],'brow')
    mats=[{'id':'skin','color':p['skin_color'],'roughness':.7}, {'id':'hair','color':p['hair_color'],'roughness':.48},
          {'id':'eye','color':'#F1EBE8','roughness':.4}, {'id':'iris','color':p['iris_color'],'roughness':.35},
          {'id':'pupil','color':'#342B2B','roughness':.5}, {'id':'brow','color':'#756979','roughness':.7}]
    return validate({'schema':'jarvis.studio3d.v1','units':'m','title':'银发人物 · 连续基础草模',
        'materials':mats,'objects':objs,'unfulfilled':['Authored implicit static surface: anatomical accuracy, face/hair detail, production topology, rig and skin weights are not validated.'],
        'render':{'quality':'preview','engine':'CYCLES','view':'front','five_views':True,'world_color':'#929AA2','floor_color':'#929AA2'}})
