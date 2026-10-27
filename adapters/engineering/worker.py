"""Trusted optional native CAD worker. JSON -> fixed factories -> checked files.

This process does NOT execute model code and is not an LPAC sandbox.
"""
import argparse, csv, hashlib, json, math, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from modules.skills.anatomy.engineering_model import validate_engineering,assembly_poses,operation_transforms,CONTRACT
from modules.skills.anatomy.engineering_physics import solve
from modules.skills.anatomy.engineering_transmission import gear_outline,transmission_ratios
from OCP.gp import gp_Pnt,gp_Dir,gp_Ax2,gp_Vec,gp_Trsf
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder,BRepPrimAPI_MakeBox,BRepPrimAPI_MakePrism,BRepPrimAPI_MakeSphere
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut,BRepAlgoAPI_Common,BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform,BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace,BRepBuilderAPI_MakeWire,BRepBuilderAPI_MakeEdge
from OCP.GeomAPI import GeomAPI_Interpolate
from OCP.TColgp import TColgp_HArray1OfPnt
from OCP.GC import GC_MakeArcOfCircle
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRep import BRep_Builder,BRep_Tool
from OCP.TopoDS import TopoDS,TopoDS_Compound
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.STEPControl import STEPControl_Writer,STEPControl_Reader,STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from OCP.StlAPI import StlAPI_Writer
from OCP.Interface import Interface_Static

def combustion(p):
    import cantera as ct
    gas=ct.Solution('gri30.yaml' if p['fuel']=='CH4' else 'h2o2.yaml');gas.TP=p['temperature'],p['pressure'];gas.set_equivalence_ratio(p['equivalence'],p['fuel'],'O2:1,N2:3.76')
    enthalpy=gas.enthalpy_mass;elements={e:gas.elemental_mass_fraction(e) for e in gas.element_names};gas.equilibrate('HP')
    return {'kind':'combustion','title':'绝热定压化学平衡','columns':['species','mole_fraction'],'rows':[[s,float(gas[s].X[0])] for s in ['CO2','H2O','CO','O2','H2','N2'] if s in gas.species_names],'summary':{'temperature_K':gas.T,'relative_enthalpy_error':abs(gas.enthalpy_mass-enthalpy)/max(1,abs(enthalpy)),'max_element_mass_error':max(abs(gas.elemental_mass_fraction(e)-v) for e,v in elements.items()),'mechanism':'gri30.yaml' if p['fuel']=='CH4' else 'h2o2.yaml','cantera_version':ct.__version__},'limits':'零维绝热定压化学平衡终态；不包含点火时间、火焰空间形状、湍流、排放认证或三维燃烧 CFD。'}


def cylinder(radius,height,z=0,x=0,y=0):return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,z),gp_Dir(0,0,1)),radius,height).Shape()
def cut(a,b):
    op=BRepAlgoAPI_Cut(a,b)
    if not op.IsDone():raise ValueError('CAD cut failed')
    return op.Shape()
def compound(shapes):
    result=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(result)
    for s in shapes:builder.Add(result,s)
    return result
def ring(outer,inner,h):
    s=cylinder(outer/2,h,-h/2)
    return cut(s,cylinder(inner/2,h+2,-h/2-1)) if inner>0 else s
def shape(part):
    p=part['params'];kind=part['kind']
    if kind=='gear':
        # Curved flanks replace hundreds of separate planar facets per gear.
        z=p['teeth'];pitch=p['module']*z/2;base=pitch*math.cos(math.radians(20));root=p['module']*(z-2.5)/2;tip=p['module']*(z+2)/2;start=max(base,root);wire=BRepBuilderAPI_MakeWire()
        inv=lambda a:math.tan(a)-a
        half=lambda r:math.pi/(2*z)+inv(math.radians(20))-inv(math.acos(min(1,base/r)))-p['backlash']/(4*pitch)
        point=lambda r,a:gp_Pnt(r*math.cos(a),r*math.sin(a),-p['thickness']/2)
        def line(a,b):
            if a.Distance(b)>1e-8:wire.Add(BRepBuilderAPI_MakeEdge(a,b).Edge())
        def curve(points):
            array=TColgp_HArray1OfPnt(1,len(points))
            for i,pt in enumerate(points):array.SetValue(i+1,pt)
            fit=GeomAPI_Interpolate(array,False,1e-9);fit.Perform();wire.Add(BRepBuilderAPI_MakeEdge(fit.Curve()).Edge())
        def arc(a,b,c):wire.Add(BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(a,b,c).Value()).Edge())
        for j in range(z):
            a=j*2*math.pi/z;h=half(start);ht=half(tip);line(point(root,a-h),point(start,a-h))
            curve([point(r,a-half(r)) for r in [start+(tip-start)*i/18 for i in range(19)]])
            arc(point(tip,a-ht),point(tip,a),point(tip,a+ht))
            curve([point(r,a+half(r)) for r in [tip-(tip-start)*i/18 for i in range(19)]])
            line(point(start,a+h),point(root,a+h));next_a=a+2*math.pi/z-h;arc(point(root,a+h),point(root,(a+h+next_a)/2),point(root,next_a))
        s=BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(wire.Wire()).Face(),gp_Vec(0,0,p['thickness'])).Shape()
        return cut(s,cylinder(p['bore']/2,p['thickness']+2,-p['thickness']/2-1))
    if kind=='shell':
        def prism(L,back,front,z,h):
            poly=BRepBuilderAPI_MakePolygon()
            for x,y in [(-L/2,-back/2),(L/2,-front/2),(L/2,front/2),(-L/2,back/2)]:poly.Add(gp_Pnt(x,y,z))
            poly.Close();return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(poly.Wire()).Face(),gp_Vec(0,0,h)).Shape()
        L,H,w=p['length'],p['height'],p['wall'];s=prism(L,p['rear_width'],p['front_width'],-H/2,H)
        s=cut(s,prism(L-2*w,p['rear_width']-2*w,p['front_width']-2*w,-H/2-1,H-w+1))
        if p['opening']:s=cut(s,BRepPrimAPI_MakeBox(gp_Pnt(-p['opening']/2,-min(p['rear_width'],p['front_width'])/4,H/2-w-1),p['opening'],min(p['rear_width'],p['front_width'])/2,w+2).Shape())
        if p['mount_span']:
            for x in (-p['mount_span']/2,p['mount_span']/2):
                for y in (-p['mount_width']/2,p['mount_width']/2):s=cut(s,cylinder(1.7,H+2,-H/2-1,x,y))
        return s
    if kind=='shaft':return cylinder(p['diameter']/2,p['length'],-p['length']/2)
    if kind=='tube':return ring(p['outer'],p['inner'],p['length'])
    if kind=='nut':
        poly=BRepBuilderAPI_MakePolygon()
        for i in range(6):a=math.pi*i/3;poly.Add(gp_Pnt(p['outer']/2*math.cos(a),p['outer']/2*math.sin(a),-p['thickness']/2))
        poly.Close();s=BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(poly.Wire()).Face(),gp_Vec(0,0,p['thickness'])).Shape()
        return cut(s,cylinder(p['inner']/2,p['thickness']+2,-p['thickness']/2-1))
    if kind=='box':
        s=BRepPrimAPI_MakeBox(gp_Pnt(-p['width']/2,-p['depth']/2,-p['height']/2),p['width'],p['depth'],p['height']).Shape()
        return cut(s,cylinder(p['bore']/2,p['height']+2,-p['height']/2-1)) if p['bore'] else s
    if kind=='flange':
        s=ring(p['outer'],p['inner'],p['thickness'])
        for i in range(p['bolts']):
            a=math.pi*2*i/p['bolts'];s=cut(s,cylinder(p['bolt_diameter']/2,p['thickness']+2,-p['thickness']/2-1,p['bolt_circle']/2*math.cos(a),p['bolt_circle']/2*math.sin(a)))
        return s
    if kind=='bolt':return BRepAlgoAPI_Fuse(cylinder(p['diameter']/2,p['length'],-p['length']),cylinder(p['head_diameter']/2,p['head_height'])).Shape()
    if kind=='bearing':
        # Two plain annular races and discrete balls; no machined raceway/contact model.
        a=p['inner']/2;b=p['outer']/2;gap=(b-a)*.32;middle=(a+b)/2;h=p['length'];ball=min(gap*.46,h*.36)
        rings=[ring(2*(middle-gap/2),p['inner'],h),ring(p['outer'],2*(middle+gap/2),h)]
        rings += [BRepPrimAPI_MakeSphere(gp_Pnt(middle*math.cos(i*math.pi/4),middle*math.sin(i*math.pi/4),0),ball).Shape() for i in range(8)]
        return compound(rings)
    raise ValueError('Unregistered part')
def placed(s,pose):
    t=gp_Trsf();R=pose['rotation'];v=pose['position'];t.SetValues(*[x for i in range(3) for x in [*R[i],v[i]]]);return BRepBuilderAPI_Transform(s,t,True).Shape()
def properties(s):
    p=GProp_GProps();BRepGProp.VolumeProperties_s(s,p,True);c=p.CentreOfMass();I=p.MatrixOfInertia()
    return p.Mass(),[c.X(),c.Y(),c.Z()],[[I.Value(i+1,j+1) for j in range(3)] for i in range(3)]
def mesh(s):
    if s.IsNull():return {'vertices':[],'triangles':[]}
    BRepMesh_IncrementalMesh(s,1.0,False,.45,False).Perform();exp=TopExp_Explorer(s,TopAbs_FACE);vertices=[];triangles=[]
    while exp.More():
        face=TopoDS.Face_s(exp.Current());loc=TopLoc_Location();tri=BRep_Tool.Triangulation_s(face,loc)
        if tri is not None:
            offset=len(vertices)
            for i in range(1,tri.NbNodes()+1):v=tri.Node(i).Transformed(loc.Transformation());vertices.append([round(v.X(),6),round(v.Y(),6),round(v.Z(),6)])
            for i in range(1,tri.NbTriangles()+1):
                a,b,c=tri.Triangle(i).Get()
                if face.Orientation()==TopAbs_REVERSED:b,c=c,b
                triangles.append([offset+a-1,offset+b-1,offset+c-1])
        exp.Next()
    if len(vertices)>18000 or len(triangles)>18000:raise ValueError('Per-part display mesh budget exceeded')
    return {'vertices':vertices,'triangles':triangles}
def bounds(s):
    b=Bnd_Box();BRepBndLib.Add_s(s,b,False);return list(b.Get())
def step_file(s,path):
    w=STEPControl_Writer();w.Transfer(s,STEPControl_AsIs)
    if w.Write(str(path))!=IFSelect_RetDone:raise ValueError('STEP export failed')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();out=Path(args.folder).resolve()
    # Folder is supplied by trusted host, never by scene/model.
    if not out.is_dir():raise ValueError('Missing trusted work folder')
    scene=validate_engineering(json.loads(sys.stdin.buffer.read(200001)));poses=assembly_poses(scene);solids={};rows=[];bom=[];cache={};cutbox=BRepPrimAPI_MakeBox(gp_Pnt(-2500,-2500,-2500),5000,2500,5000).Shape()
    Interface_Static.SetCVal_s('write.step.unit','MM')
    for p in scene['parts']:
        key=json.dumps([p['kind'],p['params']],sort_keys=True)
        if key not in cache:cache[key]=shape(p)
        local=cache[key];s=placed(local,poses[p['id']]);solids[p['id']]=s
        if not BRepCheck_Analyzer(s).IsValid():raise ValueError('Invalid CAD B-rep')
        volume,center,inertia=properties(s)
        if volume<=0:raise ValueError('Nonpositive CAD solid volume')
        density=CONTRACT['materials'][p['material']]['density'];mass=volume*1e-9*density
        item={'id':p['id'],'name':p['name'],'kind':p['kind'],'material':p['material'],'density_kg_m3':density,'mass_kg':mass,'volume_mm3':volume,'center_mm':center,'inertia_kg_m2':[[v*density*1e-15 for v in row] for row in inertia],'bounds':bounds(s),'pose':poses[p['id']],'valid':True}
        bom.append(item);rows.append({**item,'color':CONTRACT['materials'][p['material']]['color'],'mesh':mesh(s),'section':mesh(cut(s,cutbox))})
        step_file(s,out/(p['id']+'.step'))
    print('PHASE static',flush=True);collisions=[];pairs=0
    for i,a in enumerate(bom):
        for b in bom[i+1:]:
            aa,bb=a['bounds'],b['bounds']
            if any(aa[k+3]<bb[k]-1e-6 or bb[k+3]<aa[k]-1e-6 for k in range(3)):continue
            pairs+=1;op=BRepAlgoAPI_Common(solids[a['id']],solids[b['id']])
            if not op.IsDone():raise ValueError('CAD intersection inconclusive')
            volume=properties(op.Shape())[0]
            if volume>1e-5:collisions.append({'a':a['id'],'b':b['id'],'volume_mm3':volume})
    fits=[];ids={p['id']:p for p in scene['parts']}
    boxes={p['id']:p['bounds'] for p in bom};path_pairs=0
    def sample_path(step,installed):
        nonlocal path_pairs
        ident=step['part'];hits={}
        for sample in range(7):
            remaining=1-sample/6;delta=[v*step['distance']*remaining for v in step['direction']];box=[boxes[ident][i]+delta[i%3] for i in range(6)];moving=None
            for other in installed:
                b=boxes[other]
                if any(box[k+3]<b[k]-1e-6 or b[k+3]<box[k]-1e-6 for k in range(3)):continue
                if moving is None:
                    tr=gp_Trsf();tr.SetTranslation(gp_Vec(*delta));moving=BRepBuilderAPI_Transform(solids[ident],tr,True).Shape()
                path_pairs+=1;op=BRepAlgoAPI_Common(moving,solids[other])
                if not op.IsDone():raise ValueError('Insertion sample intersection inconclusive')
                volume=properties(op.Shape())[0]
                if volume>1e-5:
                    row=hits.setdefault(other,{'part':ident,'obstacle':other,'max_intersection_mm3':0,'remaining_fractions':[]});row['max_intersection_mm3']=max(row['max_intersection_mm3'],volume);row['remaining_fractions'].append(round(remaining,6))
        return list(hits.values())
    print('PHASE insertion',flush=True);path_hits=[];installed=[]
    for step in scene['steps']:
        path_hits.extend(sample_path(step,installed));installed.append(step['part'])
    insertion={'status':'sampled_interference' if path_hits else 'clear_at_sampled_poses','samples_per_step':7,'narrow_phase_pairs':path_pairs,'hits':path_hits,'limits':'按声明的直线插入方向、距离和父先子后步骤，在每步7个时刻检查已安装零件；离散采样可能漏过薄障碍物或采样间穿透，不是连续碰撞/扫掠体证明。'}
    plan_candidate=None
    if path_hits and not collisions and 'assembly_plan' not in scene:
        parents={m['part']:m['parent'] for m in scene['mates']};attempts=0;failed_sets=set();centers={p['id']:p['center_mm'] for p in bom}
        def search(installed,pending):
            nonlocal attempts
            if not pending:return []
            key=frozenset(installed)
            if key in failed_sets or attempts>=128:return None
            ready=[step for step in pending if step['part'] not in parents or parents[step['part']] in installed]
            ready.sort(key=lambda step:math.dist(centers[step['part']],centers[parents[step['part']]]) if step['part'] in parents else 0)
            for step in ready:
                chosen=None
                for sign in (1,-1):
                    if attempts>=128:return None
                    candidate={**step,'direction':[sign*v for v in step['direction']]};attempts+=1
                    if not sample_path(candidate,installed):chosen=candidate;break
                if chosen is None:continue
                tail=search(installed+[step['part']],[p for p in pending if p['part']!=step['part']])
                if tail is not None:
                    chosen['instruction']='实体采样建议：从相对最终位置 '+str(chosen['direction'])+' 方向的起点，沿反向直线装入；按采样核对，连续路径仍未证明。'
                    return [chosen]+tail
            failed_sets.add(key);return None
        ordered=search([],list(scene['steps']))
        plan_candidate={'status':'candidate_sampled_clear' if ordered is not None else 'no_sampled_plan_found','steps':ordered or [],'attempts':attempts,'limits':'在原方向及其反向、原距离内作有界顺序搜索；不改变零件/配合/最终姿态。建议需重新制作验证，不保证存在解或连续无碰撞，不静默替换原步骤。'}
    print('PHASE groups',flush=True);group_report=None;motion_report=None
    if 'assembly_plan' in scene:
        # All components of each subassembly have the same translation at each sample.
        # Internal intersections are unchanged and covered by static checks.
        installed=[];hits=[];before=path_pairs
        for group in scene['assembly_plan']:
            for ident in group['parts']:
                for hit in sample_path({'part':ident,'direction':group['direction'],'distance':group['distance']},installed):hits.append({**hit,'group':group['id']})
            installed.extend(group['parts'])
        group_report={'status':'sampled_interference' if hits else 'clear_at_sampled_poses','hits':hits,'samples_per_group':7,'narrow_phase_pairs':path_pairs-before,'limits':'子总成以同一刚体平移，逐组检查已安装总成；内部零件相对位置不变。未检查连续扫掠路径。分组内部逐件装配另见 insertion。'}
        parallel_hits=[];parallel_pairs=0;by_step={s['part']:s for s in scene['steps']}
        for group in scene['assembly_plan']:
            batches=group.get('batches',[[s['part']] for s in scene['steps'] if s['part'] in group['parts']]);installed=[]
            for batch_index,batch in enumerate(batches):
                for ident in batch:
                    for hit in sample_path(by_step[ident],installed):parallel_hits.append({**hit,'group':group['id'],'batch':batch_index})
                for sample in range(7):
                    at={};bb={}
                    for ident in batch:
                        step=by_step[ident];delta=[v*step['distance']*(1-sample/6) for v in step['direction']];tr=gp_Trsf();tr.SetTranslation(gp_Vec(*delta));at[ident]=BRepBuilderAPI_Transform(solids[ident],tr,True).Shape();bb[ident]=[boxes[ident][i]+delta[i%3] for i in range(6)]
                    for i,a in enumerate(batch):
                        for b in batch[i+1:]:
                            if any(bb[a][k+3]<bb[b][k]-1e-6 or bb[b][k+3]<bb[a][k]-1e-6 for k in range(3)):continue
                            parallel_pairs+=1;op=BRepAlgoAPI_Common(at[a],at[b])
                            if not op.IsDone():raise ValueError('Parallel sample intersection inconclusive')
                            volume=properties(op.Shape())[0]
                            if volume>1e-5:parallel_hits.append({'group':group['id'],'batch':batch_index,'a':a,'b':b,'remaining_fraction':1-sample/6,'volume_mm3':volume})
                installed.extend(batch)
        group_report['parallel_internal']={'status':'sampled_interference' if parallel_hits else 'clear_at_sampled_poses','hits':parallel_hits,'samples_per_batch':7,'moving_pair_checks':parallel_pairs,'limits':'独立子总成工位内，每批次7时刻检查移动零件间及前序已装件；批内同时、批间顺序。不含其他总成或连续路径。'}
    if 'operation' in scene:
        print('PHASE motion',flush=True)
        # Fixed 9/30 B-rep poses, separately scoped from insertion checks.
        hits=[];tested=0;cache_hits=0;motion_cache={};static_volume={(c['a'],c['b']):c['volume_mm3'] for c in collisions}
        identity=(1,0,0,0,1,0,0,0,1,0,0,0)
        signature=lambda t:tuple(v for row in t['rotation'] for v in row)+tuple(t['position'])
        extended=scene['operation'].get('verification')=='extended';maximum=scene['operation']['max_steer'];steers=[-maximum,-maximum/2,0,maximum/2,maximum] if extended else [-maximum,0,maximum]
        patterns=[[a]*4 for a in (0,math.pi/4,math.pi/2)]
        if extended:patterns=[[0]*4,[math.pi/10]*4,[math.pi/5]*4,[0,math.pi/2,math.pi/3,0],[math.pi/2,0,0,math.pi/3],[math.pi,math.pi/3,math.pi/2,math.pi/4]]
        for steering in steers:
            for phase in patterns:
                delta=operation_transforms(scene,phase,steering);moving={k:placed(solids[k],v) for k,v in delta.items()};at={**solids,**moving};bb={k:bounds(s) for k,s in moving.items()}
                for i,a in enumerate(ids):
                    for b in list(ids)[i+1:]:
                        if a not in delta and b not in delta:continue
                        aa,ab=bb.get(a,boxes[a]),bb.get(b,boxes[b])
                        if any(aa[k+3]<ab[k]-1e-6 or ab[k+3]<aa[k]-1e-6 for k in range(3)):continue
                        sa=signature(delta[a]) if a in delta else identity;sb=signature(delta[b]) if b in delta else identity;key=(a,b,sa,sb)
                        if sa==sb:volume=static_volume.get((a,b),0);cache_hits+=1
                        elif key in motion_cache:volume=motion_cache[key];cache_hits+=1
                        else:
                            tested+=1;op=BRepAlgoAPI_Common(at[a],at[b])
                            if not op.IsDone():raise ValueError('Motion sample intersection inconclusive')
                            volume=properties(op.Shape())[0];motion_cache[key]=volume
                        if volume>1e-5:hits.append({'a':a,'b':b,'steer_deg':steering,'wheel_phase_rad':phase,'volume_mm3':volume})
        motion_report={'status':'sampled_interference' if hits else 'clear_at_sampled_poses','hits':hits,'poses':len(steers)*len(patterns),'narrow_phase_pairs':tested,'reused_identical_checks':cache_hits,'limits':'限定转向/车轮相位组合的 B-rep 离散采样，extended 含异相轮位；完全相同刚体变换复用静态/已算交集。未穷举独立相位、全转角域、连续轨迹、轮胎接触和动力学。'}
    for m in scene['mates']:
        parent,child=ids[m['parent']],ids[m['part']];d=None;engagement=None
        if parent['kind']=='shaft' and m['parent_port']=='axis' and m['child_port']=='axis' and 'inner' in child['params']:d=child['params']['inner']-parent['params']['diameter']
        if parent['kind']=='flange' and m['parent_port'].startswith('bolt-') and child['kind']=='bolt':d=parent['params']['bolt_diameter']-child['params']['diameter']
        if parent['kind']=='bolt' and child['kind']=='nut' and m['parent_port']==m['child_port']=='axis':
            d=child['params']['inner']-parent['params']['diameter'];h=child['params']['thickness'];engagement=max(0,min(0,m['gap']+h/2)-max(-parent['params']['length'],m['gap']-h/2))
        status='unverified' if d is None else 'pass' if (d>=0 if m['fit']!='press' else d<=0) else 'mismatch'
        if engagement is not None and engagement<child['params']['thickness']-1e-6:status='mismatch'
        fits.append({'part':m['part'],'parent':m['parent'],'declared_fit':m['fit'],'diametral_clearance_mm':d,'axial_engagement_mm':engagement,'status':status})
    print('PHASE assembly export',flush=True);assembly=compound(list(solids.values()));step_file(assembly,out/'assembly.step');reader=STEPControl_Reader()
    if reader.ReadFile(str(out/'assembly.step'))!=IFSelect_RetDone:raise ValueError('STEP reimport failed')
    reader.TransferRoots();reimport=reader.OneShape();original=properties(assembly)[0];roundtrip=properties(reimport)[0]
    bound_error=max(abs(a-b) for a,b in zip(bounds(assembly),bounds(reimport)))
    if not BRepCheck_Analyzer(reimport).IsValid() or abs(roundtrip-original)/original>1e-6 or bound_error>1e-5:raise ValueError('STEP roundtrip validation failed')
    BRepMesh_IncrementalMesh(assembly,.3,False,.3,False).Perform();stl=StlAPI_Writer();stl.ASCIIMode=False
    if not stl.Write(assembly,str(out/'assembly.stl')):raise ValueError('STL export failed')
    # DXF is a true planar outline of the first flange: circles, center bore and holes.
    flange=next((p for p in scene['parts'] if p['kind']=='flange'),None)
    if flange:
        q=flange['params'];circles=[(0,0,q['outer']/2)]+([(0,0,q['inner']/2)] if q['inner'] else [])+[(q['bolt_circle']/2*math.cos(i*2*math.pi/q['bolts']),q['bolt_circle']/2*math.sin(i*2*math.pi/q['bolts']),q['bolt_diameter']/2) for i in range(q['bolts'])]
        dxf='0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n0\nSECTION\n2\nENTITIES\n'
        for x,y,r in circles:dxf+=f'0\nCIRCLE\n8\n0\n10\n{x}\n20\n{y}\n30\n0\n40\n{r}\n'
        (out/'flange-profile.dxf').write_text(dxf+'0\nENDSEC\n0\nEOF\n',encoding='ascii')
    with (out/'bom.csv').open('w',newline='',encoding='utf-8-sig') as f:
        safe=lambda x: "'"+x if isinstance(x,str) and x.lstrip().startswith(('=','+','-','@')) else x
        w=csv.writer(f);w.writerow(['id','name','material','mass_kg','volume_mm3']);w.writerows([safe(p[k]) for k in ['id','name','material','mass_kg','volume_mm3']] for p in bom)
    report={'schema':'anatomy.engineering.result.v1','parts':rows,'bom':bom,'assembly':{'interference_status':'interference' if collisions else 'clear_at_static_pose','collisions':collisions,'narrow_phase_pairs':pairs,'fits':fits,'step_roundtrip_relative_volume_error':abs(roundtrip-original)/original,'step_roundtrip_bounds_error_mm':bound_error,'total_mass_kg':sum(p['mass_kg'] for p in bom),'limits':'静态装配姿态 B-rep 体积交集检查；不证明运动全过程或装配插入路径无碰撞。配合检查为名义尺寸，未含制造公差。轴承滚道/螺纹/预紧为简化。'},'experiments':solve(scene['experiments'],{'combustion':combustion}),'units':{'length':'mm','mass':'kg','inertia':'kg*m^2'},'limits':['展示的装配步骤是用户/模型定义的操作次序，插入路径未经连续碰撞检查。','剖面为原实体沿全局 Y=0 的真实布尔截面；展示拆解不改变检查几何。','CAD 有效性与 STEP 回读不等于制造认证。']}
    report['assembly']['insertion']=insertion
    report['assembly']['plan_candidate']=plan_candidate
    report['assembly']['groups']=group_report
    report['assembly']['operation']=motion_report
    if scene.get('operation',{}).get('transmission'):report['assembly']['transmission']={'ratios_to_carrier':transmission_ratios(scene),'limits':'20°直齿渐开线样条插值近似，直线简化齿根；未建模刀具根切/圆角、弹性接触、齿面应力、润滑与效率。差速内部仍为理想平均关系。'}
    report['limits'][0]='装配插入已作每步7时刻的离散实体采样检查，不能作为连续无碰撞路径证明。'
    (out/'configuration.json').write_text(json.dumps(scene,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'report.json').write_text(json.dumps({k:v for k,v in report.items() if k!='parts'},ensure_ascii=False,indent=2),encoding='utf-8')
    provenance={'first_party':'Jarvis trusted parameter/CAD/numerical adapters; first-party project licensing remains as declared by the project','anatomy':json.loads((ROOT/'external/anatomy/source.json').read_text(encoding='utf-8')),'native_runtime':json.loads((ROOT/'modules/skills/anatomy/runtime-lock.json').read_text(encoding='utf-8'))}
    (out/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8');(out/'LICENSE.anatomy.txt').write_bytes((ROOT/'external/anatomy/LICENSE').read_bytes())
    with zipfile.ZipFile(out/'cad-package.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in out.iterdir():
            if path.suffix in ('.step','.stl','.csv','.dxf','.json','.txt'):z.write(path,path.name)
    (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print(json.dumps({'status':'completed','parts':len(bom),'collisions':len(collisions)}))

if __name__=='__main__':main()
