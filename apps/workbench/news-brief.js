import {el,button,field,input,link,get,post,notice} from './ui.js';

const api='/api/news-brief';
const statusNames={news_unreachable:'所选新闻源均未连通，将在稍后重试',news_failed:'整理失败',network_disabled:'联网已暂停',stopped:'核心已停止',conflict:'设置已更新'};
const dateTime=value=>new Date(value*1000).toLocaleString('zh-CN',{hour12:false});
function toggle(text,checked){
 const box=el('input');box.type='checkbox';box.checked=checked;
 const label=el('label',undefined,'news-option');label.append(box,el('span',text));return {box,label};
}
function issueDetail(body,issue,data,refresh){
 const names=new Map(data.catalog.map(entry=>[entry.id,entry]));
 const top=el('header',undefined,'news-issue-head');
 top.append(el('h3',issue.day+' 每日简报'),el('small',issue.method+' · '+issue.items.length+' 条'));
 if(issue.unread)top.append(button('标为已读',async()=>{await post(api,{action:'read',day:issue.day,edition:issue.edition});await refresh();}));
 body.append(top);
 if(!issue.items.length)body.append(el('p','最近 24 小时没有符合订阅条件的条目。','note'));
 for(const item of issue.items){
  const row=el('article',undefined,'news-story'),source=names.get(item.source);
  const title=link(item.title,item.url);title.target='_blank';title.rel='noopener noreferrer';
  row.append(el('small',source.topic+' · '+source.name+' · '+dateTime(item.published)),title);
  if(item.summary&&item.summary!==item.title)row.append(el('p',item.summary));
  body.append(row);
 }
 const errors=Object.entries(issue.failures);
 if(errors.length)body.append(el('p','本期未能读取：'+errors.map(([id,reason])=>names.get(id).name+' ('+reason+')').join('、'),'note'));
}
export async function newsInbox(body){
 const list=el('div',undefined,'news-inbox');body.replaceChildren(list);
 let current='';
 async function refresh(){
  const data=await get(api);if(!list.isConnected)return;
  list.replaceChildren();const settings=link('订阅设置','/settings#news','action');settings.target='_blank';settings.rel='noopener';
  const info=el('div',undefined,'news-issue-head');info.append(el('strong',data.unread+' 份未读'),settings);list.append(info);
  if(!data.briefs.length){list.append(el('p',data.settings.enabled?'等待首份简报 · '+(statusNames[data.status]||data.status):'在订阅设置中开启每日投递，或立即生成首份简报。','note'));return;}
  const pick=el('select');pick.setAttribute('aria-label','选择简报日期');
  for(const issue of data.briefs)pick.add(new Option(issue.day+(issue.unread?' · 未读':''),issue.day));
  if(data.briefs.some(d=>d.day===current))pick.value=current;
  const content=el('section');function show(){current=pick.value;content.replaceChildren();issueDetail(content,data.briefs.find(d=>d.day===current),data,refresh);}
  pick.onchange=show;list.append(pick,content);show();
 }
 await refresh();
}

export async function newsSettings(body){
 const data=await get(api);if(!body.isConnected)return;
 const p=data.settings,form=el('form',undefined,'news-settings'),panel=el('section',undefined,'card');
 const enabled=toggle('每天投递到右侧信息栏',p.enabled),at=input(p.at),limit=input(String(p.limit));
 at.type='time';at.required=true;limit.type='number';limit.min='1';limit.max='30';limit.required=true;
 panel.append(enabled.label,field('投递时间（本机时间）',at),field('每期条数',limit));
 const groups=el('section',undefined,'card'),selected=new Map(),topics=new Map();
 groups.append(el('h3','新闻栏目与来源'));
 for(const source of data.catalog){
  if(!topics.has(source.topic)){
   const group=el('fieldset'),legend=el('legend',source.topic);group.append(legend);groups.append(group);topics.set(source.topic,group);
  }
  const choice=toggle(source.name+' · '+source.region,p.sources.includes(source.id));
  topics.get(source.topic).append(choice.label);selected.set(source.id,choice.box);
 }
 const filters=el('section',undefined,'card'),exclude=input(p.exclude.join('，')),interest=input(p.interest);
 interest.maxLength=160;filters.append(field('排除词（中英文逗号分隔，按标题和导语匹配）',exclude),field('优先关注（可选，由已启动的本地模型排序）',interest));
 const save=el('button','保存订阅','primary');save.type='submit';
 const status=el('p',statusNames[data.status]||data.status,'note');status.setAttribute('role','status');
 const manual=button('立即生成',async()=>{
  manual.disabled=true;
  try{
   await post(api,{action:'generate'});status.textContent='正在采集…';
   for(let i=0;i<50&&status.isConnected;i++){
    await new Promise(resolve=>setTimeout(resolve,1000));const next=await get(api);
    status.textContent=statusNames[next.status]||next.status;if(next.status!=='正在采集')break;
   }
  }finally{manual.disabled=false;}
 });
 let revision=data.revision;
 form.onsubmit=async event=>{
  event.preventDefault();save.disabled=true;
  try{const sources=[...selected].filter(([,v])=>v.checked).map(([k])=>k);
   if(!sources.length){notice('请至少保留一个新闻栏目。');return;}
   const words=exclude.value.split(/[，,\n]/u).map(w=>w.trim()).filter(Boolean);
   if(words.length>40||words.some(w=>w.length>60)){notice('最多 40 个排除词，每个最多 60 字。');return;}
   await post(api,{action:'save',revision,settings:{enabled:enabled.box.checked,at:at.value,limit:Number(limit.value),sources,exclude:words,interest:interest.value}});
   revision++;status.textContent='订阅已保存';notice('新闻订阅已保存。');
  }catch(error){notice(error.message);}finally{save.disabled=false;}
 };
 form.append(panel,groups,filters,save,manual,status);body.append(form);
 const inbox=el('div');body.append(button('查看最近简报',()=>newsInbox(inbox)),inbox);
}

export function watchNewsBadge(node,label){
 let closed=false;
 async function poll(){
  if(closed||!node.isConnected)return;
  try{const {unread}=await get(api+'/badge');if(closed)return;
   const count=node.querySelector('.count');if(count){count.hidden=!unread;count.textContent=String(unread);}
   node.dataset.unread=String(unread>0);const text=label+(unread?' · '+unread+' 份未读':'');
   node.title=text;node.dataset.tooltip=text;node.setAttribute('aria-label',text);
  }catch{/* Keep the last known count if the local host is restarting. */}
 }
 void poll();const timer=setInterval(poll,30000);
 window.addEventListener('pagehide',()=>{closed=true;clearInterval(timer);},{once:true});
}
