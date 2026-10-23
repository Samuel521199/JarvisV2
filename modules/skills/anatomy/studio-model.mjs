// Pure, bounded teaching models. No combustion/CFD/circuit transient solver.
export function validateScene(value,schema){
 const fail=()=>{throw Error('场景无效：请核对组件、参数、效果和无环连接。')},object=v=>v&&typeof v==='object'&&!Array.isArray(v),keys=(v,w)=>object(v)&&Object.keys(v).sort().join(',')===w.split(' ').sort().join(','),txt=(v,n,empty=false)=>typeof v==='string'&&(empty||v.trim().length>0)&&v.trim().length<=n&&!/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v);
 if(!keys(value,'version title description modules links unfulfilled')||value.version!==1||!txt(value.title,80)||!txt(value.description,500,true)||!Array.isArray(value.modules)||value.modules.length<1||value.modules.length>8||!Array.isArray(value.links)||value.links.length>8||!Array.isArray(value.unfulfilled)||value.unfulfilled.length>12||value.unfulfilled.some(x=>!txt(x,200)))fail();
 const ids=new Map(),incoming=new Map();const scene={version:1,title:value.title.trim(),description:value.description.trim(),modules:[],links:[],unfulfilled:value.unfulfilled.map(x=>x.trim())};
 for(const m of value.modules){
  if(!keys(m,'id type label params effects')||typeof m.id!=='string'||!(/^[a-z][a-z0-9-]{0,23}$/).test(m.id)||ids.has(m.id)||!Object.hasOwn(schema.types,m.type)||!txt(m.label,50))fail();
  const spec=schema.types[m.type],params={};if(!object(m.params)||Object.keys(m.params).some(k=>!Object.hasOwn(spec.params,k))||!Array.isArray(m.effects)||new Set(m.effects).size!==m.effects.length||m.effects.some(e=>!spec.effects.includes(e)))fail();
  for(const [k,r] of Object.entries(spec.params)){const v=Object.hasOwn(m.params,k)?m.params[k]:r.default;if(r.kind==='parts'){params[k]=validateParts(v,schema);continue;}if(r.enum?!r.enum.includes(v):typeof v!=='number'||!Number.isFinite(v)||v<r.min||v>r.max||r.integer&&!Number.isInteger(v))fail();params[k]=v;}
  const row={id:m.id,type:m.type,label:m.label.trim(),params,effects:[...m.effects]};ids.set(m.id,row);scene.modules.push(row);
 }
 for(const l of value.links){if(!keys(l,'from to kind ratio')||!ids.has(l.from)||!ids.has(l.to)||l.from===l.to||incoming.has(l.to)||!Object.hasOwn(schema.links,l.kind))fail();const s=schema.links[l.kind];if(!s.from.includes(ids.get(l.from).type)||!s.to.includes(ids.get(l.to).type)||typeof l.ratio!=='number'||!Number.isFinite(l.ratio)||Math.abs(l.ratio)<.1||Math.abs(l.ratio)>4||l.kind==='flow'&&l.ratio<0)fail();incoming.set(l.to,l);scene.links.push({...l});}
 const active=new Set(),done=new Map();
 function bound(id){if(active.has(id))fail();if(done.has(id))return done.get(id);active.add(id);const m=ids.get(id),p=m.params;let rpm=Math.abs(p.rpm||0);if(m.type==='motor')rpm=p.switch_closed?p.constant*p.voltage/(p.resistance*.0002+p.constant**2)*60/(2*Math.PI):0;if(incoming.has(id)){const l=incoming.get(id),s=bound(l.from);if(l.kind==='shaft')rpm=s*Math.abs(l.ratio);}if(m.type==='gear-pair')rpm*=p.teeth_a/p.teeth_b;if(rpm>24000)fail();active.delete(id);done.set(id,rpm);return rpm;}
 for(const id of ids.keys())bound(id);return scene;
}
export const mod=(x,n)=>((x%n)+n)%n;
export function validateParts(parts,schema){
 const fail=()=>{throw Error('零件配置无效：请核对基本体、关节、范围与父子树。')},contract=schema.parts_contract,ids=new Map();if(!Array.isArray(parts)||parts.length<1||parts.length>16)fail();
 for(const p of parts){if(!p||typeof p!=='object'||Array.isArray(p)||Object.keys(p).sort().join(',')!==[...contract.required].sort().join(',')||typeof p.id!=='string'||!(/^[a-z][a-z0-9-]{0,23}$/).test(p.id)||ids.has(p.id)||typeof p.parent!=='string')fail();
  for(const k of ['shape','joint','axis','color'])if(!contract[k].includes(p[k]))fail();
  for(const [k,lo,hi] of [['position',-150,150],['offset',-150,150],['size',2,100],['rotation',-180,180]])if(!Array.isArray(p[k])||p[k].length!==3||p[k].some(v=>typeof v!=='number'||!Number.isFinite(v)||v<lo||v>hi))fail();
  if(p.shape==='cylinder'&&p.size[0]!==p.size[1])fail();
  for(const [k,hi] of [['amplitude',p.joint==='revolute'?180:p.joint==='prismatic'?100:0],['frequency',2],['phase',360]])if(typeof p[k]!=='number'||!Number.isFinite(p[k])||p[k]<0||p[k]>hi)fail();ids.set(p.id,p);
 }
 const done=new Set(),active=new Set();function visit(id){if(active.has(id)||!ids.has(id))fail();if(done.has(id))return;active.add(id);if(ids.get(id).parent)visit(ids.get(id).parent);active.delete(id);done.add(id);}for(const id of ids.keys())visit(id);return structuredClone(parts);
}
const I3=()=>[[1,0,0],[0,1,0],[0,0,1]],mv=(a,b)=>a.map(row=>row.reduce((s,v,i)=>s+v*b[i],0)),mm=(a,b)=>a.map(row=>b[0].map((_,j)=>row.reduce((s,v,i)=>s+v*b[i][j],0))),add=(a,b)=>a.map((v,i)=>v+b[i]);
function rotation(axis,degrees){const i='xyz'.indexOf(axis),j=(i+1)%3,k=(i+2)%3,r=I3(),c=Math.cos(degrees*Math.PI/180),s=Math.sin(degrees*Math.PI/180);r[j][j]=c;r[j][k]=-s;r[k][j]=s;r[k][k]=c;return r;}
export function assemblyState(parts,time){
 const ids=new Map(parts.map(p=>[p.id,p])),done=new Map();
 function visit(id){if(done.has(id))return done.get(id);const p=ids.get(id),parent=p.parent?visit(p.parent):{rotation:I3(),position:[0,0,0]},rest=mm(mm(rotation('x',p.rotation[0]),rotation('y',p.rotation[1])),rotation('z',p.rotation[2]));
  const value=p.joint==='fixed'?0:p.amplitude*Math.sin(2*Math.PI*p.frequency*time+p.phase*Math.PI/180),shift=[0,0,0];if(p.joint==='prismatic')shift['xyz'.indexOf(p.axis)]=value;
  const R=mm(parent.rotation,mm(rest,p.joint==='revolute'?rotation(p.axis,value):I3())),position=add(parent.position,mv(parent.rotation,add(p.position,mv(rest,shift)))),center=add(position,mv(R,p.offset));let local=[],faces=[];
  if(p.shape==='box'){const [w,d,h]=p.size;for(const z of [-h/2,h/2])for(const y of [-d/2,d/2])for(const x of [-w/2,w/2])local.push([x,y,z]);faces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]];}
  else{const n=20;for(const z of [-p.size[2]/2,p.size[2]/2])for(let i=0;i<n;i++)local.push([p.size[0]/2*Math.cos(i*2*Math.PI/n),p.size[0]/2*Math.sin(i*2*Math.PI/n),z]);faces.push(Array.from({length:n},(_,i)=>i),Array.from({length:n},(_,i)=>i+n));for(let i=0;i<n;i++)faces.push([i,(i+1)%n,(i+1)%n+n,i+n]);}
  const row={id,value,rotation:R,position,center,vertices:local.map(v=>add(center,mv(R,v))),faces,color:p.color,joint:p.joint};done.set(id,row);return row;
 }for(const id of ids.keys())visit(id);return Object.fromEntries(done);
}
export function engineCylinder(p,angle,index=0){
 const phase=mod(angle+index*720/p.cylinders,720),theta=phase*Math.PI/180,r=p.crank_mm,L=r*p.rod_ratio;
 const pinX=r*Math.sin(theta),pinZ=r*Math.cos(theta),piston=pinZ+Math.sqrt(L*L-pinX*pinX),stage=Math.floor(phase/180);
 return {phase,stage,pinX,pinZ,piston,displacement:r+L-piston,intake:stage===0,exhaust:stage===3,spark:phase>=360&&phase<374,flame:stage===2?Math.sin((phase-360)/180*Math.PI):0};
}
export function motorState(p){
 const b=.0002,K=p.constant,R=p.resistance,V=p.voltage;
 const omega=p.switch_closed?Math.max(0,(K*V/R-p.load)/(b+K*K/R)):0;
 const current=p.switch_closed?(V-K*omega)/R:0,torque=K*current;
 return {omega,rpm:omega*60/(2*Math.PI),current,torque,backEmf:K*omega,inputPower:V*current,copperLoss:current*current*R,loadPower:p.load*omega,frictionPower:b*omega*omega,stalled:p.switch_closed&&V>0&&omega===0};
}
export function waveState(p,x,t,drive=1){
 const k=2*Math.PI/p.wavelength,omega=Math.sqrt(9.81*k*Math.tanh(k*p.depth)),a=p.amplitude*Math.min(1,Math.max(0,drive));
 // Half-amplitude counterpropagating waves keep the requested peak bound.
 const height=p.interference?a*Math.cos(k*x)*Math.cos(omega*t):a*Math.cos(k*x-omega*t);
 return {k,omega,frequency:omega/(2*Math.PI),phaseSpeed:omega/k,height,amplitude:a};
}
export function sceneState(scene,time,angles={}){
 const ids=new Map(scene.modules.map(m=>[m.id,m])),incoming=new Map(scene.links.map(l=>[l.to,l])),done=new Map();
 function visit(id){if(done.has(id))return done.get(id);const m=ids.get(id),p=m.params,l=incoming.get(id);let motor=m.type==='motor'?motorState(p):null,rpm=motor?motor.rpm:(p.rpm||0)*(m.type==='jet'?p.throttle:1),angle=angles[id]??rpm*time*6,drive=1;
  if(l){const source=visit(l.from);if(l.kind==='shaft'){rpm=source.rpm*l.ratio;angle=source.angle*l.ratio;}else drive=Math.min(1,Math.abs(source.rpm)/600*l.ratio);}
  const inputRpm=rpm===0?0:rpm,inputAngle=angle===0?0:angle;if(m.type==='gear-pair'){rpm=-rpm*p.teeth_a/p.teeth_b;angle=-angle*p.teeth_a/p.teeth_b;}if(rpm===0)rpm=0;if(angle===0)angle=0;
  const row={id,type:m.type,rpm,angle,inputRpm,inputAngle,drive,motor,wave:m.type==='wave'?waveState(p,0,time,drive):null,assembly:m.type==='assembly'?assemblyState(p.parts,time):null,cylinders:m.type==='four-stroke'?Array.from({length:p.cylinders},(_,i)=>engineCylinder(p,angle,i)):null};done.set(id,row);return row;
 }for(const id of ids.keys())visit(id);return Object.fromEntries(done);
}
