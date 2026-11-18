import {get,post,details} from './ui.js';

const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('jarvis-work-attention'):null,confirmed=new Set();
function remember(value){if(typeof value?.key!=='string'||value.key.length>200||!/^[a-f0-9]{64}$/.test(value.version||''))return;confirmed.add(value.key+':'+value.version);if(confirmed.size>2000)confirmed.delete(confirmed.values().next().value);}
function changed(){window.dispatchEvent(new Event('jarvis:work-viewed'));}
if(channel)channel.onmessage=event=>{
 const values=Array.isArray(event.data?.viewed)?event.data.viewed:[event.data];
 for(const value of values)remember(value);
 changed();
};

// Both surfaces read the original task projection and use the original commands.
export const workApi={
 async state(){const data=await get('/api/work-status');for(const item of data.items)if(item.attention&&confirmed.has(item.attention.key+':'+item.attention.version))item.attention={...item.attention,unread:false};return data;},
 async viewed(item){const result=await post('/api/work-status',{action:'viewed',key:item.attention.key,version:item.attention.version});remember(result);changed();channel?.postMessage({key:result.key,version:result.version});return result;},
 async viewedMany(items){
  const receipts=[...new Map(items.filter(item=>item.attention?.unread).map(item=>{
   const {key,version}=item.attention;
   return [key,{key,version}];
  })).values()];
  if(!receipts.length)return {viewed:[],skipped:0};
  const result=await post('/api/work-status',{action:'viewed_many',receipts});
  for(const receipt of result.viewed)remember(receipt);
  changed();
  channel?.postMessage({viewed:result.viewed});
  return result;
 },
 async viewedGroup(unit){for(const item of unit.members)if(item.attention?.unread)await this.viewed(item);},
 cancel(item){
  if(item.source==='dialogue')return post('/api/chat/cancel',{request_id:item.id});
  if(item.source==='tasks')return post('/api/operations',{action:'task_cancel',id:item.id});
  if(item.source==='standing')return post('/api/standing-work',{action:'cancel',id:item.id,revision:item.revision,request_id:crypto.randomUUID()});
  if(item.source==='mail_standing')return post('/api/mail-standing',{action:'cancel',id:item.id,revision:item.revision,request_id:crypto.randomUUID()});
  throw Error('此来源需到对应模块停止工作。');
 },
 async record(item){
  const value=item.source==='commitments'?await get('/api/commitments/'+encodeURIComponent(item.id)):item.source==='tasks'?await post('/api/operations',{action:'task_detail',id:item.id}):item;
  details('工作记录',value);
  if(item.attention?.unread)await this.viewed(item);
 }
};

export async function readAllWork(control, units, refresh){
 control.disabled=true;
 try{
  const result=await workApi.viewedMany(units.flatMap(unit=>unit.members));
  await refresh();
  if(result.skipped)throw Error('部分提醒已有新状态，仍保留未读。');
 }finally{control.disabled=false;}
}

const receipts=new Set(),observed=new Map();
const observer=new IntersectionObserver(entries=>{
 for(const entry of entries){
  if(document.hidden||!entry.isIntersecting)continue;
  const attention=observed.get(entry.target);if(!attention)continue;
  const key=attention.key+attention.version;receipts.add(key);observer.unobserve(entry.target);observed.delete(entry.target);
  workApi.viewed({attention}).catch(()=>receipts.delete(key));
 }
},{threshold:0.1});
export function watchReply(node,attention){
 for(const previous of observed.keys())if(!previous.isConnected){observer.unobserve(previous);observed.delete(previous);}
 if(!attention?.unread||receipts.has(attention.key+attention.version))return;
 observed.set(node,attention);observer.observe(node);
}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)for(const node of observed.keys()){observer.unobserve(node);observer.observe(node);}});
window.addEventListener('pagehide',()=>{observer.disconnect();observed.clear();});
