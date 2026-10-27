"""Bounded modelling DATA. No paths, Python, shader graphs or external URLs."""
import copy, math, re
from sdk.protocol import CoreError

SCHEMA='jarvis.studio3d.v1'
CONTRACT={'schema':SCHEMA,'units':'m','objects_max':128,'vertices_max':40000,'evaluated_triangles_max':1500000,
 'object':{'required':['id','kind','material'],'optional':['position','rotation','scale','params','modifiers','visible','shading','bake_target','cap_material'],
 'kinds':{'box':'size[3]','sphere':'radius','cylinder':'radius,depth','torus':'radius,tube',
 'lathe':'profile:[[radius,z],...] radius .0001..10m,z -10..10m; segments:12..128 (local Z axis); caps:boolean; lobes:0..8; lobe_depth:0..0.08 radius fraction; asymmetry:0..0.06',
 'loft':'rings:[[[x,y,z],...],...] equal width; closed:boolean; caps:boolean',
 'mesh':'vertices:[[x,y,z],...],faces:[[index,index,index,...],...]',
 'curve':'points:[[x,y,z],...],radius,closed:boolean (smooth Bezier tube)',
 'sweep':'points:[[x,y,z],...] and radii:[metres,...] same length 2..32; curved tapered solid; segments 8..64, steps 2..16, oval .5..2, end_irregularity 0..0.2; optional object cap_material for cut ends'},
 'modifiers':'bevel:0..0.1 metres; subdivision:0..2; thickness:0..0.05 metres; difference:[previous closed mesh IDs] max8'},
 'material':{'required':['id','color'],'color':'#RRGGBB','optional':{'metallic':'0..1','roughness':'0.03..1','coat':'0..1','coat_roughness':'0.03..1','transmission':'0..1','detail':'none/rubber/brushed/carbon/painted/weathered_paint/steel/fruit_skin/bark','secondary_color':'#RRGGBB; fruit stripe color','streak_strength':'0..1; fruit stripe coverage','speckle_density':'20..180; fruit lenticel scale','streak_scale':'XYZ .1..100','streak_distortion':'0..1','mottle_contrast':'0..1','speckle_color':'#RRGGBB','speckle_size':'.005..0.15','speckle_strength':'0..1','micro_scale':'20..1000','bump_distance':'0..0.0005 metres','roughness_variation':'0..0.3','basin_radius':'0..0.45','basin_color':'#RRGGBB','regions':'up to 8 ellipsoid masks: center XYZ 0..1, radius XYZ .01..2, color #RRGGBB, opacity 0..1, roughness .03..1; generated-coordinate reference-guided pigment zones, not photo projection'}},
 'required':['schema','units','title','objects','materials','unfulfilled'],
 'optional':['description','render','asset','asset_pipeline','reference','master','surface_texture'], 'render':{'engine':['CYCLES','BLENDER_EEVEE_NEXT'],'quality':['preview','final'],'view':['front','rear','side'],'five_views':'boolean; five orthographic renders, X forward/Y left/Z up','exposure':'-3..1 stops','camera_direction':'XYZ -4..4 from object center','lens':'20..120 mm','floor_color':'#RRGGBB','world_color':'#RRGGBB','format':['landscape','square'],'world_strength':'0..2','lights':'1..3 area lights: position XYZ -4..4 in object spans, power 0..500 W per span squared, size .03..4 spans, color #RRGGBB'},
 'production':'Explicit asset_pipeline method=project; category vehicle/machine/prop/organic; triangle_budget 1000..100000; ray_distance .001..0.10m; detail bake_target names preceding visible base part. cylinder segments 8..128; bevel_segments 1..8.',
 'limits':['Visual assets; not manufacturing CAD, contact dynamics, fluid or combustion simulation.','Automatic UV; optional static baking and LOD are reviewed separately. Production retopology and AAA quality are not certified.','Base export keeps procedural microdetail in BLEND/render. Explicit asset preparation bakes a static PBR atlas and merges hierarchy.']}

def bad(message='Invalid bounded 3D scene'):raise CoreError('studio3d_invalid',message)
def number(v,lo,hi):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:bad('Number outside contract')
    return v
def vector(v,lo=-20,hi=20):
    if not isinstance(v,list) or len(v)!=3:bad('Expected XYZ')
    return [number(x,lo,hi) for x in v]
def ident(v):
    if not isinstance(v,str) or not re.fullmatch('[a-z][a-z0-9-]{0,39}',v):bad('Invalid identifier')
    return v
def text(v,n):
    if not isinstance(v,str) or not 1<=len(v)<=n or any(ord(c)<32 and c not in '\n\t' for c in v):bad('Invalid label')
    return v

def hexcolor(v):
    if not isinstance(v,str) or not re.fullmatch('#[0-9a-fA-F]{6}',v):bad('Invalid color')
    return v
def fields(v,required,optional=()):
    if not isinstance(v,dict) or not set(required)<=v.keys() or set(v)-set(required)-set(optional):bad('Unexpected fields')
def validate(value):
    v=copy.deepcopy(value);fields(v,CONTRACT['required'],CONTRACT['optional'])
    if v['schema']!=SCHEMA or v['units']!='m':bad('Use metres and the registered schema')
    if 'asset' in v and (not isinstance(v['asset'],str) or not re.fullmatch('[a-f0-9]{32}',v['asset'])):bad('Invalid approved asset ID')
    if 'reference' in v and (not isinstance(v['reference'],str) or not re.fullmatch('[a-f0-9]{32}',v['reference'])):bad('Invalid approved reference ID')
    if 'master' in v and (not isinstance(v['master'],str) or not re.fullmatch('[a-f0-9]{32}',v['master']) or not isinstance(v.get('asset_pipeline'),dict) or v['asset_pipeline'].get('method')!='project'):bad('Frozen master requires explicit projection')
    if 'asset_pipeline' in v:
        fields(v['asset_pipeline'],['texture_size'],['method','category','triangle_budget','ray_distance','generate_lods'])
        if type(v['asset_pipeline']['texture_size']) is not int or v['asset_pipeline']['texture_size'] not in (512,1024,2048):bad('Use a bounded texture size')
        pipeline=v['asset_pipeline']
        if type(pipeline.get('generate_lods',True)) is not bool:bad('generate_lods must be boolean')
        if pipeline.get('method','surface') not in ('surface','project'):bad('Unknown baking method')
        if pipeline.get('category','prop') not in ('vehicle','machine','prop','organic'):bad('Unsupported production category')
        if type(pipeline.get('triangle_budget',30000)) is not int or not 1000<=pipeline.get('triangle_budget',30000)<=100000:bad('Triangle budget outside production bounds')
        number(pipeline.get('ray_distance',.03),.001,.10)
        if pipeline.get('method','surface')=='surface' and set(pipeline)-{'texture_size','method','generate_lods'}:bad('Projection options require project method')
    text(v['title'],80)
    if 'description' in v:text(v['description'],800)
    if not isinstance(v['unfulfilled'],list) or len(v['unfulfilled'])>16:bad()
    for t in v['unfulfilled']:text(t,250)
    mats=v['materials']
    if not isinstance(mats,list) or not 1<=len(mats)<=24:bad()
    ids=set()
    for m in mats:
        fields(m,['id','color'],CONTRACT['material']['optional']);ident(m['id'])
        if m['id'] in ids or not isinstance(m['color'],str) or not re.fullmatch('#[0-9a-fA-F]{6}',m['color']):bad()
        ids.add(m['id'])
        for k,default in [('metallic',0),('roughness',.35),('coat',0),('transmission',0)]:m[k]=number(m.get(k,default),.03 if k=='roughness' else 0,1)
        if m.get('detail','none') not in ('none','rubber','brushed','carbon','painted','weathered_paint','steel','fruit_skin','bark'):bad()
        if 'secondary_color' in m and (not isinstance(m['secondary_color'],str) or not re.fullmatch('#[0-9a-fA-F]{6}',m['secondary_color'])):bad('Invalid secondary color')
        for key,lo,hi in [('streak_strength',0,1),('speckle_density',20,180)]:
            if key in m:number(m[key],lo,hi)
        for key,lo,hi in [('coat_roughness',.03,1),('streak_distortion',0,1),('mottle_contrast',0,1),('speckle_size',.005,.15),('speckle_strength',0,1),('micro_scale',20,1000),('bump_distance',0,.0005),('roughness_variation',0,.3),('basin_radius',0,.45)]:
            if key in m:number(m[key],lo,hi)
        for key in ('speckle_color','basin_color'):
            if key in m:hexcolor(m[key])
        if 'streak_scale' in m:vector(m['streak_scale'],.1,100)
        if 'regions' in m:
            if not isinstance(m['regions'],list) or len(m['regions'])>8:bad('Region budget exceeded')
            for region in m['regions']:
                fields(region,['center','radius','color','opacity','roughness']);vector(region['center'],0,1);vector(region['radius'],.01,2);hexcolor(region['color']);number(region['opacity'],0,1);number(region['roughness'],.03,1)
    if 'surface_texture' in v:
        binding=v['surface_texture'];fields(binding,['reference','material','mapping'],['rotation'])
        if not isinstance(binding['reference'],str) or not re.fullmatch('[a-f0-9]{32}',binding['reference']):bad('Invalid surface texture reference')
        if binding['mapping'] not in ('cylindrical','lathe') or not isinstance(binding['material'],str) or binding['material'] not in ids:bad('Texture requires known material and bounded mapping')
        if next(m for m in mats if m['id']==binding['material']).get('detail')!='fruit_skin':bad('Texture binding currently supports fruit skin')
        number(binding.get('rotation',0),-180,180)
    objects=v['objects'];names=set();budget=0
    if not isinstance(objects,list) or not (0 if 'asset' in v else 1)<=len(objects)<=128:bad('Object budget exceeded')
    if v.get('surface_texture',{}).get('mapping')=='lathe' and any(isinstance(o,dict) and o.get('material')==v['surface_texture']['material'] and o.get('kind')!='lathe' for o in objects):bad('Lathe mapping requires lathe geometry')
    for o in objects:
        fields(o,['id','kind','material'],['position','rotation','scale','params','modifiers','visible','shading','bake_target','cap_material']);ident(o['id'])
        # One bounded alias for sweep callers. Conflicts are rejected, not guessed.
        if o['kind']=='sweep' and isinstance(o.get('params'),dict) and 'cap_material' in o['params']:
            if 'cap_material' in o:bad('Duplicate cut-end material')
            o['cap_material']=o['params'].pop('cap_material')
        if 'cap_material' in o and (o['kind']!='sweep' or not isinstance(o['cap_material'],str) or o['cap_material'] not in ids):bad('Cut-end material requires sweep and known material')
        if o.get('shading','smooth') not in ('flat','smooth'):bad('Use flat or smooth shading')
        if o['id'] in names or not isinstance(o['material'],str) or o['material'] not in ids:bad('Duplicate object or unknown material')
        previous=set(names);names.add(o['id']);o['position']=vector(o.get('position',[0,0,0]));o['rotation']=vector(o.get('rotation',[0,0,0]),-360,360);o['scale']=vector(o.get('scale',[1,1,1]),.001,20)
        if 'bake_target' in o:
            if not isinstance(o['bake_target'],str) or o['bake_target'] not in previous:bad('Detail bake target must precede source')
            target=next(x for x in objects if x['id']==o['bake_target'])
            if target.get('bake_target') or not target.get('visible',True) or not o.get('visible',True):bad('Bake targets must be visible base parts, not chains or cutters')
        if type(o.get('visible',True)) is not bool:bad()
        p=o.setdefault('params',{});kind=o['kind'];verts=0
        if kind=='box':fields(p,[],['size']);p['size']=vector(p.get('size',[1,1,1]),.001,20);verts=8
        elif kind in ('sphere','cylinder','torus'):
            keys={'sphere':['radius'],'cylinder':['radius','depth'],'torus':['radius','tube']}[kind];fields(p,[],keys+(['segments'] if kind=='cylinder' else []))
            for k in keys:p[k]=number(p.get(k,.1 if k=='tube' else 1),.001,10)
            if kind=='cylinder' and (type(p.get('segments',128)) is not int or not 8<=p.get('segments',128)<=128):bad('Cylinder segments must be 8..128')
            verts=2145 if kind=='sphere' else 4096 if kind=='torus' else 256
        elif kind=='lathe':
            fields(p,['profile'],['segments','caps','lobes','lobe_depth','asymmetry']);a=p['profile'];s=p.setdefault('segments',64)
            if type(p.get('caps',False)) is not bool or type(p.get('lobes',0)) is not int or not 0<=p.get('lobes',0)<=8:bad('Invalid organic lathe')
            number(p.get('lobe_depth',0),0,.08);number(p.get('asymmetry',0),0,.06)
            if type(s) is not int or not 12<=s<=128 or not isinstance(a,list) or not 2<=len(a)<=64:bad()
            for pair in a:
                if not isinstance(pair,list) or len(pair)!=2:bad()
                number(pair[0],.0001,10);number(pair[1],-10,10)
            verts=len(a)*s
        elif kind=='loft':
            fields(p,['rings'],['closed','caps']);rings=p['rings']
            if not isinstance(rings,list) or not 2<=len(rings)<=64 or not isinstance(rings[0],list) or not 3<=len(rings[0])<=128:bad()
            for ring in rings:
                if not isinstance(ring,list) or len(ring)!=len(rings[0]):bad('Loft ring widths differ')
                for pt in ring:vector(pt)
            for k in ('closed','caps'):
                if type(p.get(k,True)) is not bool:bad()
            verts=len(rings)*len(rings[0])
        elif kind=='mesh':
            fields(p,['vertices','faces']);a=p['vertices'];f=p['faces']
            if not isinstance(a,list) or not 3<=len(a)<=20000 or not isinstance(f,list) or not 1<=len(f)<=20000:bad()
            for pt in a:vector(pt)
            for face in f:
                if not isinstance(face,list) or not 3<=len(face)<=8 or any(type(i) is not int or not 0<=i<len(a) for i in face) or len(set(face))!=len(face):bad('Invalid mesh indices')
            verts=len(a)
        elif kind=='sweep':
            fields(p,['points','radii'],['segments','steps','oval','end_irregularity']);a=p['points'];radii=p['radii']
            if not isinstance(a,list) or not 2<=len(a)<=32 or not isinstance(radii,list) or len(radii)!=len(a):bad('Sweep control points/radii mismatch')
            for pt in a:vector(pt)
            if any(sum((x-y)**2 for x,y in zip(a[i],a[i+1]))<1e-12 for i in range(len(a)-1)):bad('Repeated sweep point')
            for radius in radii:number(radius,.0001,.25)
            for key,default,lo,hi in [('segments',24,8,64),('steps',8,2,16)]:
                p.setdefault(key,default)
                if type(p[key]) is not int or not lo<=p[key]<=hi:bad('Sweep resolution budget')
            number(p.get('oval',1),.5,2);verts=((len(a)-1)*p['steps']+1)*p['segments']
            number(p.get('end_irregularity',0),0,.2)
        elif kind=='curve':
            fields(p,['points'],['radius','closed']);a=p['points']
            if not isinstance(a,list) or not 2<=len(a)<=64:bad()
            for pt in a:vector(pt)
            p['radius']=number(p.get('radius',.01),.001,.25)
            if type(p.get('closed',False)) is not bool:bad()
            verts=len(a)*64
        else:bad('Unknown geometry operation')
        mod=o.setdefault('modifiers',{});fields(mod,[],['bevel','bevel_segments','subdivision','thickness','difference'])
        if type(mod.get('bevel_segments',3)) is not int or not 1<=mod.get('bevel_segments',3)<=8:bad('Bevel segments must be 1..8')
        cuts=mod.get('difference',[])
        if not isinstance(cuts,list) or len(cuts)>8 or any(not isinstance(c,str) or c not in previous for c in cuts):bad('Boolean cutters must precede target')
        for k,limit in [('bevel',.1),('thickness',.05)]:number(mod.get(k,0),0,limit)
        if type(mod.get('subdivision',0)) is not int or not 0<=mod.get('subdivision',0)<=2:bad()
        budget+=verts
    if budget>40000:bad('Input vertex budget exceeded')
    r=v.setdefault('render',{});fields(r,[],CONTRACT['render'])
    if 'camera_direction' in r:
        vector(r['camera_direction'],-4,4)
        if sum(x*x for x in r['camera_direction'])<.01:bad('Camera direction too short')
    if 'lens' in r:number(r['lens'],20,120)
    if 'floor_color' in r:hexcolor(r['floor_color'])
    if 'world_color' in r:hexcolor(r['world_color'])
    if r.get('format','landscape') not in ('landscape','square'):bad('Unknown image format')
    if 'world_strength' in r:number(r['world_strength'],0,2)
    if 'lights' in r:
        if not isinstance(r['lights'],list) or not 1<=len(r['lights'])<=3:bad('Light budget exceeded')
        for light in r['lights']:
            fields(light,['position','power','size','color']);vector(light['position'],-4,4);number(light['power'],0,500);number(light['size'],.03,4);hexcolor(light['color'])
            if sum(x*x for x in light['position'])<.01:bad('Light is inside target center')
    if 'exposure' in r:number(r['exposure'],-3,1)
    if type(r.get('five_views',False)) is not bool:bad('five_views must be boolean')
    for k,default in [('engine','CYCLES'),('quality','preview'),('view','front')]:
        r.setdefault(k,default)
        if r[k] not in CONTRACT['render'][k]:bad()
    return v
