import {selectWorkspaceChat,workspaceMutation} from './workspace-events.js';
let full=null;
const bridge=new BroadcastChannel('jarvis.presentation.v1'),requests=new Map();
bridge.onmessage=event=>{const m=event.data;if(m?.type==='result')requests.get(m.id)?.(m);};
export function nativeWorkbenchController(){
 bridge.addEventListener('message',async event=>{const m=event.data;if(m?.type!=='fold'||typeof m.id!=='string'||m.id.length>100)return;
  try{await window.__TAURI_INTERNALS__.invoke('presence_workbench',{action:'hide'});bridge.postMessage({type:'result',id:m.id});}
  catch(error){bridge.postMessage({type:'result',id:m.id,error:String(error)});}
 });
}
async function foldNativeWorkbench(){
 return new Promise((resolve,reject)=>{const id=crypto.randomUUID(),timer=setTimeout(()=>{requests.delete(id);reject(Error('精灵窗口没有确认收回，工作台保持原状。'));},5000);
  requests.set(id,m=>{clearTimeout(timer);requests.delete(id);m.error?reject(Error(m.error)):resolve();});bridge.postMessage({type:'fold',id});
 });
}
const selected=id=>{if(/^chat-[a-f0-9]{32}$/.test(id||''))return id;try{return localStorage.getItem('jarvis.companion.chat.v1')||'';}catch{return '';}};
export async function expandWorkbench(chatId=''){
 if(!window.__TAURI_INTERNALS__){full=window.open('','jarvis-workbench');if(!full)throw Error('工作台窗口被浏览器阻止，请允许本机页面打开工作台。');}
 await workspaceMutation([],async()=>{const id=selected(chatId);selectWorkspaceChat(id);
  if(window.__TAURI_INTERNALS__){await window.__TAURI_INTERNALS__.invoke('presence_workbench',{action:'open',chatId:id||null});return;}
  full.location.href='/#presentation=workbench'+(id?'&chat='+encodeURIComponent(id):'');full.focus();
 });
}
export async function foldWorkbench(chatId=''){
 let id;await workspaceMutation([],async()=>{id=selected(chatId);selectWorkspaceChat(id);});
 if(window.__TAURI_INTERNALS__&&location.pathname==='/workbench/native'){await foldNativeWorkbench();return;}
 if(window.opener&&!window.opener.closed){window.opener.focus();window.close();return;}
 location.assign('/companion'+(id?'#chat='+encodeURIComponent(id):''));
}
