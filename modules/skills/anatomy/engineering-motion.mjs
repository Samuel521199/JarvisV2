// Bounded, first-party rigid transforms. No model expressions or executable input.
export const matmul=(a,b)=>a.map((row,i)=>row.map((_,j)=>row.reduce((sum,x,k)=>sum+x*b[k][j],0)));
export const matvec=(a,v)=>a.map(row=>row.reduce((sum,x,j)=>sum+x*v[j],0));
export const turnZ=a=>{const c=Math.cos(a),s=Math.sin(a);return [[c,-s,0],[s,c,0],[0,0,1]];};
export const turnY=a=>{const c=Math.cos(a),s=Math.sin(a);return [[c,0,s],[0,1,0],[-s,0,c]];};
export const around=(rotation,pivot)=>({rotation,position:matvec(rotation,pivot).map((x,i)=>pivot[i]-x)});
export const transformPoint=(t,v)=>t?matvec(t.rotation,v).map((x,i)=>x+t.position[i]):v;
export function transmissionRatios(scene){
 const t=scene.operation?.transmission;if(!t)return {};const ids=Object.fromEntries(scene.parts.map(p=>[p.id,p])),edges={};
 const link=(a,b,r)=>{(edges[a]??=[]).push([b,r]);(edges[b]??=[]).push([a,1/r]);};
 for(const p of t.stages)link(p.driver,p.driven,-ids[p.driver].params.teeth/ids[p.driven].params.teeth);
 for(const s of t.shafts)for(const id of s.parts)if(id!==s.gear)link(s.gear,id,1);
 const ratios={[t.output]:1},pending=[t.output];while(pending.length){const a=pending.pop();for(const [b,r] of edges[a]||[])if(ratios[b]===undefined){ratios[b]=ratios[a]*r;pending.push(b);}}
 return ratios;
}
export function vehicleKinematics(o,steer){
 const delta=Math.max(-o.max_steer,Math.min(o.max_steer,steer))*Math.PI/180,L=o.wheelbase,radius=Math.abs(delta)>1e-10?L/Math.tan(delta):null,rearX=o.wheels.find(w=>w.axle==='rear').center[0],angles=[],ratios=[];
 for(const w of o.wheels){const a=radius!==null&&w.axle==='front'?Math.atan(L/(radius-w.pivot[1])):0,v=w.center.map((x,i)=>x-w.pivot[i]),c=Math.cos(a),s=Math.sin(a),center=[w.pivot[0]+c*v[0]-s*v[1],w.pivot[1]+s*v[0]+c*v[1],w.center[2]];angles.push(a*180/Math.PI);ratios.push(radius===null?1:Math.hypot(center[0]-rearX,center[1]-radius)/Math.abs(radius));}
 return {steer_deg:angles,speed_ratios:ratios,turn_radius_mm:radius};
}
export function operationTransforms(scene,phases,steer){
 const o=scene.operation,k=vehicleKinematics(o,steer),out={};
 o.wheels.forEach((w,i)=>{const R=turnZ(k.steer_deg[i]*Math.PI/180),t=around(R,w.pivot),roll=around(turnY(phases[i]),w.center),combined={rotation:matmul(R,roll.rotation),position:matvec(R,roll.position).map((x,j)=>x+t.position[j])};if(w.axle==='front')for(const id of o.steering_parts[w.side])out[id]=t;for(const id of w.parts)out[id]=combined;});
 const rear=o.wheels.map((w,i)=>w.axle==='rear'?i:-1).filter(i=>i>=0),angle=rear.reduce((s,i)=>s+phases[i],0)/rear.length,pivot=o.wheels[rear[0]].center;
 for(const id of o.rear_rotating)out[id]=around(turnY(angle),pivot);
 if(o.transmission){const ids=Object.fromEntries(scene.parts.map(p=>[p.id,p]));for(const [id,ratio] of Object.entries(transmissionRatios(scene)))out[id]=around(turnY(angle*ratio),ids[id].position);}
 return out;
}
export function assemblyItems(scene,scope='',mode='parts'){
 const group=(scene.assembly_plan||[]).find(g=>g.id===scope),steps=scene.steps.filter(s=>!group||group.parts.includes(s.part));
 if(!group&&mode==='groups')return scene.assembly_plan.map(g=>({id:g.id,name:g.name,parts:g.parts,direction:g.direction,distance:g.distance,instruction:'将已预装的 '+g.name+' 作为刚体整体装入。'}));
 if(group&&mode==='parallel')return (group.batches||steps.map(s=>[s.part])).map((parts,i)=>({id:group.id+'-'+i,name:parts.length+' 件同步 · '+parts.map(id=>scene.parts.find(p=>p.id===id).name).join(' / '),parts,parallel:true,instruction:'独立工位第 '+(i+1)+' 批：'+parts.length+' 件沿各自声明路径同步装入；前序批次保持已安装姿态。'}));
 return steps.map(s=>({...s,id:s.part,name:scene.parts.find(p=>p.id===s.part).name,parts:[s.part]}));
}
export function assemblyOffsets(scene,items,progress,explode){
 const out={},steps=Object.fromEntries(scene.steps.map(s=>[s.part,s]));items.forEach((s,i)=>{if(progress<=i)return;const u=Math.min(1,progress-i);for(const id of s.parts){const path=s.parallel?steps[id]:s;out[id]=path.direction.map(x=>x*path.distance*(explode+1-u));}});return out;
}
export function operationReady({scope,progress,total,explode,playing,assembly}){
 return !scope&&progress>=total&&explode===0&&!playing&&assembly.collisions.length===0&&!assembly.fits.some(f=>f.status==='mismatch')&&!(assembly.insertion?.hits.length)&&!(assembly.groups?.hits.length)&&!(assembly.groups?.parallel_internal?.hits.length)&&assembly.operation?.status==='clear_at_sampled_poses';
}
