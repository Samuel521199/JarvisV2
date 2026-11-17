// Shared presentation events and a draft barrier within one browser/WebView profile.
import {post} from './ui.js';
const channel=new BroadcastChannel('jarvis.workspace.v1'),prefix='jarvis.workspace.editor:',identity=crypto.randomUUID();
let editor=null,stopEditor=null;
const held=new Map(),pending=new Map(),released=new Set();
export function workspaceChanged(){channel.postMessage({type:'changed'});window.dispatchEvent(new Event('jarvis:workspace-changed'));}
export function selectWorkspaceChat(id){if(!/^chat-[a-f0-9]{32}$/.test(id||''))return;try{localStorage.setItem('jarvis.companion.chat.v1',id);}catch{}channel.postMessage({type:'selection',id});}
async function prepare(request){
 if(!editor)return;
 try{const release=await editor(request.ids);if(released.has(request.id)){release();return;}const timer=setTimeout(()=>checkHeld(request.id),15000);held.set(request.id,{release,timer});channel.postMessage({type:'prepared',id:request.id,editor:identity});}
 catch(error){channel.postMessage({type:'prepared',id:request.id,editor:identity,error:error.message});}
}
async function checkHeld(id){const item=held.get(id);if(!item)return;const state=await navigator.locks.query();if(state.held.some(x=>x.name==='jarvis.workspace.change'))item.timer=setTimeout(()=>checkHeld(id),15000);else releaseHeld(id);}
function releaseHeld(id){const item=held.get(id);if(item){clearTimeout(item.timer);held.delete(id);item.release();}}
channel.onmessage=event=>{
 const m=event.data;if(!m||typeof m!=='object')return;
 if(m.type==='changed')window.dispatchEvent(new Event('jarvis:workspace-changed'));
 if(m.type==='selection'&&/^chat-[a-f0-9]{32}$/.test(m.id||''))window.dispatchEvent(new CustomEvent('jarvis:workspace-selection',{detail:m.id}));
 if(m.type==='prepare'&&Array.isArray(m.targets)&&m.targets.includes(identity)&&Array.isArray(m.ids)&&m.ids.length<=500&&m.ids.every(id=>/^chat-[a-f0-9]{32}$/.test(id))&&typeof m.id==='string')void prepare(m);
 if(m.type==='release'&&typeof m.id==='string'){released.add(m.id);if(released.size>256)released.delete(released.values().next().value);releaseHeld(m.id);}
 if(m.type==='prepared')pending.get(m.id)?.(m);
};
export function registerWorkspaceEditor(callback){
 editor=callback;
 if(navigator.locks)void navigator.locks.request(prefix+identity,()=>new Promise(resolve=>{stopEditor=resolve;}));
 window.addEventListener('pagehide',()=>{for(const id of held.keys())releaseHeld(id);stopEditor?.();},{once:true});
}
export async function workspaceMutation(ids,action){
 if(!navigator.locks)throw Error('当前浏览器无法核对其他视图的草稿，请在原会话内完成保存后整理。');
 return navigator.locks.request('jarvis.workspace.change',async()=>{
  const state=await navigator.locks.query(),targets=state.held.filter(x=>x.name.startsWith(prefix)).map(x=>x.name.slice(prefix.length)),id=crypto.randomUUID();let localRelease;
  try{
   if(targets.includes(identity)&&editor)localRelease=await editor(ids);
   const remote=targets.filter(x=>x!==identity);
   if(remote.length)await new Promise((resolve,reject)=>{
    const remaining=new Set(remote),timer=setTimeout(()=>{pending.delete(id);reject(Error('另一个视图尚未确认草稿已保存，本次整理未执行。'));},5000);
    pending.set(id,m=>{if(!remaining.has(m.editor))return;if(m.error){clearTimeout(timer);pending.delete(id);reject(Error(m.error));return;}remaining.delete(m.editor);if(!remaining.size){clearTimeout(timer);pending.delete(id);resolve();}});
    channel.postMessage({type:'prepare',id,ids,targets:remote});
   });
   const result=await action();workspaceChanged();return result;
  }finally{localRelease?.();channel.postMessage({type:'release',id});}
 });
}
export function updateWorkspaceChat(item,patch){return workspaceMutation([item.id],()=>post('/api/chat/update',{id:item.id,patch}));}
