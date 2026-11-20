import {el,button,field,input,link,get,post,notice} from './ui.js';

const api='/api/news-brief';
const statusNames={news_unreachable:'所选新闻源均未连通，将在稍后重试',news_failed:'整理失败',network_disabled:'联网已暂停',stopped:'核心已停止',conflict:'设置已更新'};
const dateTime=value=>new Date(value*1000).toLocaleString('zh-CN',{hour12:false});
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
  if(!data.briefs.length){list.append(el('p',data.settings.enabled?'等待首份简报 · '+(statusNames[data.status]||data.status):'在订阅设置中选择栏目并启用每日投递。','note'));return;}
  const pick=el('select');pick.setAttribute('aria-label','选择简报日期');
  for(const issue of data.briefs)pick.add(new Option(issue.day+(issue.unread?' · 未读':''),issue.day));
  if(data.briefs.some(d=>d.day===current))pick.value=current;
  const content=el('section');function show(){current=pick.value;content.replaceChildren();issueDetail(content,data.briefs.find(d=>d.day===current),data,refresh);}
  pick.onchange=show;list.append(pick,content);show();
 }
 await refresh();
}

const publisherBySource={'agencia-brasil':'ebc','dw-world':'dw','abc-au':'abc','un-zh':'un'};
function newsSection(title){
 const block=el('section',undefined,'news-section');block.append(el('h2',title));return block;
}
function choice(label,value,group,kind){
 const check=el('input');check.type='checkbox';check.checked=value;
 const wrap=el('label',undefined,kind);wrap.append(check);group.append(wrap);
 check.setAttribute('aria-label',label);return {wrap,check};
}

export async function newsSettings(body){
 const data=await get(api);if(!body.isConnected)return;
 const p=data.settings,form=el('form',undefined,'news-settings'),sourceBoxes=new Map(),topicBoxes=new Map();
 let enabled=p.enabled,revision=data.revision;
 const delivery=newsSection('每日投递'),controls=el('div',undefined,'news-delivery');
 const at=input(p.at),limit=input(String(p.limit));
 at.type='time';at.required=true;limit.type='number';limit.min='1';limit.max='30';limit.required=true;
 const power=el('button',undefined,'news-power');power.type='button';power.setAttribute('role','switch');power.setAttribute('aria-label','每日投递');
 function showPower(){power.setAttribute('aria-checked',String(enabled));power.textContent=enabled?'已启用':'已停用';}
 showPower();
 controls.append(field('本机时间',at),field('每期条数',limit),power);delivery.append(controls);

 const topics=newsSection('兴趣栏目'),topicList=el('div',undefined,'news-tags');
 topics.append(el('p','可多选，匹配任一项即收录。留空时接收所选频道的全部新闻。','note'),topicList);
 for(const title of data.topics){
  const {wrap,check}=choice(title,p.topics.includes(title),topicList,'news-tag');
  wrap.append(el('span',title));topicBoxes.set(title,check);
 }
 const custom=new Set(p.custom_topics),customList=el('div',undefined,'news-tags');
 const extra=el('details',undefined,'news-extra');extra.append(el('summary','添加自定义兴趣'));
 const customInput=input('','例如：电动车');customInput.maxLength=48;customInput.setAttribute('aria-label','自定义兴趣');
 function renderCustom(){
  customList.replaceChildren();customList.hidden=custom.size===0;
  for(const term of custom){
   const remove=button(term+' ×',()=>{custom.delete(term);renderCustom();},'news-remove');
   remove.setAttribute('aria-label','移除兴趣 '+term);customList.append(remove);
  }
 }
 function addCustom(){
  const term=customInput.value.trim();if(!term)return;
  if(topicBoxes.has(term)){topicBoxes.get(term).checked=true;}
  else{if(custom.size>=20&&!custom.has(term)){notice('最多可添加 20 个自定义兴趣。');return;}custom.add(term);}
  customInput.value='';renderCustom();
 }
 customInput.onkeydown=event=>{if(event.key==='Enter'&&!event.isComposing){event.preventDefault();addCustom();}};
 const editor=el('div',undefined,'news-extra-row');editor.append(customInput,button('添加',addCustom));extra.append(editor);
 renderCustom();topics.append(customList,extra);

 const sources=newsSection('新闻频道'),grid=el('div',undefined,'news-channels');
 const counter=el('small');sources.firstElementChild.append(counter);
 function updateCount(){counter.textContent=[...sourceBoxes.values()].filter(x=>x.checked).length+' / '+data.catalog.length+' 已选';}
 for(const source of data.catalog){
  const {wrap,check}=choice(source.name,p.sources.includes(source.id),grid,'news-channel');
  const image=el('img');image.alt='';image.width=28;image.height=28;
  const brand=publisherBySource[source.id]||source.id.split('-')[0];
  image.src='/brand/news/'+brand+'.png';
  const text=el('span',undefined,'news-channel-copy');text.append(el('strong',source.name),el('small',source.region+' · '+source.topic));
  wrap.prepend(image,text);check.onchange=updateCount;sourceBoxes.set(source.id,check);
 }
 updateCount();sources.append(grid);
 const advanced=el('details',undefined,'news-extra');advanced.append(el('summary','排除词与本地模型排序'));
 const exclude=input(p.exclude.join('，')),interest=input(p.interest);interest.maxLength=160;
 const advancedFields=el('div',undefined,'news-advanced');
 advancedFields.append(field('排除词（用逗号分隔）',exclude),field('本地模型优先排序（可选）',interest));advanced.append(advancedFields);

 const save=el('button','保存并启用','primary');save.type='submit';
 const status=el('span',statusNames[data.status]||data.status,'note');status.setAttribute('role','status');
 const inbox=el('div'),actions=el('div',undefined,'news-actions');
 actions.append(save,button('查看最近简报',()=>newsInbox(inbox)),status);
 async function persist(payload,on){
  power.disabled=save.disabled=true;
  try{
   await post(api,{...payload,revision});revision++;enabled=on;showPower();
   status.textContent=payload.action==='save'?'订阅已保存，每日投递已启用':enabled?'已恢复投递':'已暂停投递';
  }catch(error){notice(error.message);}finally{power.disabled=save.disabled=false;}
 }
 power.onclick=()=>persist({action:'toggle',enabled:!enabled},!enabled);
 form.onsubmit=event=>{
  event.preventDefault();
  const selected=map=>[...map].filter(([,box])=>box.checked).map(([key])=>key);
  const sources=selected(sourceBoxes);
  if(!sources.length){notice('请至少选择一个新闻频道。');return;}
  const words=exclude.value.split(/[，,\n]/u).map(w=>w.trim()).filter(Boolean);
  if(words.length>40||words.some(w=>w.length>60)){notice('最多 40 个排除词，每个最多 60 字。');return;}
  if(customInput.value.trim()){addCustom();if(customInput.value.trim())return;}
  void persist({action:'save',settings:{enabled:true,at:at.value,limit:Number(limit.value),sources,
   topics:selected(topicBoxes),custom_topics:[...custom],exclude:words,interest:interest.value}},true);
 };
 form.append(delivery,topics,sources,advanced,actions);body.append(form,inbox);
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
