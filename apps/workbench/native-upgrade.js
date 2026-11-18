import {get,notice} from './ui.js';
import {workspaceMutation} from './workspace-events.js';

const buildPattern=/^[a-f0-9]{64}$/;
const stateKey='jarvis.native-presentation.v1:'+location.pathname;
const loaded=document.querySelector('meta[name="jarvis-application"]')?.content;
const route=location.pathname;
const dock=route==='/companion/native';
const robot=route==='/companion/native-robot';
const native=dock||robot||route==='/workbench/native';

export function takePresentationState(){
 if(!native&&route!=='/conversation')return {};
 try{
  const raw=sessionStorage.getItem(stateKey);sessionStorage.removeItem(stateKey);
  const saved=JSON.parse(raw);
  return saved?.schema===1&&Number.isFinite(saved.savedAt)&&Math.abs(Date.now()-saved.savedAt)<300000
   && saved.state&&typeof saved.state==='object' ? saved.state : {};
 }catch{return {};}
}

export function savePresentationState(state){
 sessionStorage.setItem(stateKey,JSON.stringify({schema:1,savedAt:Date.now(),state}));
}

// Each native top-level window keeps its own HWND and stores only view context.
// The dock is the coordinator; the other pages also check when shown or focused.
export function observeNativeUpdate({capture=()=>({})}={}){
 if(!native||!buildPattern.test(loaded||''))return ()=>{};
 const channel=new BroadcastChannel('jarvis.native-presentation.v1');
 let checking=false,closed=false,navigating=false,retryAt=0,noticeBuild='';
 const update=async()=>{
  if(closed||checking||navigating||Date.now()<retryAt)return;
  checking=true;
  let target,shellLocked=false;
  try{
   target=await get('/api/instance');
   if(!target.presentation_ready||!buildPattern.test(target.application_build)||target.application_build===loaded)return;
   const replace=async()=>{
    if(closed)return;
    const current=await get('/api/instance');
    if(!current.presentation_ready||current.application_build!==target.application_build
       ||current.application_epoch!==target.application_epoch)return;
    savePresentationState(await capture());
    if(dock)channel.postMessage({type:'ready',build:current.application_build});
    navigating=true;location.reload();
   };
   if(robot){await replace();return;}
   document.body.inert=true;shellLocked=true;
   await workspaceMutation([],replace,{purpose:'reload',announce:false});
  }catch(error){
   retryAt=Date.now()+15000;
   if(!robot&&target?.presentation_ready&&target.application_build!==noticeBuild){
    noticeBuild=target.application_build;
    notice('新版已就绪。当前操作或草稿还未保存，保留窗口，稍后自动重试。'+error.message);
   }
  }finally{
   if(shellLocked&&!navigating)document.body.inert=false;
   checking=false;
  }
 };
 channel.onmessage=({data})=>{if(data?.type==='ready'&&buildPattern.test(data.build)&&data.build!==loaded)void update();};
 const visible=()=>{if(!document.hidden)void update();};
 window.addEventListener('focus',visible);
 document.addEventListener('visibilitychange',visible);
 window.addEventListener('pagehide',()=>{
  closed=true;channel.close();
  window.removeEventListener('focus',visible);document.removeEventListener('visibilitychange',visible);
 },{once:true});
 return update;
}
