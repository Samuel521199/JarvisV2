(()=>{'use strict';
const Q=s=>document.querySelector(s),{validatePlanetary,planetaryState,externalProfile,internalSector}=Planetary;
let config=validatePlanetary(initialConfig),inputAngle=0,playing=!matchMedia('(prefers-reduced-motion: reduce)').matches,explode=0,topView=false,showCarrier=true,showPitch=false,visible=true,last=null,lastPaint=0,frameCount=0;
const style=document.createElement('style');style.textContent=ISO_CSS;document.head.prepend(style);document.body.classList.add('iso');document.body.dataset.theme='light';
Q('#source').textContent='上游固定提交：'+provenance.commit;Q('#license').textContent=licenseText;
let profiles,ringCache=null,baseCache=null;
function resetGeometry(){profiles={sun:externalProfile(config.sun_teeth),planet:externalProfile(config.planet_teeth),ring:internalSector(config.ring_teeth)};ringCache=null;baseCache=null;}
function mapPoints(points,x,y,angle){const c=Math.cos(angle),s=Math.sin(angle);return points.map(([u,v])=>[x+u*c-v*s,y+u*s+v*c]);}
const paths={
 'ring-fixed':{title:'齿圈固定：同向减速',note:'输入 S → 输出 C；R 保持静止',text:'太阳轮推动行星轮反向自转，同时带动行星架同向公转。行星架比输入轴慢。',roles:['输入轴','固定件','输出轴']},
 'sun-fixed':{title:'太阳轮固定：同向增速',note:'输入 C → 输出 R；S 保持静止',text:'行星架带着行星轮绕固定太阳轮滚动，内齿圈与行星架同向旋转，转速更高。',roles:['固定件','输出轴','输入轴']},
 'carrier-fixed':{title:'行星架固定：反向传动',note:'输入 S → 输出 R；C 保持静止',text:'行星轮中心固定在机架上，只有自转；太阳轮经行星轮带动内齿圈反向旋转。',roles:['输入轴','输出轴','固定件']}
};
function render(){
 const state=planetaryState(config,inputAngle,Number(Q('#speed').value)),R=state.ring_teeth,extent=R+16;
 const P=fitProjection(boxCorners({x:-extent,y:-extent,w:extent*2,d:extent*2},-27,62+explode*105),900,680,{pad:42,elevation:topView?90:55});
 const parts=[];let serial=0;
 function push(shape,center,type='housing'){parts.push({svg:solidSvg(shape,{className:type,crease:'faint'}),key:depthOf(center,P),serial:serial++});}
 function disk(x,y,r,z,h,type){push(cylinder(x,y,r,z,h,P,24,.3),[x,y,z+h/2],type);}
 const plate={x:-extent+2,y:-extent+2,w:(extent-2)*2,d:(extent-2)*2,r:10};
 const baseKey=JSON.stringify(P);
 if(baseCache?.key===baseKey){parts.push(...baseCache.parts);serial=baseCache.serial;}
 else{
 push(slabOf(plate,-17,6,P,5,.6),[0,0,-14]);
 for(const x of [-extent+15,extent-15])for(const y of [-extent+15,extent-15]){disk(x,y,7,-26,9,'shaft');disk(x,y,3,-10,3,'shaft');}
 disk(0,0,14,-11,12,'shaft');disk(0,0,8,0,24+explode*40,'shaft');
 for(let i=0;i<8;i++){const a=i*Math.PI/4;disk((R+8)*Math.cos(a),(R+8)*Math.sin(a),3,-10,3,'shaft');}
 baseCache={key:baseKey,parts:[...parts],serial};}
 const gearZ=24+explode*40,carrierZ=38+explode*100;
 // Each ring tooth is a real annular sector; never cover the mechanism with a solid disk.
 const ringKey=JSON.stringify([P,state.ringAngle,R]);
 if(ringCache?.key===ringKey){for(const piece of ringCache.parts)parts.push({...piece,serial:serial++});}
 else{const start=parts.length;
 for(let i=0;i<R;i++){const a=state.ringAngle+i*2*Math.PI/R;push(extrude(mapPoints(profiles.ring,0,0,a),24,10,P,{convex:false}),[(R+4)*Math.cos(a),(R+4)*Math.sin(a),29],'ring-gear');}
 ringCache={key:ringKey,parts:parts.slice(start)};}
 const gear=(points,x,y,a,type,teeth)=>{
 push(extrude(mapPoints(points,x,y,a),gearZ,10,P,{convex:false}),[x,y,gearZ+5],type);
 disk(x,y,Math.max(3,teeth*.19),gearZ+10,2,'shaft');
 const markerRadius=teeth*.58;disk(x+markerRadius*Math.cos(a),y+markerRadius*Math.sin(a),1.5,gearZ+12,.5,'marker');
 };
 gear(profiles.sun,0,0,state.sunAngle,'sun',config.sun_teeth);
 for(const planet of state.planets)gear(profiles.planet,planet.x,planet.y,planet.angle,'planet',config.planet_teeth);
 if(showCarrier){
 for(const planet of state.planets){const len=state.orbit,nx=-planet.y/len*3.2,ny=planet.x/len*3.2;
 push(extrude([[nx,ny],[planet.x+nx,planet.y+ny],[planet.x-nx,planet.y-ny],[-nx,-ny]],carrierZ,3,P),[planet.x/2,planet.y/2,carrierZ+1.5],'carrier');
 disk(planet.x,planet.y,5,gearZ+12,Math.max(1,carrierZ-gearZ-12),'shaft');disk(planet.x,planet.y,5.5,carrierZ+3,2,'carrier');disk(planet.x,planet.y,2,carrierZ+5,1.5,'shaft');}
 disk(0,0,7,carrierZ,6,'carrier');disk(0,0,3,carrierZ+6,5,'shaft');}
 parts.sort((a,b)=>a.key-b.key||a.serial-b.serial);
 let svg=parts.map(x=>x.svg).join('');
 if(showPitch){const circle=(x,y,r)=>'<path class="pitch" d="'+ring(x,y,r,gearZ+13,P,90)+'"/>';svg+=circle(0,0,config.sun_teeth)+circle(0,0,R);for(const p of state.planets)svg+=circle(p.x,p.y,config.planet_teeth);}
 Q('#machine').innerHTML=svg;Q('#machine').dataset.parts=parts.length;
 const info=paths[config.mode];Q('#mode-title').textContent=info.title;Q('#path-note').textContent=info.note;Q('#explanation').textContent=info.text;
 for(const key of ['sun','ring','carrier','planet'])Q('#'+key+'-rpm').textContent=state.rates[key].toFixed(2)+' rpm';
 ['sun','ring','carrier'].forEach((key,i)=>Q('#'+key+'-role').textContent=info.roles[i]);
 Q('#ratio').textContent='S / P / R = '+config.sun_teeth+' / '+config.planet_teeth+' / '+R+'；输入转速 / 输出转速 = '+state.ratio.toFixed(4)+'。'+(state.ratio<0?'负号表示输出反向。':'正号表示输入、输出同向。');
 Q('#angle-label').textContent=inputAngle.toFixed(1)+'°';Q('#angle').value=((inputAngle%720)+720)%720;Q('#speed-label').textContent=Q('#speed').value+' rpm';
 Q('#play').textContent=playing?'暂停':'播放';Q('#motion-note').textContent=playing?'运行中 · 输入轴按设定工况运动':'已暂停 · 读数保留设定工况，可逐步观察';Q('#explode-label').textContent=Math.round(explode*100)+'%';
 Q('#view').setAttribute('aria-pressed',String(topView));Q('#carrier').setAttribute('aria-pressed',String(showCarrier));Q('#pitch').setAttribute('aria-pressed',String(showPitch));
 window.anatomyState={...state,inputAngle,playing,explode,topView,showCarrier,parts:parts.length,frameCount:++frameCount};
}
function reconfigure(next){try{config=validatePlanetary(next);inputAngle=0;resetGeometry();Q('#sun-teeth').value=config.sun_teeth;Q('#planet-teeth').value=config.planet_teeth;const preset=config.sun_teeth+','+config.planet_teeth;Q('#preset').value=[...Q('#preset').options].some(x=>x.value===preset)?preset:'custom';Q('#configuration-status').textContent='装配条件通过；已回到零位。';render();}catch(e){Q('#configuration-status').textContent='齿数无效：S 为18–48，P 为18–36；R=S+2P，S+R 须被3整除。原机构保留。';}}
Q('#mode').value=config.mode;Q('#sun-teeth').value=config.sun_teeth;Q('#planet-teeth').value=config.planet_teeth;Q('#preset').value=[...Q('#preset').options].some(x=>x.value===config.sun_teeth+','+config.planet_teeth)?config.sun_teeth+','+config.planet_teeth:'custom';
Q('#mode').onchange=()=>reconfigure({...config,mode:Q('#mode').value});
Q('#preset').onchange=()=>{if(Q('#preset').value==='custom'){Q('#configuration-status').textContent='填写下方齿数并点击应用。';return;}const [sun,planet]=Q('#preset').value.split(',').map(Number);reconfigure({...config,sun_teeth:sun,planet_teeth:planet});};
Q('#apply-teeth').onclick=()=>reconfigure({...config,sun_teeth:Number(Q('#sun-teeth').value),planet_teeth:Number(Q('#planet-teeth').value)});
Q('#angle').oninput=()=>{playing=false;inputAngle=Number(Q('#angle').value);render();};Q('#speed').oninput=render;
Q('#play').onclick=()=>{playing=!playing;last=null;render()};
const step=amount=>{playing=false;inputAngle+=amount;render()};Q('#step').onclick=()=>step(5);Q('#step-back').onclick=()=>step(-5);Q('#reset').onclick=()=>{inputAngle=0;render()};
Q('#explode').oninput=()=>{explode=Number(Q('#explode').value)/100;render()};
Q('#view').onclick=()=>{topView=!topView;showCarrier=!topView;resetGeometry();render()};Q('#carrier').onclick=()=>{showCarrier=!showCarrier;render()};Q('#pitch').onclick=()=>{showPitch=!showPitch;render()};
Q('#theme').onclick=()=>{document.body.dataset.theme=document.body.dataset.theme==='light'?'dark':'light';};
Q('#export').onclick=()=>{const copy=Q('#machine').cloneNode(true);copy.setAttribute('xmlns','http://www.w3.org/2000/svg');copy.classList.add('iso');copy.setAttribute('data-theme','light');const css=document.createElementNS('http://www.w3.org/2000/svg','style');css.textContent=ISO_CSS+'\n'+Q('#planetary-style').textContent+'\n.iso-solid .iso-fill{fill:#9babb4}.iso-solid .iso-top{fill:#b9c7d0}.sun .iso-fill,.sun .iso-top{fill:#eba74d}.planet .iso-fill,.planet .iso-top{fill:#6da8d3}.carrier .iso-fill,.carrier .iso-top{fill:#66b9a4}';copy.prepend(css);const desc=document.createElementNS(copy.namespaceURI,'desc');desc.textContent='Jarvis ideal planetary illustration; Anatomy MIT; '+provenance.repository+' @ '+provenance.commit+'; not manufacturing CAD\n'+licenseText;copy.prepend(desc);const a=document.createElement('a'),url=URL.createObjectURL(new Blob([copy.outerHTML],{type:'image/svg+xml'}));a.href=url;a.download='jarvis-planetary.svg';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.addEventListener('keydown',e=>{if(e.target.matches('input,select,button,a'))return;if(e.code==='Space'){e.preventDefault();playing=!playing;last=null;render()}else if(e.key==='ArrowRight'){e.preventDefault();step(5)}else if(e.key==='ArrowLeft'){e.preventDefault();step(-5)}});
new IntersectionObserver(rows=>{visible=rows[0].isIntersecting;last=null;}).observe(Q('#machine'));
document.addEventListener('visibilitychange',()=>last=null);
matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',e=>{if(e.matches){playing=false;render()}});
function tick(now){if(last!==null&&playing&&visible&&!document.hidden&&now-lastPaint>=50){inputAngle+=Math.min(now-last,150)*Number(Q('#speed').value)*.006;if(Math.abs(inputAngle)>1e7){playing=false;Q('#motion-note').textContent='请回到零位后继续。';}render();lastPaint=now;last=now;}if(last===null||!playing||!visible||document.hidden)last=now;requestAnimationFrame(tick)}
resetGeometry();render();window.anatomyPlanetary=Planetary;requestAnimationFrame(tick);
})();
