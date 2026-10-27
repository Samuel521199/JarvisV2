"""First-party involute polyline and constrained parallel-axis ratio graph.

Nominal 20-degree spur gears; no generated cutter fillet, undercut or elastic contact.
Geometry reference: KHK Calculation of Gear Dimensions (see project evidence).
"""
import math
from modules.skills.anatomy.engineering_model import fields,fail,assembly_poses

def gear_outline(p):
    z=p['teeth'];m=p['module'];pitch=m*z/2;base=pitch*math.cos(math.radians(20));root=m*(z-2.5)/2;tip=m*(z+2)/2
    inv=lambda a:math.tan(a)-a
    half=lambda r:math.pi/(2*z)+inv(math.radians(20))-inv(math.acos(min(1,base/r)))-p['backlash']/(4*pitch)
    start=max(root,base);rs=[start+(tip-start)*i/6 for i in range(7)];points=[]
    def point(r,a):return [r*math.cos(a),r*math.sin(a)]
    for j in range(z):
        center=j*2*math.pi/z;h=half(start)
        points.append(point(root,center-h))
        points.extend(point(r,center-half(r)) for r in rs)
        points.extend(point(tip,center-half(tip)+2*half(tip)*i/3) for i in (1,2,3))
        points.extend(point(r,center+half(r)) for r in reversed(rs[:-1]))
        points.append(point(root,center+h))
        gap=2*math.pi/z-2*h
        points.extend(point(root,center+h+gap*i/3) for i in (1,2))
    # Avoid coincident vertices when root lies on the involute start.
    return [v for i,v in enumerate(points) if i==0 or math.dist(v,points[i-1])>1e-9]

def transmission_ratios(scene):
    t=scene['operation']['transmission'];ids={p['id']:p for p in scene['parts']};edges={}
    def link(a,b,ratio):edges.setdefault(a,[]).append((b,ratio));edges.setdefault(b,[]).append((a,1/ratio))
    for pair in t['stages']:link(pair['driver'],pair['driven'],-ids[pair['driver']]['params']['teeth']/ids[pair['driven']]['params']['teeth'])
    for shaft in t['shafts']:
        for ident in shaft['parts']:
            if ident!=shaft['gear']:link(shaft['gear'],ident,1)
    ratios={t['output']:1.};pending=[t['output']]
    while pending:
        a=pending.pop()
        for b,weight in edges.get(a,[]):
            value=ratios[a]*weight
            if b in ratios:
                if abs(ratios[b]-value)>1e-8:fail()
            else:ratios[b]=value;pending.append(b)
    if set(ratios)!=set(edges) or any(not .05<=abs(x)<=32 for x in ratios.values()):fail()
    return ratios

def validate_transmission(scene,ids,poses,occupied):
    t=scene['operation']['transmission'];fields(t,'output stages shafts')
    if not isinstance(t['output'],str) or t['output'] not in ids or ids[t['output']]['kind']!='gear':fail()
    if not isinstance(t['stages'],list) or not 1<=len(t['stages'])<=4 or not isinstance(t['shafts'],list) or not 1<=len(t['shafts'])<=5:fail()
    gears=set();bound=set();mated={m['part'] for m in scene['mates']}
    for pair in t['stages']:
        fields(pair,'driver driven')
        if any(not isinstance(pair[k],str) or pair[k] not in ids or ids[pair[k]]['kind']!='gear' for k in ('driver','driven')) or pair['driver']==pair['driven']:fail()
        a,b=[ids[pair[k]] for k in ('driver','driven')];pa,pb=[poses[p['id']]['position'] for p in (a,b)];qa,qb=a['params'],b['params']
        if qa['module']!=qb['module'] or abs(math.hypot(pa[0]-pb[0],pa[2]-pb[2])-qa['module']*(qa['teeth']+qb['teeth'])/2)>1e-5 or abs(pa[1]-pb[1])>=(qa['thickness']+qb['thickness'])/2:fail()
        gears.update((a['id'],b['id']))
    for shaft in t['shafts']:
        fields(shaft,'gear parts');gear=shaft['gear'];parts=shaft['parts']
        if not isinstance(gear,str) or gear not in gears or not isinstance(parts,list) or gear not in parts:fail()
        for ident in parts:
            if not isinstance(ident,str) or ident not in ids or ident in bound or ident in occupied or ident in mated:fail()
            p=poses[ident];g=poses[gear]
            if any(abs(p['position'][i]-g['position'][i])>1e-5 for i in (0,2)) or abs(abs(p['rotation'][1][2])-1)>1e-5:fail()
            bound.add(ident)
    if not gears<=bound or t['output'] not in gears:fail()
    ratios=transmission_ratios(scene)
    rear=next(w for w in scene['operation']['wheels'] if w['axle']=='rear');pos=poses[t['output']]['position']
    if any(abs(pos[i]-rear['center'][i])>1e-5 for i in (0,2)):fail()
    return ratios
