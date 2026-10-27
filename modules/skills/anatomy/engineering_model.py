"""Pure first-party parameter contract and rigid assembly transforms."""
import copy,json,math,re
from pathlib import Path
from sdk.protocol import CoreError
ROOT=Path(__file__).resolve().parents[3]
HOME=Path(__file__).resolve().parent
CONTRACT=json.loads((HOME/'engineering-contract.json').read_text(encoding='utf-8'))

def fail():raise CoreError('anatomy_engineering_invalid','Invalid bounded engineering data, feature, mate or experiment')
def fields(v,names):
    if not isinstance(v,dict) or set(v)!=set(names.split()):fail()
def number(v,lo,hi):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:fail()
    return v
def vec(v,lo,hi):
    if not isinstance(v,list) or len(v)!=3:fail()
    return [number(x,lo,hi) for x in v]
def label(v,n,empty=False):
    if not isinstance(v,str) or not (0 if empty else 1)<=len(v.strip())<=n or any(ord(c)<32 and c not in '\n\t' for c in v):fail()
    return v.strip()
def params(value,rules):
    if not isinstance(value,dict) or set(value)-rules.keys():fail()
    result={}
    for key,rule in rules.items():
        x=value.get(key,rule['default'])
        if 'enum' in rule:
            if x not in rule['enum']:fail()
        else:
            number(x,rule['min'],rule['max'])
            if rule.get('integer') and type(x) is not int:fail()
        result[key]=x
    return result
def length(part):
    p=part['params'];return p.get('length',p.get('thickness',p.get('height',p.get('head_height',0))))
def ports(part):
    p=part['params'];h=length(part)
    result={'axis':[0,0,0],'front':[0,0,h/2],'back':[0,0,-h/2]}
    if part['kind']=='bolt':result.update(front=[0,0,p['head_height']],back=[0,0,-p['length']])
    if part['kind']=='flange':
        for i in range(p['bolts']):
            a=2*math.pi*i/p['bolts'];result['bolt-'+str(i)]=[p['bolt_circle']/2*math.cos(a),p['bolt_circle']/2*math.sin(a),0]
    return result
def validate_engineering(value):
    if not isinstance(value,dict):fail()
    fields({k:v for k,v in value.items() if k not in ('assembly_plan','operation')},'schema units title description parts mates steps experiments unfulfilled')
    if value['schema']!=CONTRACT['schema'] or value['units']!='mm':fail()
    result=copy.deepcopy(value);result['title']=label(value['title'],80);result['description']=label(value['description'],500,True)
    if not isinstance(value['unfulfilled'],list) or len(value['unfulfilled'])>12:fail()
    result['unfulfilled']=[label(x,200) for x in value['unfulfilled']]
    parts=value['parts'];mates=value['mates'];steps=value['steps'];experiments=value['experiments']
    if not isinstance(parts,list) or not 1<=len(parts)<=CONTRACT['max_parts'] or not isinstance(mates,list) or len(mates)>=CONTRACT['max_parts'] or not isinstance(steps,list) or len(steps)!=len(parts) or not isinstance(experiments,list) or len(experiments)>4:fail()
    ids={};result['parts']=[]
    for p in parts:
        fields(p,'id name kind params material position rotation')
        ident=p['id'];kind=p['kind']
        if not isinstance(ident,str) or not re.fullmatch('[a-z][a-z0-9-]{0,23}',ident) or ident in ids or not isinstance(kind,str) or kind not in CONTRACT['kinds'] or not isinstance(p['material'],str) or p['material'] not in CONTRACT['materials']:fail()
        row=copy.deepcopy(p);row['name']=label(p['name'],50);row['params']=params(p['params'],CONTRACT['kinds'][kind]);vec(p['position'],-500,500);vec(p['rotation'],-180,180)
        q=row['params']
        if kind in ('tube','bearing','nut','flange') and q['inner']>=q['outer']-1:fail()
        if kind=='bearing' and q['outer']-q['inner']<8:fail()
        if kind=='nut' and q['inner']>q['outer']*math.cos(math.pi/6)-1:fail()
        if kind=='box' and q['bore']>=min(q['width'],q['depth'])-1:fail()
        if kind=='flange' and (q['bolt_circle']+q['bolt_diameter']>q['outer']-1 or q['bolt_circle']-q['bolt_diameter']<q['inner']+1 or q['bolt_diameter']>=q['bolt_circle']*math.sin(math.pi/q['bolts'])-1):fail()
        if kind=='bolt' and q['head_diameter']<=q['diameter']+1:fail()
        if kind=='gear' and q['bore']>=q['module']*(q['teeth']-2.5)-2:fail()
        if kind=='shell':
            if q['wall']*2>=min(q['front_width'],q['rear_width'],q['height'])-2 or q['opening']>q['length']-12:fail()
            if bool(q['mount_span'])!=bool(q['mount_width']) or q['mount_span']>q['length']-12 or q['mount_width']>min(q['front_width'],q['rear_width'])-12:fail()
        ids[ident]=row;result['parts'].append(row)
    incoming={}
    for m in mates:
        fields(m,'part parent parent_port child_port gap twist joint fit')
        if any(not isinstance(m[k],str) for k in ('part','parent','parent_port','child_port','joint','fit')) or m['part'] not in ids or m['parent'] not in ids or m['part']==m['parent'] or m['part'] in incoming:fail()
        if m['parent_port'] not in ports(ids[m['parent']]) or m['child_port'] not in ports(ids[m['part']]) or m['joint'] not in ('fixed','revolute','prismatic') or m['fit'] not in ('locate','clearance','press'):fail()
        number(m['gap'],-300,300);number(m['twist'],-180,180)
        if ids[m['part']]['position']!=[0,0,0] or ids[m['part']]['rotation']!=[0,0,0]:fail()
        incoming[m['part']]=m
    seen=set()
    for step in steps:
        fields(step,'part instruction direction distance')
        ident=step['part']
        if not isinstance(ident,str) or ident not in ids or ident in seen:fail()
        label(step['instruction'],200);vec(step['direction'],-1,1);number(step['distance'],0,300)
        if abs(math.hypot(*step['direction'])-1)>1e-6:fail()
        if ident in incoming and incoming[ident]['parent'] not in seen:fail()
        seen.add(ident)
    kinds=set();result['experiments']=[]
    for e in experiments:
        fields(e,'kind params')
        k=e['kind']
        if not isinstance(k,str) or k not in CONTRACT['experiments'] or k in kinds:fail()
        kinds.add(k);q=params(e['params'],CONTRACT['experiments'][k]);result['experiments'].append({'kind':k,'params':q})
        if k=='channel' and q['height']**3*q['pressure_drop']*q['density']/(6*q['viscosity']**2*q['length'])>1000:fail()
        if k=='shallow-water' and q['amplitude']>q['depth']*.25:fail()
    poses=assembly_poses(result)
    if any(abs(x)>2000 for p in poses.values() for x in p['position']):fail()
    if 'assembly_plan' in value:validate_plan(result,ids,incoming)
    if 'operation' in value:validate_operation(result,ids,poses)
    return result

def validate_plan(scene,ids,incoming):
    groups=scene['assembly_plan']
    if not isinstance(groups,list) or not 1<=len(groups)<=CONTRACT['max_groups']:fail()
    used=set();names=set();owner={}
    for i,g in enumerate(groups):
        if not isinstance(g,dict):fail()
        fields({k:v for k,v in g.items() if k not in ('batches','type')},'id name parts direction distance')
        if 'type' in g and g['type']!='body':fail()
        if not isinstance(g['id'],str) or not re.fullmatch('[a-z][a-z0-9-]{0,23}',g['id']) or g['id'] in names:fail()
        names.add(g['id']);label(g['name'],50);vec(g['direction'],-1,1);number(g['distance'],0,300)
        if abs(math.hypot(*g['direction'])-1)>1e-6 or not isinstance(g['parts'],list) or not g['parts']:fail()
        for ident in g['parts']:
            if not isinstance(ident,str) or ident not in ids or ident in used:fail()
            used.add(ident);owner[ident]=i
        if 'batches' in g:
            batches=g['batches']
            if not isinstance(batches,list) or not batches or len(batches)>CONTRACT['max_parts'] or any(not isinstance(b,list) or not b for b in batches):fail()
            flat=[x for b in batches for x in b]
            if any(not isinstance(x,str) for x in flat) or len(set(flat))!=len(flat) or set(flat)!=set(g['parts']):fail()
            batch_owner={x:j for j,b in enumerate(batches) for x in b}
            if any(m['parent'] in batch_owner and batch_owner[m['parent']]>batch_owner[x] for x,m in incoming.items() if x in batch_owner):fail()
    if used!=set(ids):fail()
    if any(owner[m['parent']]>owner[ident] for ident,m in incoming.items()):fail()

def validate_operation(scene,ids,poses):
    o=scene['operation']
    if not isinstance(o,dict):fail()
    fields({k:v for k,v in o.items() if k not in ('transmission','verification')},'kind wheels steering_parts rear_rotating wheelbase pivot_track radius max_steer')
    if 'verification' in o and o['verification']!='extended':fail()
    if o['kind']!='vehicle' or 'assembly_plan' not in scene:fail()
    for k,lo,hi in [('wheelbase',50,400),('pivot_track',40,250),('radius',10,80),('max_steer',5,25)]:number(o[k],lo,hi)
    if o['wheelbase']/math.tan(math.radians(o['max_steer']))<=o['pivot_track']/2+o['radius']:fail()
    wheels=o['wheels']
    if not isinstance(wheels,list) or len(wheels)!=4:fail()
    used=set();front=set()
    for w in wheels:
        fields(w,'axle side center pivot parts')
        if not isinstance(w['axle'],str) or not isinstance(w['side'],str):fail()
        if w['axle'] not in ('front','rear') or w['side'] not in ('left','right') or (w['axle'],w['side']) in used:fail()
        used.add((w['axle'],w['side']));vec(w['center'],-500,500);vec(w['pivot'],-500,500)
        if not isinstance(w['parts'],list) or not w['parts'] or any(not isinstance(x,str) or x not in ids or x in front for x in w['parts']) or len(set(w['parts']))!=len(w['parts']):fail()
        front.update(w['parts'])
        # Wheels must be concentric with the declared axle and lie on level ground.
        if any(abs(poses[x]['position'][j]-w['center'][j])>1e-5 for x in w['parts'] for j in (0,2)):fail()
        if abs(w['center'][2]-o['radius'])>1e-5 or abs(w['pivot'][2]-o['radius'])>1e-5:fail()
        if w['axle']=='front' and abs(w['pivot'][1]-(1 if w['side']=='left' else -1)*o['pivot_track']/2)>1e-5:fail()
        if any(abs(poses[x]['rotation'][i][2])>1e-5 for x in w['parts'] for i in (0,2)):fail()
        if not any(abs(ids[x]['params'].get('outer',0)-2*o['radius'])<1e-5 for x in w['parts']):fail()
    f=[w for w in wheels if w['axle']=='front'];r=[w for w in wheels if w['axle']=='rear']
    if any(abs(w['pivot'][0]-f[0]['pivot'][0])>1e-5 for w in f) or any(abs(w['center'][0]-r[0]['center'][0])>1e-5 for w in r) or abs(f[0]['pivot'][0]-r[0]['center'][0]-o['wheelbase'])>1e-5:fail()
    steering=o['steering_parts'];fields(steering,'left right');extra=set()
    for side in ('left','right'):
        a=steering[side]
        if not isinstance(a,list):fail()
        for ident in a:
            if not isinstance(ident,str) or ident not in ids or ident in front or ident in extra:fail()
            extra.add(ident)
    rear=o['rear_rotating']
    if not isinstance(rear,list) or any(not isinstance(x,str) for x in rear) or len(set(rear))!=len(rear):fail()
    for ident in rear:
        if not isinstance(ident,str) or ident not in ids or ident in front or ident in extra:fail()
        if abs(poses[ident]['position'][0]-r[0]['center'][0])>1e-5 or abs(poses[ident]['position'][2]-o['radius'])>1e-5:fail()
    if 'transmission' in o:
        from modules.skills.anatomy.engineering_transmission import validate_transmission
        validate_transmission(scene,ids,poses,front|extra|set(rear))

def vehicle_kinematics(operation,steer):
    """Ideal Ackermann steering with wheel-centre offsets, SI display speed elsewhere."""
    o=operation;delta=math.radians(max(-o['max_steer'],min(o['max_steer'],steer)));L=o['wheelbase']
    radius=L/math.tan(delta) if abs(delta)>1e-10 else None;angles=[];ratios=[]
    for w in o['wheels']:
        angle=math.atan(L/(radius-w['pivot'][1])) if radius is not None and w['axle']=='front' else 0
        c,s=math.cos(angle),math.sin(angle);v=[w['center'][i]-w['pivot'][i] for i in range(3)]
        center=[w['pivot'][0]+c*v[0]-s*v[1],w['pivot'][1]+s*v[0]+c*v[1],w['center'][2]]
        rear_x=next(a['center'][0] for a in o['wheels'] if a['axle']=='rear')
        ratios.append(math.hypot(center[0]-rear_x,center[1]-radius)/abs(radius) if radius is not None else 1)
        angles.append(math.degrees(angle))
    return {'steer_deg':angles,'speed_ratios':ratios,'turn_radius_mm':radius}

def operation_transforms(scene,phases,steer):
    """World-space rigid deltas; same formula is mirrored in the offline viewer."""
    o=scene['operation'];k=vehicle_kinematics(o,steer);out={}
    def around(R,pivot):return {'rotation':R,'position':[pivot[i]-v for i,v in enumerate(mv(R,pivot))]}
    for i,w in enumerate(o['wheels']):
        a=k['steer_deg'][i];R=rotation([0,0,a]);pivot=w['pivot'];t=around(R,pivot)
        if w['axle']=='front':
            for ident in o['steering_parts'][w['side']]:out[ident]=t
        roll=around(rotation([0,math.degrees(phases[i]),0]),w['center']);combined={'rotation':mm(R,roll['rotation']),'position':[x+y for x,y in zip(mv(R,roll['position']),t['position'])]}
        for ident in w['parts']:out[ident]=combined
    for ident in o['rear_rotating']:
        w=next(w for w in o['wheels'] if w['axle']=='rear');a=sum(phases[i] for i,w in enumerate(o['wheels']) if w['axle']=='rear')/2
        out[ident]=around(rotation([0,math.degrees(a),0]),w['center'])
    if 'transmission' in o:
        from modules.skills.anatomy.engineering_transmission import transmission_ratios
        poses=assembly_poses(scene);mean=sum(phases[i] for i,w in enumerate(o['wheels']) if w['axle']=='rear')/2
        for ident,ratio in transmission_ratios(scene).items():out[ident]=around(rotation([0,math.degrees(mean*ratio),0]),poses[ident]['position'])
    return out

def mm(a,b):return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def mv(a,v):return [sum(a[i][j]*v[j] for j in range(3)) for i in range(3)]
def rotation(angles):
    a,b,c=[math.radians(x) for x in angles];ca,sa,cb,sb,cc,sc=math.cos(a),math.sin(a),math.cos(b),math.sin(b),math.cos(c),math.sin(c)
    return mm(mm([[1,0,0],[0,ca,-sa],[0,sa,ca]],[[cb,0,sb],[0,1,0],[-sb,0,cb]]),[[cc,-sc,0],[sc,cc,0],[0,0,1]])
def assembly_poses(scene):
    ids={p['id']:p for p in scene['parts']};incoming={m['part']:m for m in scene['mates']};done={};active=set()
    def visit(ident):
        if ident in done:return done[ident]
        if ident in active:fail()
        active.add(ident);p=ids[ident]
        if ident not in incoming:R=rotation(p['rotation']);t=p['position']
        else:
            m=incoming[ident];parent=visit(m['parent']);R=mm(parent['rotation'],rotation([0,0,m['twist']]))
            a=mv(parent['rotation'],[x+(m['gap'] if i==2 else 0) for i,x in enumerate(ports(ids[m['parent']])[m['parent_port']])]);b=mv(R,ports(p)[m['child_port']]);t=[parent['position'][i]+a[i]-b[i] for i in range(3)]
        result={'rotation':R,'position':t};done[ident]=result;active.remove(ident);return result
    for ident in ids:visit(ident)
    return done

