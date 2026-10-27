// First-party software 3D geometry and SVG projection. No fetched code or assets.
export const vadd=(a,b)=>a.map((v,i)=>v+b[i]);
export const vsub=(a,b)=>a.map((v,i)=>v-b[i]);
export const vmul=(a,k)=>a.map(v=>v*k);
export const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
export const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
export const unit=a=>vmul(a,1/(Math.hypot(...a)||1));
const pi=Math.PI,TAU_LOCAL=2*Math.PI;
export function basis(a,b){const w=unit(vsub(b,a)),u=unit(cross(w,Math.abs(w[2])<.8?[0,0,1]:[0,1,0]));return {w,u,v:cross(w,u)};}
export function ringPoint(center,frame,r,angle){return vadd(center,vadd(vmul(frame.u,r*Math.cos(angle)),vmul(frame.v,r*Math.sin(angle))));}
export class MeshScene{
 constructor(){this.faces=[];this.lines=[];this.particles=[];this.parts=[];this.bounds=[];this.effects=[];this.current=null;}
 part(id,label,note,layer='fixed',anchor=[0,0,0],color='#9db7c9',offset=[0,0,0]){const p={id,label,note,layer,anchor:vadd(anchor,offset),color,offset};this.parts.push(p);this.current=p;return p;}
 face(points,color=this.current.color,opacity=1){points=points.map(p=>vadd(p,this.current.offset));this.faces.push({points,color,opacity,part:this.current.id,layer:this.current.layer});if(this.current.layer!=='fluid')this.bounds.push(...points);}
 line(points,color='#7897ad',width=1,opacity=1){points=points.map(p=>vadd(p,this.current.offset));this.lines.push({points,color,width,opacity,part:this.current.id,layer:this.current.layer});}
 particle(position,radius,color,opacity=.8,glow=false){position=vadd(position,this.current.offset);this.particles.push({position,radius,color,opacity,glow,part:this.current.id,layer:this.current.layer});}
 box(center,size,color=this.current.color,opacity=1){const pts=[];for(const z of [-.5,.5])for(const y of [-.5,.5])for(const x of [-.5,.5])pts.push(vadd(center,[x*size[0],y*size[1],z*size[2]]));for(const f of [[0,2,3,1],[4,5,7,6],[0,1,5,4],[2,6,7,3],[0,4,6,2],[1,3,7,5]])this.face(f.map(i=>pts[i]),color,opacity);}
 cylinder(a,b,r,color=this.current.color,segments=16,opacity=1,rEnd=r,caps=true){const f=basis(a,b),rings=[a,b].map((c,i)=>Array.from({length:segments},(_,j)=>ringPoint(c,f,i?rEnd:r,j*2*pi/segments)));for(let j=0;j<segments;j++){const k=(j+1)%segments;this.face([rings[0][j],rings[0][k],rings[1][k],rings[1][j]],color,opacity);}if(caps){this.face([...rings[0]].reverse(),color,opacity);this.face(rings[1],color,opacity);}}
 tube(a,b,outer,inner,color=this.current.color,segments=20,opacity=1,outerEnd=outer,innerEnd=inner){const f=basis(a,b);for(let j=0;j<segments;j++){const t=j*2*pi/segments,q=(j+1)*2*pi/segments;const ao=ringPoint(a,f,outer,t),bo=ringPoint(a,f,outer,q),co=ringPoint(b,f,outerEnd,q),d=ringPoint(b,f,outerEnd,t),ai=ringPoint(a,f,inner,t),bi=ringPoint(a,f,inner,q),ci=ringPoint(b,f,innerEnd,q),di=ringPoint(b,f,innerEnd,t);this.face([ao,bo,co,d],color,opacity);this.face([ai,di,ci,bi],color,opacity);this.face([ao,ai,bi,bo],color,opacity);this.face([d,co,ci,di],color,opacity);}}
 pipe(points,r,color=this.current.color,opacity=.6,segments=8){for(let i=1;i<points.length;i++)this.cylinder(points[i-1],points[i],r,color,segments,opacity,r,false);}
}
export function flowParticles(scene,points,time,{color='#52c9e7',count=24,radius=1.6,speed=1,spread=0}={}){
 const lengths=[0];for(let i=1;i<points.length;i++)lengths.push(lengths.at(-1)+Math.hypot(...vsub(points[i],points[i-1])));const total=lengths.at(-1);if(!total)return;
 for(let i=0;i<count;i++){const d=(((time*speed+i/count)%1)+1)%1*total;let j=1;while(j<lengths.length-1&&lengths[j]<d)j++;const f=(d-lengths[j-1])/(lengths[j]-lengths[j-1]||1),p=vadd(points[j-1],vmul(vsub(points[j],points[j-1]),f)),o=[Math.sin(i*2.39)*spread,Math.cos(i*3.71)*spread,Math.sin(i*5.13)*spread];scene.particle(vadd(p,o),radius*(.7+(i%5)/10),color,.65,true);}
 scene.effects.push({kind:'flow',points,count});
}
export function flameVolume(scene,start,end,radius,time,strength=1){
 if(strength<=0)return;const frame=basis(start,end),length=Math.hypot(...vsub(end,start));
 for(let layer=0;layer<2;layer++)for(let j=0;j<8;j++)for(let k=0;k<5;k++){
  const vertex=(u,t)=>{const r=radius*(layer?.42:.84)*(1-u)*(.8+.2*Math.sin(time*8+u*11+j)),center=vadd(start,vmul(frame.w,length*u));return ringPoint(center,frame,r,t+time*.4+u*.8);},t=j*TAU_LOCAL/8,q=(j+1)*TAU_LOCAL/8,u=k/5,v=(k+1)/5;
  scene.face([vertex(u,t),vertex(u,q),vertex(v,q),vertex(v,t)],layer?'#ffdc76':'#ff6e24',(.22+layer*.18)*strength);
 }
 // A cloud in a 3D tapered volume; billboards are projected only at the last step.
 for(let i=0;i<76;i++){const u=(((i*.6180339+time*.7)%1)+1)%1,t=i*2.39996+time*1.8,r=radius*Math.sqrt((i%13+.5)/13)*(1-u)*(.6+.4*strength),center=vadd(start,vmul(frame.w,length*u)),p=vadd(center,vadd(vmul(frame.u,r*Math.cos(t)),vmul(frame.v,r*Math.sin(t))));scene.particle(p,Math.max(.7,radius*(.14+.18*(1-u))*(.7+.3*Math.sin(i+time*9))),i%4?'#ff8d39':'#ffe08d',(.18+.35*(1-u))*strength,true);}
 scene.effects.push({kind:'flame',start,end,radius,strength});
}
export function clipPolygon(points,cutY){
 const result=[];for(let i=0;i<points.length;i++){const a=points[i],b=points[(i+1)%points.length],inside=a[1]>=cutY,next=b[1]>=cutY;if(inside)result.push(a);if(inside!==next){const t=(cutY-a[1])/(b[1]-a[1]);result.push(vadd(a,vmul(vsub(b,a),t)));}}return result;
}
export function cameraProjection(points,options={}){
 const az=(options.azimuth??38)*pi/180,el=(options.elevation??25)*pi/180;
 const right=[Math.cos(az),-Math.sin(az),0],up=[Math.sin(az)*Math.sin(el),Math.cos(az)*Math.sin(el),Math.cos(el)],toward=unit(cross(right,up));
 const screen=p=>[dot(p,right),-dot(p,up),dot(p,toward)];const projected=points.map(screen),min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];for(const p of projected)for(let i=0;i<3;i++){min[i]=Math.min(min[i],p[i]);max[i]=Math.max(max[i],p[i]);}
 const scale=Math.min(510/Math.max(1,max[0]-min[0]),255/Math.max(1,max[1]-min[1]))*(options.zoom??1),cx=(min[0]+max[0])/2,cy=(min[1]+max[1])/2;
 return {scale,toward,project:p=>{const q=screen(p);return [300+(q[0]-cx)*scale,158+(q[1]-cy)*scale,q[2]];}};
}
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function tint(hex,k){const rgb=hex.match(/[a-f0-9]{2}/gi).map(x=>parseInt(x,16));return '#'+rgb.map(c=>Math.round(Math.min(255,c*k)).toString(16).padStart(2,'0')).join('');}
export function projectStructure(scene,options={}){
 const camera=cameraProjection(scene.bounds.length?scene.bounds:[[0,0,0],[1,1,1]],options),light=unit([-1,-2,3]),view=[],selected=options.selected||'',shell=options.shell||'section',cut=(options.cut??0)*scene.bounds.reduce((a,p)=>Math.max(a,Math.abs(p[1])),1),visible=layer=>options.layers?.[layer]!==false;
 const opacity=(part,base)=>base*(selected&&part!==selected ? .2 : 1),fmt=n=>Number(n.toFixed(2)),coords=pts=>pts.map(p=>p.slice(0,2).map(fmt).join(',')).join(' ');
 let visibleFaces=0,clipped=0;
 for(const face of scene.faces){if(!visible(face.layer)||face.layer==='housing'&&shell==='hidden')continue;let points=face.points;if(face.layer==='housing'&&shell==='section'){points=clipPolygon(points,cut);if(points.length<3){clipped++;continue;}}
  const normal=unit(cross(vsub(points[1],points[0]),vsub(points[2],points[0]))),shade=face.layer==='fluid'?1:.7+.28*Math.abs(dot(normal,light));const pts=points.map(camera.project),depth=pts.reduce((sum,p)=>sum+p[2],0)/pts.length,alpha=opacity(face.part,face.opacity*(face.layer==='housing'&&shell==='transparent' ? .12 : 1));
  view.push({depth,svg:`<polygon data-part="${esc(face.part)}" class="structure-face" points="${coords(pts)}" fill="${tint(face.color,shade)}" fill-opacity="${alpha}" stroke="${face.part===selected?'#eeb253':'#527184'}" stroke-opacity="${face.layer==='fluid'||options.edges===false&&face.part!==selected?0:Math.min(.5,alpha*.6)}" stroke-width="${face.part===selected?1.1:.35}"/>`});visibleFaces++;
  if(face.layer==='housing'&&shell==='section'){
   const edge=[];for(let i=0;i<face.points.length;i++){const a=face.points[i],b=face.points[(i+1)%face.points.length];if((a[1]>=cut)!==(b[1]>=cut)){const t=(cut-a[1])/(b[1]-a[1]);edge.push(camera.project(vadd(a,vmul(vsub(b,a),t))));}}
   if(edge.length===2)view.push({depth:(edge[0][2]+edge[1][2])/2+.3,svg:`<polyline data-part="${esc(face.part)}" class="structure-cut-edge" points="${coords(edge)}" stroke="#e5b46f" stroke-width="1.25" opacity="${opacity(face.part,.85)}" fill="none"/>`});
  }
 }
 for(const line of scene.lines){if(!visible(line.layer))continue;const pts=line.points.map(camera.project);view.push({depth:pts.reduce((s,p)=>s+p[2],0)/pts.length+.2,svg:`<polyline data-part="${esc(line.part)}" points="${coords(pts)}" fill="none" stroke="${line.color}" stroke-width="${line.width}" opacity="${opacity(line.part,line.opacity)}"/>`});}
 for(const p of scene.particles){if(!visible(p.layer))continue;const v=camera.project(p.position),r=Math.max(.6,p.radius*camera.scale);view.push({depth:v[2]+.1,svg:`<circle data-part="${esc(p.part)}" class="structure-particle" cx="${fmt(v[0])}" cy="${fmt(v[1])}" r="${fmt(r)}" fill="${p.color}" fill-opacity="${opacity(p.part,p.opacity)}"/>`});}
 view.sort((a,b)=>a.depth-b.depth);let svg=view.map(v=>v.svg).join('');
 const labels=selected?scene.parts.filter(p=>p.id===selected):scene.parts.filter(p=>p.layer!=='fluid').filter((_,i)=>i%Math.max(1,Math.floor(scene.parts.length/6))===0).slice(0,6);
 if(options.labels!==false)labels.forEach((p,i)=>{if(!visible(p.layer))return;const pos=camera.project(p.anchor),left=pos[0]<300,x=left?8:474,y=24+i*42;svg+=`<path class="structure-leader" d="M${fmt(pos[0])} ${fmt(pos[1])} L${left?105:473} ${y-3}"/><text class="structure-label" x="${x}" y="${y}">${esc(p.label)}</text>`;});
 svg+='<text class="structure-hint" x="12" y="321">拖动旋转 · 滚轮缩放 · 点击零件查看结构</text>';
 return {svg,parts:scene.parts,stats:{faces:scene.faces.length,visibleFaces,clipped,particles:scene.particles.length,vertices:scene.bounds.length},camera:{scale:camera.scale,azimuth:options.azimuth??38,elevation:options.elevation??25},effects:scene.effects};
}
