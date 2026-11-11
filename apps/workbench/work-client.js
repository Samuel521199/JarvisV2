import {get,post,details} from './ui.js';

// Both surfaces read the original task projection and use the original commands.
export const workApi={
 state:()=>get('/api/work-status'),
 viewed:item=>post('/api/work-status',{action:'viewed',key:item.attention.key,version:item.attention.version}),
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
