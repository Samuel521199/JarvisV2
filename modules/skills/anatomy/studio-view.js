(()=>{'use strict';
const Q=s=>document.querySelector(s),NS='http://www.w3.org/2000/svg',M=SceneModel;
let scene=M.validateScene(JSON.parse(Q('#scene-data').textContent),sceneSchema),time=0,angles={},playing=!matchMedia('(prefers-reduced-motion: reduce)').matches,last=null,lastPaint=0,frames=0,shown=new Set();
let view3D={azimuth:38,elevation:25,zoom:1,explode:0,shell:'section',cut:0,labels:true,layers:{housing:true,fixed:true,moving:true,fluid:true}},inspecting=null;
const structures=new Map(),selectedParts=new Map();
const fmt=(n,d=1)=>Number(n).toFixed(d),xy=p=>p.map(x=>fmt(x,2)).join(','),line=(a,b,attrs='class="axis"')=>`<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" ${attrs}/>`;
const circle=(x,y,r,attrs='class="metal"')=>`<circle cx="${x}" cy="${y}" r="${r}" ${attrs}/>`,path=(points,attrs='class="muted-path"',closed=false)=>`<path d="${pathOf(points,closed)}" ${attrs}/>`;
const fixedText=(x,y,s)=>`<text x="${x}" y="${y}">${s}</text>`;
const has=(m,e)=>Q('#effects').checked&&m.effects.includes(e);
function particlePath(points,t,color,count=10){let s='';for(let i=0;i<count;i++){const u=M.mod(t*.65+i/count,1)*(points.length-1),j=Math.min(points.length-2,Math.floor(u)),f=u-j,a=points[j],b=points[j+1];s+=circle(a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f,2.4,`fill="${color}" opacity=".85"`);}return s;}
function engine(m,s){
 const n=m.params.cylinders,scale=14/m.params.crank_mm,L=14*m.params.rod_ratio,spacing=33,extent=(n-1)*spacing;
 const P=fitProjection(boxCorners({x:-35,y:-28,w:70,d:extent+56},-20,L+65),600,330,{pad:35,elevation:28,azimuth:20});
 const pt=(x,y,z)=>iso([x,y,z],P);let out='';
 const base=slabOf({x:-29,y:-22,w:58,d:extent+44,r:6},-14,6,P,4,.4);out+=solidSvg(base,{className:'base'});out+=line(pt(0,-21,0),pt(0,extent+23,0),'stroke="#809aac" stroke-width="8" stroke-linecap="round"');
 for(let i=0;i<n;i++){
  const c=s.cylinders[i],y=i*spacing,pz=c.piston*scale,px=c.pinX*scale,cz=c.pinZ*scale,head=14+L+11,gasColor=['#69bde0','#eec870','#f6a263','#a79acb'][c.stage];
  if(Q('#cutaway').checked){for(const x of [-17,17]){out+=line(pt(x,y-12,-5),pt(x,y-12,head),'class="wire"');out+=line(pt(x,y+12,-5),pt(x,y+12,head),'class="wire"');}out+=path([pt(-17,y-12,head),pt(17,y-12,head),pt(17,y+12,head),pt(-17,y+12,head)],'class="wire"',true);}
  // Exact pin-to-piston length; the walls remain open so the linkage is visible.
  out+=line(pt(0,y,0),pt(px,y,cz),'stroke="#d99356" stroke-width="9" stroke-linecap="round"');out+=circle(...pt(px,y,cz),4,'fill="#efcba9" stroke="#a47956"');out+=line(pt(px,y,cz),pt(0,y,pz),'stroke="#8a9fac" stroke-width="6" stroke-linecap="round"');
  out+=solidSvg(cylinder(0,y,14,pz-4,8,P,20,.4),{className:'piston'});out+=circle(...pt(0,y,pz),2,'fill="#f0f6fa"');
  if(has(m,'airflow')||has(m,'flame'))out+=path([pt(-12,y-8,pz+4),pt(12,y-8,pz+4),pt(12,y-8,head-4),pt(-12,y-8,head-4)],`fill="${gasColor}" fill-opacity=".22" stroke="none"`,true);
  out+=line(pt(-10,y,head+6),pt(-10,y,head-(c.intake?9:2)),`stroke="${c.intake?'#37a9d2':'#8c9aa6'}" stroke-width="3"`);out+=line(pt(10,y,head+6),pt(10,y,head-(c.exhaust?9:2)),`stroke="${c.exhaust?'#a08bcf':'#8c9aa6'}" stroke-width="3"`);
  if(has(m,'airflow')){if(c.intake)out+=particlePath([pt(-29,y,head+9),pt(-10,y,head),pt(-3,y,pz+9)],time*2,'#44b7e1',6);if(c.exhaust)out+=particlePath([pt(4,y,pz+9),pt(10,y,head),pt(32,y,head+9)],time*2,'#a58cda',6);}
  if(has(m,'flame')&&c.flame>0){const center=pt(0,y,head-7),height=Math.max(3,(head-pz-10)*P.scale*.9);for(let j=0;j<5;j++){const x=center[0]+(j-2)*4,h=height*(.4+.6*Math.abs(Math.sin(time*13+j)));out+=path([[x-3,center[1]],[x+Math.sin(time*10+j)*3,center[1]+h],[x+3,center[1]]],`class="flame" opacity="${.25+c.flame*.6}"`,true);}}
  if(has(m,'spark')&&c.spark){const a=pt(0,y,head);out+=path([[a[0]-4,a[1]-8],[a[0]+3,a[1]-3],[a[0]-2,a[1]],[a[0]+5,a[1]+7]],'stroke="#ffcd42" stroke-width="3" fill="none"');}
  const label=pt(0,y,head+16);out+=fixedText(label[0]-10,label[1],String(i+1));
 }
 out+=fixedText(24,308,'蓝：进气 · 黄：压缩 · 橙：做功 · 紫：排气');return out;
}
function jet(m,s){
 const a=s.angle*Math.PI/180,th=m.params.throttle;let out='';
 if(Q('#cutaway').checked){out+=path([[35,112],[110,86],[220,102],[340,90],[445,110],[540,128],[540,205],[445,224],[340,242],[220,230],[110,246],[35,220]],'fill="#9bb7c5" fill-opacity=".12" stroke="#7493a8" stroke-width="2"',true);}
 out+=line([85,167],[478,167],'stroke="#9cb0be" stroke-width="12" stroke-linecap="round"');
 for(let i=0;i<7;i++){const x=112+i*18,h=48-i*3,v=Math.sin(a+i*.6)*11;out+=path([[x,167],[x+v,167-h],[x+7+v,170-h],[x+6,167],[x+7-v,167+h],[x-v,167+h]],'class="metal"',true);}
 for(let i=0;i<4;i++){const x=390+i*17,h=47-i*6,v=Math.sin(a+i)*12;out+=path([[x,166],[x+v,166-h],[x+v+7,166-h],[x+6,166],[x-v+6,166+h],[x-v,166+h]],'class="copper"',true);}
 out+=path([[256,115],[345,115],[365,141],[256,141]],'class="copper"',true)+path([[256,192],[365,192],[345,217],[256,217]],'class="copper"',true);
 if(has(m,'airflow')&&th>0){for(let j=0;j<6;j++){const y=127+j*16,route=[[20,y],[105,y],[235,140+j*10],[350,140+j*10],[490,y],[575,155+j*5]];out+=path(route,'stroke="#66b5d3" stroke-width=".8" opacity=".4" fill="none"');out+=particlePath(route,time*(.5+th),j<3?'#50b9e3':'#c6a3df',9);}}
 if(has(m,'flame')&&th>0){for(let j=0;j<7;j++){const y=146+j*7,len=(20+35*th)*(1+.25*Math.sin(time*10+j));out+=path([[273,y-3],[273+len,y+Math.sin(time*14+j)*4],[273,y+3]],`class="flame" opacity="${.4+th*.4}"`,true);}for(let j=0;j<5;j++)out+=path([[540,151+j*7],[540+(15+55*th)*(1+.2*Math.sin(time*9+j)),154+j*7],[540,158+j*7]],'fill="#c1a1e5" opacity=".3"',true);}
 out+=fixedText(60,280,'进气')+fixedText(142,280,'压气机')+fixedText(273,280,'燃烧室')+fixedText(400,280,'涡轮')+fixedText(503,280,'喷口');return out;
}
function motor(m,s){
 const p=m.params,c=s.motor,a=s.angle*Math.PI/180,active=c.current>1e-8;let out='';
 out+=path([[55,215],[55,71],[178,71],[215,71],[315,71],[315,114]],'class="muted-path"')+path([[315,221],[315,260],[55,260],[55,244]],'class="muted-path"');
 out+=line([38,216],[72,216],'stroke="#d6aa36" stroke-width="3"')+line([44,230],[65,230],'stroke="#d6aa36" stroke-width="5"')+fixedText(26,190,fmt(p.voltage,1)+' V');
 out+=circle(178,71,3)+circle(216,71,3)+line([178,71],p.switch_closed?[216,71]:[208,51],'stroke="#ca9c38" stroke-width="3"');
 if(Q('#cutaway').checked)out+=`<rect x="238" y="111" width="161" height="113" rx="26" fill="#aac0cd" fill-opacity=".1" stroke="#7894a6" stroke-width="2"/>`;
 out+=`<rect x="256" y="121" width="126" height="23" rx="7" fill="#d98e7e"/><rect x="256" y="192" width="126" height="22" rx="7" fill="#7d9dc8"/>`+fixedText(271,137,'N')+fixedText(271,208,'S');
 out+=circle(318,167,38,'class="lightmetal"');for(let i=0;i<4;i++){const b=a+i*Math.PI/2;out+=line([318+12*Math.cos(b),167+12*Math.sin(b)],[318+34*Math.cos(b),167+34*Math.sin(b)],'stroke="#d39558" stroke-width="9" stroke-linecap="round"');}out+=circle(318,167,10,'class="metal"')+line([352,167],[465,167],'stroke="#a6b5c0" stroke-width="8"')+circle(466,167,27,'class="metal"');out+=line([466,167],[466+21*Math.cos(a),167+21*Math.sin(a)],'stroke="#f5b64d" stroke-width="4"');
 if(has(m,'field'))for(let i=0;i<5;i++)out+=path([[276+i*21,147],[276+i*21,190]],'stroke="#a494d3" stroke-width="1" stroke-dasharray="3 4" fill="none"');
 if(has(m,'current')&&active){out+=particlePath([[55,215],[55,71],[315,71],[315,114]],time*Math.min(c.current,3),'#efbf36',15);out+=particlePath([[315,221],[315,260],[55,260],[55,244]],time*Math.min(c.current,3),'#efbf36',12);}
 out+=fixedText(112,52,p.switch_closed?'闭合回路':'开关断开')+fixedText(440,216,c.stalled?'负载堵转':'输出轴')+fixedText(115,100,'电枢 R = '+fmt(p.resistance,1)+' Ω')+fixedText(223,299,'稳态模型 · 电感和启动过程未求解');return out;
}
function gear(m,s){
 let out='',a=s.inputAngle*Math.PI/180,b=s.angle*Math.PI/180,z1=m.params.teeth_a,z2=m.params.teeth_b,unit=180/(z1+z2),r1=z1*unit,r2=z2*unit,c1=[300-r2,162],c2=[300+r1,162];
 function wheel(c,r,z,angle,color){const pts=[];for(let i=0;i<z;i++)for(const [phase,depth] of [[-.42,-3],[-.28,4],[.28,4],[.42,-3]]){const t=angle+(i+phase)*Math.PI*2/z;pts.push([c[0]+(r+depth)*Math.cos(t),c[1]+(r+depth)*Math.sin(t)]);}let x=path(pts,`fill="${color}" stroke="#6c8fa6" stroke-width="1.2"`,true);x+=circle(...c,r*.56,'fill="#f0f6f9" fill-opacity=".35" stroke="#7492a8"')+circle(...c,9,'class="metal"');x+=line(c,[c[0]+r*.8*Math.cos(angle),c[1]+r*.8*Math.sin(angle)],'stroke="#f3c46c" stroke-width="4"');return x;}
 out+=wheel(c1,r1,z1,a,'#88b7ce')+wheel(c2,r2,z2,b+Math.PI/z2,'#b2c8b9');if(has(m,'trace'))out+=circle(...c1,r1,'fill="none" stroke="#8bafc3" stroke-dasharray="4 5"')+circle(...c2,r2,'fill="none" stroke="#8bafc3" stroke-dasharray="4 5"');return out+fixedText(44,299,'n₂ = − n₁ × Z₁ / Z₂ · 齿形为教学轮廓');
}
function pump(m,s){
 const a=s.angle*Math.PI/180;let out='';
 if(Q('#cutaway').checked)out+=path([[236,91],[377,91],[377,127],[353,127],[353,230],[257,252],[206,225],[198,165],[217,118]],'fill="#a5cad8" fill-opacity=".15" stroke="#7299b0" stroke-width="2"',true);
 out+=path([[43,161],[215,161],[215,191],[43,191]],'class="water"',true)+path([[331,100],[331,47],[512,47],[512,79],[363,79],[363,116]],'class="water"',true);
 out+=circle(285,171,64,'fill="#9bbac8" fill-opacity=".12" stroke="#7f9dac"');for(let i=0;i<7;i++){const t=a+i*Math.PI*2/7,pts=[];for(let j=0;j<8;j++){const r=18+j*6,theta=t+j*.085;pts.push([285+r*Math.cos(theta),171+r*Math.sin(theta)]);}out+=path(pts,'stroke="#8eafc1" stroke-width="7" fill="none" stroke-linecap="round"');}out+=circle(285,171,17,'class="metal"');
 if(has(m,'flow')&&Math.abs(s.rpm)>0){out+=particlePath([[43,175],[220,175],[285,171]],time*Math.abs(s.rpm)/600,'#36b6df',13);const route=[];for(let i=0;i<24;i++){const t=i/23,r=15+t*75,theta=t*Math.PI*2;route.push([285+r*Math.cos(theta),171+r*Math.sin(theta)]);}route.push([346,62],[512,62]);out+=path(route,'stroke="#51b2ce" stroke-width="1" fill="none" opacity=".5"')+particlePath(route,time*Math.abs(s.rpm)/600,'#41c0e5',15);}
 return out+fixedText(62,218,'入口')+fixedText(426,100,'出口')+fixedText(151,300,'叶轮和流线为示意；未计算扬程、流量或气蚀');
}
function wave(m,s){
 const p=m.params,visible=has(m,'water'),P={scale:22,origin:[300,235],azimuth:65,elevation:25},pr=(x,y,z)=>iso([x,y,z],P);let out='';
 const length=10,width=5,depth=2;out+=path([pr(-5,-2.5,-depth),pr(5,-2.5,-depth),pr(5,2.5,-depth),pr(-5,2.5,-depth)],'fill="#aad5e3" opacity=".2" stroke="#76a9be"',true);
 const sample=(x,y)=>{const phaseX=(x+5)/10*p.wavelength*2,z=visible?M.waveState(p,phaseX,time,s.drive).height*18:0;return pr(x,y,z);};
 for(let row=0;row<=14;row++){const y=-2.5+row*5/14,pts=[];for(let i=0;i<=60;i++)pts.push(sample(-5+i/6,y));out+=path(pts,'stroke="#4aaed0" stroke-width="1.2" fill="none" opacity=".7"');}
 for(let col=0;col<=30;col++){const x=-5+col/3;out+=path([sample(x,-2.5),sample(x,2.5)],'stroke="#6cc5dc" stroke-width=".9" fill="none" opacity=".5"');}
 if(Q('#cutaway').checked){for(const x of [-5,5])for(const y of [-2.5,2.5])out+=line(pr(x,y,-depth),pr(x,y,1),'class="wire"');out+=path([pr(-5,-2.5,1),pr(5,-2.5,1),pr(5,2.5,1),pr(-5,2.5,1)],'class="wire"',true);}
 return out+fixedText(40,300,p.interference?'η = A cos(kx) cos(ωt) · 等幅反向波叠加':'η = A cos(kx − ωt) · 水面竖向位移放大显示');
}
function assembly(m,s){
 const parts=Object.values(s.assembly),points=parts.flatMap(p=>p.vertices),P=fitProjection(points,600,330,{pad:38,elevation:30,azimuth:48}),palette={steel:['#c4d2dc','#8da7b9','#b2c6d3'],teal:['#99d0c9','#568f93','#75b3af'],amber:['#f2c98f','#bd8957','#d9aa70'],blue:['#9cc7e3','#6390b2','#7eabca']},faces=[];
 for(const part of parts)part.faces.forEach((f,i)=>{const vertices=f.map(j=>part.vertices[j]),center=vertices[0].map((_,axis)=>vertices.reduce((sum,v)=>sum+v[axis],0)/vertices.length);faces.push({depth:depthOf(center,P),svg:path(vertices.map(v=>iso(v,P)),`fill="${palette[part.color][i%3]}" stroke="#6e8c9d" stroke-width=".8" stroke-linejoin="round"`,true)});});
 let guides='';for(const part of parts){if(part.joint!=='prismatic')continue;const axis='xyz'.indexOf(m.params.parts.find(p=>p.id===part.id).axis),anchor=part.position.map((v,i)=>v-part.rotation[i][axis]*part.value);guides+=line(iso(anchor,P),iso(part.position,P),'stroke="#9bb1c1" stroke-width="7" stroke-linecap="round"')+circle(...iso(anchor,P),4,'fill="#ccdce5" stroke="#849cab"');}
 let out=guides+faces.sort((a,b)=>a.depth-b.depth).map(f=>f.svg).join('');
 if(has(m,'trace')){const traces=Array.from({length:8},(_,i)=>M.assemblyState(m.params.parts,time-i*.04));for(const part of parts){if(part.joint==='fixed')continue;out+=path(traces.map(p=>iso(p[part.id].center,P)),'stroke="#c69348" stroke-dasharray="2 3" stroke-width="1.3" fill="none"');}}
 if(Q('#cutaway').checked)for(const part of parts){const p=iso(part.position,P);out+=circle(...p,3.5,'fill="#f3d493" stroke="#99794a"')+fixedText(p[0]+5,p[1]-5,part.id);}
 return out;
}
const drawings={'four-stroke':engine,jet,motor,'gear-pair':gear,pump,wave,assembly};
const notes={assembly:'用盒体/圆柱、固定/转动/移动关节组合三维运动树。驱动为给定正弦运动，不求解闭环、碰撞、逆运动学、受力或刚体动力学。', 'four-stroke':'连杆长度保持不变；各缸按均匀循环相位演示，不代表具体车型点火顺序。火焰与气流表示阶段，没有温压计算。',jet:'压气机和涡轮单轴同步；流线、火焰和尾流为定性示意，无推力、压比或温度解。',motor:'V = RI + Kω；K I = bω + T负载。b = 0.0002 N·m·s；参数变化直接求稳态，没有启动瞬态。','gear-pair':'输入与输出反向。齿数影响传动比，图形为简化教学轮廓，未做齿形接触或制造校核。',pump:'轴速可由前级传入；流线为示意。流体没有反向施加负载，不能用于选泵。',wave:'ω² = g k tanh(kh)，小振幅、无黏、无反射边界。水面竖向放大；泵关联波幅为教学映射。'};
const labels={cylinders:'气缸数',rpm:'设定转速 / rpm',crank_mm:'曲柄半径 / mm',rod_ratio:'连杆 / 曲柄',voltage:'电源电压 / V',resistance:'电枢电阻 / Ω',constant:'电机常数 / SI',load:'负载转矩 / N·m',switch_closed:'电路开关',throttle:'油门',teeth_a:'输入齿数',teeth_b:'输出齿数',amplitude:'波幅 / m',wavelength:'波长 / m',depth:'水深 / m',interference:'反向波干涉'};
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function download(name,data,type){const url=URL.createObjectURL(new Blob([data],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);}
function configure(next){
 try{const valid=M.validateScene(next,sceneSchema);scene=valid;time=0;angles={};Q('#errors').textContent='';build();render();refreshInspector();}catch(e){Q('#errors').textContent=e.message+' 原场景保留。';}
}
function build(){
 structures.clear();selectedParts.clear();inspecting=null;
 Q('#title').textContent=scene.title;document.title=scene.title+' · Anatomy';Q('#description').textContent=scene.description;Q('#scene-editor').value=JSON.stringify(scene,null,2);Q('#unfulfilled').textContent=scene.unfulfilled.length?'尚未实现：'+scene.unfulfilled.join('；'):'';
 const grid=Q('#grid'),controls=Q('#controls'),connections=Q('#connections');grid.replaceChildren();controls.replaceChildren();connections.replaceChildren();grid.classList.toggle('single',scene.modules.length===1);
 if(!scene.links.length)connections.append(node('span','独立实验 · 共享时间轴'));
 connections.append(node('span','空间流动为教学示意 · 不求解CFD温压场','note'));
 for(const link of scene.links){const from=scene.modules.find(m=>m.id===link.from),to=scene.modules.find(m=>m.id===link.to);connections.append(node('span',from.label+' → '+to.label+' · '+(link.kind==='shaft'?'轴速 × '+link.ratio:'波幅映射 × '+link.ratio)));}
 for(const m of scene.modules){const spec=sceneSchema.types[m.type],card=node('section',undefined,'module');card.dataset.id=m.id;const head=node('div',undefined,'module-head');head.append(node('h3',m.label),node('span',spec.name,'pill'));const svg=document.createElementNS(NS,'svg');svg.setAttribute('viewBox','0 0 600 330');svg.setAttribute('role','img');svg.setAttribute('aria-label',m.label+' 动态教学剖视');svg.classList.add('drawing');card.append(head,svg,node('div',undefined,'metrics'),node('div',notes[m.type],'module-note'));grid.append(card);
  svg.tabIndex=0;let drag=null;svg.onpointerdown=e=>{if(Q('#render-mode').value!=='3d')return;drag={x:e.clientX,y:e.clientY,az:view3D.azimuth,el:view3D.elevation,moved:false,part:e.target.closest('[data-part]')?.dataset.part};svg.setPointerCapture(e.pointerId);};svg.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.hypot(dx,dy)<3&&!drag.moved)return;drag.moved=true;view3D.azimuth=drag.az+dx*.4;view3D.elevation=Math.max(-65,Math.min(80,drag.el+dy*.3));render();};svg.onpointerup=e=>{if(!drag)return;if(!drag.moved&&drag.part){inspecting=m.id;selectedParts.set(m.id,drag.part);}drag=null;svg.releasePointerCapture(e.pointerId);render();refreshInspector();};svg.onpointercancel=()=>drag=null;
  svg.onwheel=e=>{if(Q('#render-mode').value!=='3d'||!e.ctrlKey)return;e.preventDefault();view3D.zoom=Math.max(.5,Math.min(2,view3D.zoom*(e.deltaY>0?.92:1.08)));render();};
  svg.onkeydown=e=>{if(Q('#render-mode').value!=='3d')return;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();e.stopPropagation();view3D.azimuth+=e.key==='ArrowRight'?8:e.key==='ArrowLeft'?-8:0;view3D.elevation=Math.max(-65,Math.min(80,view3D.elevation+(e.key==='ArrowUp'?5:e.key==='ArrowDown'?-5:0)));render();}};
  const box=node('details');box.className='component-controls';box.open=m===scene.modules[0];box.append(node('summary',m.label));for(const [key,rule] of Object.entries(spec.params)){
   if(rule.kind==='parts'){box.append(node('p',m.params.parts.length+' 个基础零件；在下方场景 JSON 编辑形状、尺寸、父子关节与驱动。','note'));continue;}
   const label=node('label',undefined,'field'),caption=node('span',labels[key]||key),value=node('b'),input=document.createElement(rule.enum?'select':'input');input.dataset.module=m.id;input.dataset.param=key;input.setAttribute('aria-label',m.label+' '+labels[key]);
   if(rule.enum){for(const v of rule.enum){const o=new Option(typeof v==='boolean'?(v?'开启':'关闭'):String(v),String(v));input.add(o);}input.value=String(m.params[key]);}
   else{input.type='range';input.min=rule.min;input.max=rule.max;input.step=rule.integer||key==='rpm'||key==='crank_mm'?'1':key==='constant'||key==='load'||key==='amplitude'?'0.001':'0.01';input.value=m.params[key];}
   if(scene.links.some(l=>l.to===m.id&&l.kind==='shaft')&&key==='rpm'){input.disabled=true;input.title='由前级轴速连接控制';caption.append(node('small',' · 前级驱动'));}
   const valueText=v=>typeof v==='boolean'?(v?'开启':'关闭'):String(v);value.textContent=valueText(m.params[key]);caption.append(value);label.append(caption,input);box.append(label);
   input.oninput=()=>{const n=structuredClone(scene),item=n.modules.find(x=>x.id===m.id),v=rule.enum?(rule.enum[0]===true?(input.value==='true'):Number(input.value)):Number(input.value);item.params[key]=v;try{scene=M.validateScene(n,sceneSchema);value.textContent=valueText(v);Q('#scene-editor').value=JSON.stringify(scene,null,2);Q('#errors').textContent='';render();refreshInspector();}catch(e){input.value=scene.modules.find(x=>x.id===m.id).params[key];Q('#errors').textContent=e.message;}};
  }
  const effectNames={airflow:'气流',flame:'火焰',spark:'电火花',current:'电流',field:'磁场',trace:'运动轨迹',flow:'水流',water:'水面波动',coolant:'冷却水套流动'};
  for(const effect of spec.effects){const label=node('label',undefined,'check'),input=document.createElement('input');input.type='checkbox';input.checked=m.effects.includes(effect);input.setAttribute('aria-label',m.label+' '+effectNames[effect]);label.append(input,node('span',effectNames[effect]));input.onchange=()=>{const item=scene.modules.find(x=>x.id===m.id);item.effects=input.checked?[...item.effects,effect]:item.effects.filter(x=>x!==effect);Q('#scene-editor').value=JSON.stringify(scene,null,2);render();refreshInspector();};box.append(label);}
  controls.append(box);
 }
 Q('#source').textContent='上游固定提交 '+provenance.commit;Q('#license').textContent=licenseText;
 const observer=new IntersectionObserver(rows=>{for(const row of rows){const id=row.target.parentElement.dataset.id;if(row.isIntersecting)shown.add(id);else shown.delete(id);}last=null;});if(window.studioObserver)window.studioObserver.disconnect();window.studioObserver=observer;for(const el of grid.querySelectorAll('.drawing'))observer.observe(el);
}
function metrics(m,s){const p=m.params;if(m.type==='assembly')return [['基础零件',String(p.parts.length)],['活动关节',String(p.parts.filter(x=>x.joint!=='fixed').length)],['模型','运动树 · 无动力学']];if(m.type==='four-stroke')return [['曲轴',fmt(s.rpm)+' rpm'],['行程',fmt(p.crank_mm*2)+' mm'],['一缸阶段',['进气','压缩','做功','排气'][s.cylinders[0].stage]],['一缸循环',fmt(s.cylinders[0].phase,0)+'°']];if(m.type==='jet')return [['单轴转速',fmt(s.rpm,0)+' rpm'],['油门',fmt(p.throttle*100,0)+'%'],['热流 / 推力','未求解']];if(m.type==='motor'){const c=s.motor;return [['转速',fmt(c.rpm)+' rpm'],['电流',fmt(c.current,3)+' A'],['反电势',fmt(c.backEmf,2)+' V'],['电功率',fmt(c.inputPower,2)+' W']];}if(m.type==='gear-pair')return [['输入',fmt(s.inputRpm)+' rpm'],['输出',fmt(s.rpm)+' rpm'],['齿数',p.teeth_a+' : '+p.teeth_b]];if(m.type==='pump')return [['轴速',fmt(s.rpm)+' rpm'],['液压负载','未反馈']];return [['频率',fmt(s.wave.frequency,3)+' Hz'],['相速度',fmt(s.wave.phaseSpeed,3)+' m/s'],['当前波幅',fmt(s.wave.amplitude*1000,1)+' mm']];}
function render(force=true){
 const states=M.sceneState(scene,time,angles);for(const m of scene.modules){const card=[...Q('#grid').children].find(c=>c.dataset.id===m.id),s=states[m.id];if(force||shown.has(m.id)){if(Q('#render-mode').value==='3d'){const result=Structure3D.structureView(m,s,time,{...view3D,effects:Q('#effects').checked,shell:Q('#cutaway').checked?view3D.shell:'hidden',selected:selectedParts.get(m.id)},M);structures.set(m.id,result);card.querySelector('svg').innerHTML=result.svg;}else card.querySelector('svg').innerHTML=drawings[m.type](m,s);}const metricsNode=card.querySelector('.metrics');metricsNode.replaceChildren();for(const [label,value] of metrics(m,s)){const item=node('div',undefined,'metric');item.append(node('small',label),node('b',value));metricsNode.append(item);}}
 Q('#time-label').textContent=fmt(time,2);Q('#timeline').value=Math.min(10,time);Q('#scale-label').textContent=fmt(Q('#scale').value,2)+'×';Q('#play').textContent=playing?'暂停':'播放';Q('#status').textContent=playing?'运行中 · '+fmt(Q('#scale').value,2)+'× 时间；高转速可降低倍率观察。':'已暂停 · 可以拖动时间或单步。';
 window.anatomyStudioState={scene:structuredClone(scene),states,time,playing,frames:++frames,view3D:structuredClone(view3D),renderMode:Q('#render-mode').value,structures:Object.fromEntries([...structures].map(([k,v])=>[k,{parts:v.parts,stats:v.stats,camera:v.camera,effects:v.effects}]))};
}
function refreshInspector(){const moduleSelect=Q('#inspect-module'),partSelect=Q('#inspect-part');moduleSelect.replaceChildren();for(const m of scene.modules)moduleSelect.add(new Option(m.label,m.id));if(!scene.modules.some(m=>m.id===inspecting))inspecting=scene.modules[0].id;moduleSelect.value=inspecting;const parts=structures.get(inspecting)?.parts||[];partSelect.replaceChildren(new Option('全部零件',''));for(const p of parts)partSelect.add(new Option(p.label,p.id));partSelect.value=selectedParts.get(inspecting)||'';const part=parts.find(p=>p.id===partSelect.value);Q('#part-description').textContent=part?part.label+'：'+part.note:'选取重要零件查看用途。可以直接点击图中的零件；外壳剖切只影响外壳层，流体为定性效果。';}
Q('#inspect-module').onchange=()=>{inspecting=Q('#inspect-module').value;refreshInspector();};Q('#inspect-part').onchange=()=>{selectedParts.set(inspecting,Q('#inspect-part').value);render();refreshInspector();};
Q('#render-mode').onchange=()=>{render();refreshInspector();};Q('#shell-mode').onchange=()=>{view3D.shell=Q('#shell-mode').value;render();};Q('#cut-depth').oninput=()=>{view3D.cut=Number(Q('#cut-depth').value);render();};Q('#explode-3d').oninput=()=>{view3D.explode=Number(Q('#explode-3d').value);render();};Q('#labels-3d').onchange=()=>{view3D.labels=Q('#labels-3d').checked;render();};Q('#zoom-3d').oninput=()=>{view3D.zoom=Number(Q('#zoom-3d').value);render();};Q('#view-reset').onclick=()=>{view3D.azimuth=38;view3D.elevation=25;view3D.zoom=1;selectedParts.clear();render();refreshInspector();};
for(const name of ['moving','fixed','fluid'])Q('#layer-'+name).onchange=()=>{view3D.layers[name]=Q('#layer-'+name).checked;render();};
function advance(dt){const states=M.sceneState(scene,time,angles);for(const m of scene.modules){if(scene.links.some(l=>l.to===m.id&&l.kind==='shaft'))continue;const s=states[m.id];angles[m.id]=(angles[m.id]??s.inputAngle)+s.inputRpm*dt*6;}time+=dt;}
Q('#play').onclick=()=>{playing=!playing;last=null;render();};Q('#step').onclick=()=>{playing=false;advance(.01);render();};Q('#reset').onclick=()=>{time=0;angles={};render();};Q('#scale').oninput=()=>render();Q('#effects').onchange=()=>render();Q('#cutaway').onchange=()=>render();Q('#timeline').oninput=()=>{playing=false;time=Number(Q('#timeline').value);angles={};render();};
Q('#theme').onclick=()=>document.body.classList.toggle('dark');Q('#apply').onclick=()=>{try{configure(JSON.parse(Q('#scene-editor').value));}catch(e){Q('#errors').textContent='JSON 语法无效。原场景保留。';}};
for(const [id,p] of Object.entries(studioPresets))Q('#preset').add(new Option(p.title,id));Q('#preset').onchange=()=>{if(studioPresets[Q('#preset').value])configure(studioPresets[Q('#preset').value]);};
Q('#schema').onclick=()=>{Q('#schema-text').hidden=!Q('#schema-text').hidden;Q('#schema-text').textContent=JSON.stringify(sceneSchema,null,2);};
Q('#save-json').onclick=()=>download('jarvis-scene.json',JSON.stringify(scene,null,2),'application/json');
Q('#save-html').onclick=()=>{render();const clone=document.documentElement.cloneNode(true);clone.querySelector('#scene-data').textContent=JSON.stringify(scene).replaceAll('<','\\u003c');download('jarvis-anatomy-studio.html','<!doctype html>\n'+clone.outerHTML,'text/html');};
Q('#save-svg').onclick=()=>{render();const out=document.createElementNS(NS,'svg'),n=scene.modules.length;out.setAttribute('xmlns',NS);out.setAttribute('viewBox',`0 0 900 ${n*540+80}`);out.setAttribute('width','900');out.setAttribute('height',n*540+80);const style=document.createElementNS(NS,'style');style.textContent=Q('#studio-style').textContent;out.append(style);const bg=document.createElementNS(NS,'rect');bg.setAttribute('width','100%');bg.setAttribute('height','100%');bg.setAttribute('fill','#fff');out.append(bg);const desc=document.createElementNS(NS,'desc');desc.textContent='Jarvis Anatomy teaching illustration · '+provenance.repository+' @ '+provenance.commit+'\n'+licenseText+'\n'+scene.description;out.append(desc);scene.modules.forEach((m,i)=>{const label=document.createElementNS(NS,'text');label.setAttribute('x','30');label.setAttribute('y',String(40+i*540));label.textContent=m.label;label.setAttribute('font-size','22');out.append(label);const copy=[...Q('#grid').children].find(c=>c.dataset.id===m.id).querySelector('svg').cloneNode(true);copy.setAttribute('x','0');copy.setAttribute('y',String(50+i*540));copy.setAttribute('width','900');copy.setAttribute('height','495');out.append(copy);});download('jarvis-anatomy-studio.svg',out.outerHTML,'image/svg+xml');};
document.addEventListener('visibilitychange',()=>last=null);matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',e=>{if(e.matches){playing=false;render();}});
document.addEventListener('keydown',e=>{if(e.target.matches('input,textarea,select,button,a'))return;if(e.code==='Space'){e.preventDefault();playing=!playing;last=null;render();}if(e.key==='ArrowRight'){e.preventDefault();playing=false;advance(.01);render();}});
function tick(now){if(last!==null&&playing&&!document.hidden&&now-lastPaint>=1000/Number(Q('#frame-rate').value)){advance(Math.min(now-last,.15*1000)/1000*Number(Q('#scale').value));render(false);lastPaint=now;last=now;}if(last===null||!playing||document.hidden)last=now;requestAnimationFrame(tick);}
build();render();refreshInspector();requestAnimationFrame(tick);window.anatomyStudioModel=M;
})();
