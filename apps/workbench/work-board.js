import {workApi} from './work-client.js';
import {workGroups,relativeTime} from './work-groups.js';
import {openWorkResult} from './work-results.js';
import {el,button,icon,iconButton,get,post,field,input,select,notice} from './ui.js';
import {commitmentForm,commitmentActions} from './commitments.js';
import {openStanding} from './standing-work.js';

const tabs=[['attention','待你处理'],['active','进行中'],['unread','未读成果'],['history','已读历史']];
const states={needs_input:'待你确认',running:'正在进行',queued:'排队中',waiting:'等待条件',external:'等待外部',unknown:'结果待核对',finished:'执行结束',failed:'需要核对',cancelled:'已取消'};
const symbols={running:'refresh',queued:'levels',needs_input:'chat',finished:'star',failed:'tools',unknown:'tools',waiting:'calendar'};

function budgetForm(body,data,refresh){
 const section=el('details',undefined,'work-settings');section.append(el('summary','工作安排与资源设置'));
 const policy=data.policy,form=el('form'),workers=select([['1','1路'],['2','2路'],['3','3路'],['4','4路']],String(policy.max_workers)),memory=input(String(policy.memory_reserve_mib)),cpu=input(String(policy.cpu_ceiling));
 memory.type=cpu.type='number';memory.min='1024';memory.max='32768';memory.step='256';cpu.min='30';cpu.max='90';
 workers.setAttribute('aria-label','通用任务并发上限');
 const save=el('button','保存资源预算');save.type='submit';const error=el('p',undefined,'form-error');
 form.append(field('并行任务',workers),field('保留内存 / MiB',memory),field('CPU暂缓线 / %',cpu),error,save);
 form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{await post('/api/scheduler/policy',{...policy,max_workers:Number(workers.value),memory_reserve_mib:Number(memory.value),cpu_ceiling:Number(cpu.value)});notice('资源预算已保存。');}catch(ex){error.textContent=ex.message;}finally{save.disabled=false;}};
 section.append(form);
 const observer=select([['1','启用结果核对'],['0','关闭结果核对']],data.outcome_observer?.enabled?'1':'0');observer.setAttribute('aria-label','结果核对开关');observer.disabled=typeof data.outcome_observer?.enabled!=='boolean';
 section.append(field('结果核对',observer),button('应用核对设置',async()=>{await post('/api/operations',{action:'outcome_configure',enabled:observer.value==='1'});await refresh(true);notice('结果核对设置已保存。');}));body.append(section);
}

export function mountWorkBoard(body,{settings=false,focusKey=null,focusProject=null,initialTab=null,onOpenChat=null,editPriority=null,resume={}}={}){
 const root=el('section',undefined,'work-board');root.setAttribute('aria-label','按项目整理的当前工作');body.append(root);
 let closed=false,loading=false,pending=false,selected=tabs.some(([key])=>key===initialTab)?initialTab:null,data=null,signature='',
  query=typeof resume.query==='string'?resume.query.trim().toLocaleLowerCase():'',settingsDrawn=false;
 let restoreScroll=Number.isFinite(resume.scroll)?resume.scroll:null;
 const limits=new Map();
 const top=el('div',undefined,'work-board-top'),lead=el('div');lead.append(el('span','工作总览','work-eyebrow'),el('p','先处理需要你确认的事，再看看新成果。','work-lead'));
 const tools=el('div',undefined,'work-board-tools');tools.append(iconButton('plus','新增个人待办',()=>commitmentForm(()=>refresh(true))),iconButton('refresh','刷新工作状态',()=>refresh(true)),iconButton('calendar','持续办事安排',()=>openStanding()));top.append(lead,tools);
 const metrics=el('div',undefined,'work-metrics');metrics.setAttribute('aria-label','当前工作状态');
 const nav=el('div',undefined,'work-tabs');nav.setAttribute('role','tablist');nav.setAttribute('aria-label','工作分类');
 const search=el('input');search.type='search';search.placeholder='查找项目或任务';search.setAttribute('aria-label','查找项目或任务');search.className='work-search';search.value=typeof resume.query==='string'?resume.query:'';
 const list=el('div',undefined,'work-projects');list.setAttribute('role','tabpanel');list.id='work-projects-'+Math.random().toString(36).slice(2);list.tabIndex=-1;
 const status=el('p',undefined,'work-live-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 const footer=el('details',undefined,'work-coverage');footer.append(el('summary','来源与核对状态'));const coverage=el('p',undefined,'note');footer.append(coverage);
 const options=el('div');root.append(top,metrics,nav,search,list,status,footer,options);
 function choose(value,focus=false){selected=value;limits.clear();render();if(focus)nav.querySelector('[aria-selected="true"]')?.focus();}
 search.addEventListener('input',()=>{query=search.value.trim().toLocaleLowerCase();renderList();});
 nav.addEventListener('keydown',e=>{const index=tabs.findIndex(t=>t[0]===selected);if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();choose(e.key==='Home'?tabs[0][0]:e.key==='End'?tabs.at(-1)[0]:tabs[(index+(e.key==='ArrowRight'?1:3))%4][0],true);}});
 function current(){return workGroups((data?.items||[]).filter(i=>!focusKey||i.attention?.key===focusKey));}
 function render(){
  if(!data)return;const projection=current();
  if(!selected)selected=projection.counts.attention?'attention':projection.counts.unread?'unread':projection.counts.active?'active':'history';
  metrics.replaceChildren();
  for(const [state,label,kind] of [['running','正在进行','active'],['queued','排队中','active'],['needs_input','待你确认','attention']]){
   const count=projection.units.filter(u=>u.members.some(i=>i.state===state)).length,b=button('',()=>choose(kind),'work-metric');b.dataset.state=state;
   const glyph=el('span',undefined,'work-metric-icon');glyph.append(icon(symbols[state]));b.append(glyph,el('strong',String(count)),el('span',label));b.setAttribute('aria-label',label+' '+count+' 项');metrics.append(b);
  }
  const focusTab=nav.contains(document.activeElement);
  nav.replaceChildren();for(const [key,label] of tabs){const b=button('',()=>choose(key),'work-tab');b.dataset.bucket=key;b.setAttribute('role','tab');b.setAttribute('aria-label',label+' '+projection.counts[key]);b.setAttribute('aria-selected',String(selected===key));b.setAttribute('aria-controls',list.id);b.tabIndex=selected===key?0:-1;const short=el('span',({attention:'待处理',active:'进行中',unread:'未读',history:'已读'}[key]),'work-short');short.setAttribute('aria-hidden','true');b.append(el('span',label,'work-tab-label'),short,el('span',String(projection.counts[key]),'work-tab-count'));nav.append(b);}
  if(focusTab)nav.querySelector('[aria-selected=true]')?.focus({preventScroll:true});
  renderList();
 }
 function renderList(){
  if(!data)return;const projection=current();const scroll=restoreScroll??list.scrollTop;restoreScroll=null;
  list.replaceChildren();let total=0;
  for(const project of projection.projects){
   if(focusProject&&project.id!==focusProject)continue;
   const units=project.units.filter(u=>u.bucket===selected&&(!query||[project.title,u.title,u.chat_title,u.summary].join(' ').toLocaleLowerCase().includes(query)));if(!units.length)continue;
   const section=el('section',undefined,'work-project');const head=el('div',undefined,'work-project-head'),folder=el('span',undefined,'work-project-icon');folder.append(icon('folder'));
   head.append(folder,el('h3',project.title),el('span',units.length+' 项工作','work-project-total'));section.append(head);
   const limit=limits.get(project.id)||6;
   for(const unit of units.slice(0,limit)){
    const card=el('article',undefined,'work-card');card.dataset.state=unit.state;card.dataset.unread=String(unit.unread);card.dataset.workKey=unit.key;
    const glyph=el('span',undefined,'work-card-symbol');glyph.append(icon(symbols[unit.state]||'calendar'));
    const content=el('div',undefined,'work-card-content'),meta=el('div',undefined,'work-card-meta');meta.append(el('span',states[unit.state]||'工作反馈','work-state'),el('time',relativeTime(unit.updated_at)));
    if(unit.unread){const badge=el('span','未读','work-unread');meta.append(badge);}
    content.append(meta,el('h4',unit.title));
    if(unit.chat_title&&unit.chat_title!==unit.title)content.append(el('p',unit.chat_title,'work-chat-context'));
    if(unit.summary)content.append(el('p',unit.summary,'work-card-preview'));
    if(unit.members.length>1)content.append(el('small','含 '+unit.members.length+' 项进度与反馈','work-members'));
    const actions=el('div',undefined,'work-card-actions');
    actions.append(button(unit.bucket==='attention'?'查看并处理':unit.bucket==='active'?'查看进度':'查看成果',()=>openWorkResult(unit,{onOpenChat,refresh:()=>refresh(true)}),'work-open'));
    if(unit.unread){const read=button('已看完',async()=>{read.disabled=true;try{await workApi.viewedGroup(unit);await refresh(true);}finally{read.disabled=false;}},'work-mark-read');read.setAttribute('aria-label','将“'+unit.title+'”标记已读');actions.append(read);}
    const manages=unit.members.filter(i=>i.source==='commitments'||i.source==='standing'||i.source==='mail_standing'||i.source==='goals'||(i.source==='tasks'&&i.cancelable)||(i.source==='dialogue'&&['running','queued'].includes(i.state)));
    if(manages.length){const more=el('details',undefined,'work-manage');more.append(el('summary','任务操作'));
     for(const item of manages){const row=el('div',undefined,'row');if(manages.length>1)more.append(el('p',item.title,'note'));
      if(item.source==='commitments')commitmentActions(more,row,item,()=>refresh(true));
      else if(item.source==='standing')row.append(button('安排与反馈',()=>openStanding({onChanged:()=>refresh(true)})));
      else if(item.source==='mail_standing')row.append(button('邮件安排',async()=>{const {openMailStanding}=await import('./mail-standing.js');await openMailStanding();}));
      else if(item.source==='goals')row.append(button('打开目标与待答问题',()=>{location.href='/settings#plans';}));
      else {if(item.source==='tasks'&&editPriority)row.append(button('调整优先级',()=>editPriority(item,()=>refresh(true))));row.append(button('停止此'+(item.source==='dialogue'?'回复':'任务'),async()=>{await workApi.cancel(item);await refresh(true);}));}
      more.append(row);
     }content.append(actions,more);
    }else content.append(actions);
    card.append(glyph,content);section.append(card);
   }
   if(units.length>limit)section.append(button('展开其余 '+(units.length-limit)+' 项',()=>{limits.set(project.id,limit+12);renderList();},'work-show-more'));
   list.append(section);total+=units.length;
  }
  if(!total){const empty=el('div',undefined,'work-empty'),symbol=el('span');symbol.append(icon(selected==='unread'?'star':'calendar'));empty.append(symbol,el('strong',query?'没有找到匹配的工作':({attention:'暂时没有需要你处理的事',active:'当前没有进行中的工作',unread:'新成果都看完了',history:'这里会保留已读的工作记录'}[selected])),el('p',query?'试试项目名或任务中的关键词。':selected==='unread'?'有新反馈时，数量和标记会一起更新。':'你可以继续聊天，或添加一个待办。'));list.append(empty);}
  list.scrollTop=scroll;
 }
 async function refresh(force=false){
  if(closed||(!force&&document.hidden))return;if(loading){pending||=force;return;}loading=true;
  try{const next=await workApi.state();if(closed)return;data=next;const key=JSON.stringify([data.items,data.context_ready,data.outcome_observer]);
   if(settings&&!settingsDrawn){budgetForm(options,data,refresh);settingsDrawn=true;}
   coverage.textContent=data.coverage+(data.context_ready===false?'；部分项目关联暂不可用':'')+(data.outcome_observer?.failed_tasks?'；'+data.outcome_observer.failed_tasks+' 项结果核对待重试':'');
   status.textContent='刚刚更新 · 阅读状态与工作台同步';
   if(!force&&(key===signature||list.contains(document.activeElement)))return;signature=key;render();
  }catch(error){status.textContent='连接暂未恢复，保留上次状态：'+error.message;status.dataset.error='true';}
  finally{loading=false;if(pending&&!closed){pending=false;void refresh(true);}}
 }
 const readChanged=()=>refresh(true);window.addEventListener('jarvis:work-viewed',readChanged);
 refresh(true);const timer=setInterval(refresh,5000);
 return()=>{closed=true;clearInterval(timer);window.removeEventListener('jarvis:work-viewed',readChanged);};
}
