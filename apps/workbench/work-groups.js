// A presentation of original records, shared by the workbench and companion.
export const terminal=new Set(['finished','failed','cancelled']);
const order={needs_input:0,unknown:1,failed:2,running:3,queued:4,external:5,waiting:6,finished:7,cancelled:8};
export function bucket(item){return ['needs_input','unknown'].includes(item.state)?'attention':!terminal.has(item.state)?'active':item.attention?.unread?'unread':'history';}
export function workGroups(items){
 const units=new Map();
 for(const item of items){
  if(item.context?.routine===true&&item.state==='finished')continue;
  const c=item.context||{},project=c.project_id||c.group_id||(c.chat_id||item.chat_id?'$independent':'$other');
  const kind=bucket(item),key=kind+':'+(c.unit_id||item.source+':'+item.id);
  if(!units.has(key))units.set(key,{key,bucket:kind,project_id:project,project_name:c.project_name||(project==='$independent'?'独立会话':'其他工作'),members:[]});
  units.get(key).members.push(item);
 }
 const all=[...units.values()];
 for(const unit of all){
  unit.members.sort((a,b)=>(b.context?.updated_at||b.created||0)-(a.context?.updated_at||a.created||0));
  const top=[...unit.members].sort((a,b)=>(order[a.state]??9)-(order[b.state]??9))[0];
  const latest=unit.members[0];unit.state=top.state;unit.latest=latest;unit.title=latest.title;
  unit.chat_id=latest.context?.chat_id||latest.chat_id;unit.chat_title=latest.context?.chat_title||'';
  if(unit.chat_title&&unit.chat_title!=='新对话'&&(unit.members.length>1||['studio3d','images'].includes(latest.source)))unit.title=unit.chat_title;
  if(unit.key.includes('library:')&&unit.members.length>1)unit.title=unit.project_name.replace(/^模型库 · /,'')+' · 制作进展与成果';
  unit.summary=latest.context?.summary||latest.reason||'';unit.updated_at=latest.context?.updated_at||latest.created||0;
  unit.unread=unit.members.some(i=>i.attention?.unread);
  unit.priority=Math.max(...unit.members.map(i=>Number.isFinite(i.priority)?i.priority:1));
 }
 all.sort((a,b)=>(order[a.state]??9)-(order[b.state]??9)||(['running','queued','needs_input'].includes(a.state)?b.priority-a.priority:0)||b.updated_at-a.updated_at||a.title.localeCompare(b.title,'zh-CN'));
 const projects=new Map();
 for(const unit of all){if(!projects.has(unit.project_id))projects.set(unit.project_id,{id:unit.project_id,title:unit.project_name,units:[]});projects.get(unit.project_id).units.push(unit);}
 return {units:all,projects:[...projects.values()],counts:Object.fromEntries(['attention','active','unread','history'].map(k=>[k,all.filter(u=>u.bucket===k).length])),unread_count:all.filter(u=>u.unread).length};
}
export function relativeTime(value,now=Date.now()/1000){
 if(!value)return '';const seconds=Math.max(0,now-value);
 return seconds<60?'刚刚':seconds<3600?Math.floor(seconds/60)+'分钟前':seconds<86400?Math.floor(seconds/3600)+'小时前':new Date(value*1000).toLocaleDateString('zh-CN',{month:'short',day:'numeric'});
}
