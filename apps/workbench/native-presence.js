// Optional native window adapter. Business work remains in the shared Host APIs.
document.documentElement.classList.add('native-presence');
const invoke=(command,args={})=>window.__TAURI_INTERNALS__.invoke(command,args);
let queued=false,last='',dragged=false,pointer=null,reported=false;
function layout(){
 queued=false;const rects=[];
 for(const node of document.querySelectorAll('.companion,.edge-rail>aside,.task-dock,#card,#project-dialog,#mail-dialog,dialog[open],#error')){
  if(node.hidden||!node.getClientRects().length)continue;
  const style=getComputedStyle(node);if(style.visibility==='hidden'||style.display==='none')continue;
  let box=node.getBoundingClientRect(),x=Math.max(0,box.left),y=Math.max(0,box.top),right=Math.min(innerWidth,box.right),bottom=Math.min(innerHeight,box.bottom);
  if(node.classList.contains('task-dock')){const clip=node.parentElement.getBoundingClientRect();y=Math.max(y,clip.top);bottom=Math.min(bottom,clip.bottom);}
  if(right>x&&bottom>y)rects.push({x,y,width:right-x,height:bottom-y,rounded:node.classList.contains('companion')});
 }
 const value=JSON.stringify(rects);if(!rects.length||value===last)return;
 Promise.resolve().then(()=>invoke('presence_regions',{rects})).then(()=>last=value).catch(error=>{
  document.documentElement.dataset.nativeError='region';
  if(!reported){reported=true;const notice=document.getElementById('error');notice.hidden=false;notice.textContent='原生命中区域未就绪：'+String(error).replace(/[A-Za-z0-9_-]{32,}/g,'[redacted]').slice(0,220);}
 });
}
function schedule(){if(!queued){queued=true;requestAnimationFrame(layout);}}
const size=new ResizeObserver(schedule),mutations=new MutationObserver(()=>{observe();schedule();});
function observe(){for(const node of document.querySelectorAll('.companion,.edge-rail,aside,#card,#project-dialog,#mail-dialog,dialog,#error'))size.observe(node);}
observe();mutations.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden','class','open','style']});
document.addEventListener('transitionend',schedule);document.addEventListener('scroll',schedule,true);window.addEventListener('resize',schedule);
const robot=document.getElementById('robot');
robot.addEventListener('pointerdown',event=>{if(event.button===0){dragged=false;pointer=[event.screenX,event.screenY];}});
document.addEventListener('pointermove',event=>{if(pointer&&!dragged&&Math.hypot(event.screenX-pointer[0],event.screenY-pointer[1])>5){dragged=true;pointer=null;invoke('presence_drag').catch(()=>{});}});
document.addEventListener('pointerup',()=>pointer=null);
robot.addEventListener('click',event=>{if(dragged){event.stopImmediatePropagation();event.preventDefault();dragged=false;}},true);
document.getElementById('open-full').addEventListener('click',event=>{event.stopImmediatePropagation();invoke('presence_workbench').catch(()=>{});},true);
window.addEventListener('pagehide',()=>{size.disconnect();mutations.disconnect();});schedule();
