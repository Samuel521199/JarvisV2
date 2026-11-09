// Optional native window adapter. Business work remains in the shared Host APIs.
document.documentElement.classList.add('native-presence');
const robotSurface=location.pathname==='/companion/native-robot';
if(robotSurface)document.documentElement.classList.add('native-robot');
const invoke=(command,args={})=>window.__TAURI_INTERNALS__.invoke(command,args);
let queued=false,last='',pending=null,sending=false,dragged=false,pointer=null,reported=false;
async function flush(){
 if(sending||!pending||pending.value===last)return;
 const update=pending;pending=null;sending=true;
 try{await invoke('presence_regions',{rects:update.rects});last=update.value;delete document.documentElement.dataset.nativeError;}
 catch(error){
  document.documentElement.dataset.nativeError='region';
  if(!reported){reported=true;const notice=document.getElementById('error');notice.hidden=false;notice.textContent='原生命中区域未就绪：'+String(error).replace(/[A-Za-z0-9_-]{32,}/g,'[redacted]').slice(0,220);}
 }
 finally{sending=false;if(pending&&pending.value!==last)flush();}
}
function layout(){
 queued=false;const rects=[];
 for(const node of document.querySelectorAll(robotSurface?'.robot':'.edge-rail>aside,.task-dock,#card,#project-dialog,#mail-dialog,dialog[open],#error')){
  if(node.hidden||!node.getClientRects().length)continue;
  const style=getComputedStyle(node);if(style.visibility==='hidden'||style.display==='none')continue;
  let box=node.getBoundingClientRect(),x=Math.max(0,box.left),y=Math.max(0,box.top),right=Math.min(innerWidth,box.right),bottom=Math.min(innerHeight,box.bottom);
  if(node.classList.contains('task-dock')){const clip=node.parentElement.getBoundingClientRect();y=Math.max(y,clip.top);bottom=Math.min(bottom,clip.bottom);}
  if(right>x&&bottom>y)rects.push({x,y,width:right-x,height:bottom-y,rounded:robotSurface});
 }
 const value=JSON.stringify(rects);if(!rects.length||value===last)return;
 pending={rects,value};flush();
}
function schedule(){if(!queued){queued=true;requestAnimationFrame(layout);}}
const size=new ResizeObserver(schedule),mutations=new MutationObserver(()=>{observe();schedule();});
function observe(){for(const node of document.querySelectorAll('.companion,.edge-rail,aside,#card,#project-dialog,#mail-dialog,dialog,#error'))size.observe(node);}
observe();mutations.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden','class','open','style']});
document.addEventListener('transitionend',schedule);document.addEventListener('animationend',schedule);document.addEventListener('scroll',schedule,true);window.addEventListener('resize',schedule);
const robot=document.getElementById('robot');
if(robotSurface){
robot.addEventListener('pointerdown',event=>{if(event.button===0){dragged=false;pointer=[event.screenX,event.screenY];}});
document.addEventListener('pointermove',event=>{if(pointer&&!dragged&&Math.hypot(event.screenX-pointer[0],event.screenY-pointer[1])>5){dragged=true;pointer=null;invoke('presence_drag').catch(()=>{});}});
document.addEventListener('pointerup',()=>pointer=null);
robot.addEventListener('click',event=>{if(dragged){event.stopImmediatePropagation();event.preventDefault();dragged=false;}},true);
robot.onclick=()=>invoke('presence_toggle').catch(()=>{});
}else{
document.getElementById('open-full').addEventListener('click',event=>{event.stopImmediatePropagation();invoke('presence_workbench').catch(()=>{});},true);
window.addEventListener('jarvis:native:toggle-chat',()=>robot.onclick?.());
const dot=document.getElementById('presence-dot');let previous='';
const status=new MutationObserver(()=>{const next=dot.dataset.state||'idle';if(next===previous)return;previous=next;invoke('presence_status',{status:next}).catch(()=>{});});
status.observe(dot,{attributes:true,attributeFilter:['data-state']});
window.addEventListener('pagehide',()=>status.disconnect());
}
window.addEventListener('pagehide',()=>{size.disconnect();mutations.disconnect();});schedule();
