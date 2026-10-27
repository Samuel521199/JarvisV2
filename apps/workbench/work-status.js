import {el,button,field,input,select,get,post,modal,closeModal,details,notice} from './ui.js';
import {outcomeView,completionView} from './ui.js';

const priorities=[['0','稍后'],['1','普通'],['2','优先'],['3','紧急']];
function editPriority(item,refresh){
 const body=modal('任务优先级'),form=el('form'),priority=select(priorities,String(item.priority)),importance=select([['0','较低'],['1','普通'],['2','重要'],['3','非常重要']],String(item.importance)),due=input(),reason=input('主人在工作状态中调整'),error=el('p',undefined,'form-error'),save=el('button','保存优先级','primary');
 priority.setAttribute('aria-label','执行优先级');importance.setAttribute('aria-label','重要性');due.type='datetime-local';reason.maxLength=200;reason.required=true;save.type='submit';
 if(item.due_at){const date=new Date(item.due_at*1000);due.value=new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);}
 form.append(el('p',item.title),field('执行优先级',priority),field('重要性',importance),field('期望完成时间（可空）',due),field('安排理由',reason),el('p','影响后续调度，不会强行中断已开始的动作；资源不足时会显示等待原因。','note'),error,save);
 form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{await post('/api/scheduler/priority',{id:item.id,revision:item.revision,priority:Number(priority.value),importance:Number(importance.value),due_at:due.value?new Date(due.value).getTime()/1000:null,reason:reason.value});closeModal();await refresh();notice('任务优先级已保存。');}catch(ex){error.textContent=ex.message;}finally{save.disabled=false;}};body.append(form);
}

export function workStatusView(body,{settings=false}={}){
 let closed=false,loading=false,pendingRefresh=false,signature='',policyDrawn=false,observerSelect=null,observerApply=null,observerDrawn=false;
 const summary=el('div',undefined,'work-summary'),note=el('p',undefined,'note'),list=el('div',undefined,'work-status-list'),config=el('section',undefined,'card'),tools=el('div',undefined,'row');
 summary.setAttribute('aria-live','polite');tools.append(button('刷新工作状态',()=>refresh(true)));body.append(tools,summary,note);
 if(settings){
  body.append(config);
  const observer=select([['1','启用结果核对'],['0','关闭结果核对']],'1');observerSelect=observer;observer.disabled=true;observer.setAttribute('aria-label','结果核对开关');
  observerApply=button('应用结果核对设置',async()=>{await post('/api/operations',{action:'outcome_configure',enabled:observer.value==='1'});await refresh(true);notice('结果核对设置已保存。');});observerApply.disabled=true;tools.append(observer,observerApply);
 }
 body.append(list);
 function policyForm(policy){
  if(policyDrawn)return;policyDrawn=true;
  const form=el('form'),workers=select([['1','1 路'],['2','2 路'],['3','3 路'],['4','4 路']],String(policy.max_workers)),reserve=input(String(policy.memory_reserve_mib)),cpu=input(String(policy.cpu_ceiling)),save=el('button','保存资源预算','primary'),error=el('p',undefined,'form-error');
  workers.setAttribute('aria-label','通用任务并发上限');reserve.type='number';reserve.min='1024';reserve.max='32768';reserve.step='256';cpu.type='number';cpu.min='30';cpu.max='90';save.type='submit';
  form.append(el('h3','聊天优先的资源预算'),field('通用任务并发上限',workers),field('为聊天和系统保留内存（MiB）',reserve),field('CPU 达到此占用后暂缓新任务（%）',cpu),el('p','默认两路。独立聊天池始终保留；有冲突的工具会排队。更高档位需要结合本机响应表现使用，已运行任务不会被强行结束。','note'),error,save);
  form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{policy=await post('/api/scheduler/policy',{...policy,max_workers:Number(workers.value),memory_reserve_mib:Number(reserve.value),cpu_ceiling:Number(cpu.value)});notice('资源预算已保存，将用于后续任务准入。');await refresh(true);}catch(ex){error.textContent=ex.message;}finally{save.disabled=false;}};config.append(form);
 }
 async function refresh(force=false){
  if(closed||(!force&&document.hidden))return;if(loading){pendingRefresh||=force;return;}loading=true;
  try{
   const data=await get('/api/work-status');if(closed)return;if(settings)policyForm(data.policy);if(observerSelect&&!observerDrawn&&typeof data.outcome_observer?.enabled==='boolean'){observerSelect.disabled=false;observerApply.disabled=false;observerSelect.value=data.outcome_observer.enabled?'1':'0';observerDrawn=true;}
   const key=JSON.stringify([data.counts,data.items,data.sources,data.outcome_observer]);
   note.textContent=data.coverage+' · '+new Date(data.sampled_at*1000).toLocaleTimeString()+(data.outcome_observer?.failed_tasks?' · '+data.outcome_observer.failed_tasks+' 项结果评价需要重试':'')+(data.outcome_observer?.lag_events?' · 评价事件待处理 '+data.outcome_observer.lag_events+' 条':'');
   if(!force&&key===signature)return;
   if(!force&&list.contains(document.activeElement))return;signature=key;
   summary.replaceChildren();for(const state of ['running','queued','needs_input']){const card=el('div',undefined,'work-count');card.dataset.state=state;card.append(el('strong',String(data.counts[state])),el('span',data.labels[state]));summary.append(card);}
   const expanded=new Map([...list.querySelectorAll('.work-group')].map(n=>[n.dataset.state,n.open]));
   list.replaceChildren();
   for(const state of ['needs_input','running','queued','external','waiting','unknown','failed','finished','cancelled']){
    const rows=data.items.filter(i=>i.state===state);if(!rows.length)continue;
    const section=el('details',undefined,'work-group');section.dataset.state=state;section.open=expanded.has(state)?expanded.get(state):!['finished','cancelled','failed'].includes(state);section.append(el('summary',data.labels[state]+' · '+rows.length));
    for(const item of rows){const row=el('article',undefined,'card work-item'),actions=el('div',undefined,'row');row.dataset.state=state;row.append(el('strong',item.title),el('p',item.reason||data.labels[state],'note'));
     if(item.source==='tasks'&&item.cancelable){row.append(el('small',(priorities[item.priority]?.[1]||'普通')+' · '+item.priority_reason+(item.due_at?' · 期望 '+new Date(item.due_at*1000).toLocaleString():'')));actions.append(button('调整优先级',()=>editPriority(item,()=>refresh(true))),button('停止此任务',async()=>{await post('/api/operations',{action:'task_cancel',id:item.id});await refresh(true);}));}
     if(item.source==='dialogue')actions.append(button('打开会话',()=>{location.href='/#chat='+encodeURIComponent(item.chat_id);}),button('停止此回复',async()=>{await post('/api/chat/cancel',{request_id:item.id});await refresh(true);}));
     if(item.source==='goals')actions.append(button('查看目标与待答问题',()=>{location.href='/settings#plans';}));
     outcomeView(row,item.outcome,{taskId:item.id,refresh:()=>refresh(true)});
     completionView(row,item.completion,{refresh:()=>refresh(true)});
     if(item.recovery_wait)row.append(el('p','恢复接续：'+({WAITING:'等待原模块恢复',QUEUED:'已重新排队',BLOCKED:'需核对授权、来源或工具版本',EXPIRED:'已到期，需重新安排',CANCELLED:'已取消',SUPERSEDED:'原等待已被新的任务状态替代'}[item.recovery_wait.state]||item.recovery_wait.state),'note'));
     actions.append(button('查看记录',()=>details('工作状态与来源',item)));row.append(actions);section.append(row);
    }list.append(section);
   }
   if(!data.items.length)list.append(el('p','已接入来源暂时没有工作记录。','empty'));
   const missing=data.sources.filter(s=>!['connected','not_started'].includes(s.status));
   if(missing.length)list.append(el('p','尚未纳入此视图：'+missing.map(s=>({'private-dialogue':'私密对话',anatomy:'机械场景','local-model-operations':'本地模型操作',mail:'邮件',dialogue:'聊天',images:'出图',studio3d:'3D 工作室'}[s.id]||s.id)).join('、')+'。请到对应模块查看。','note'));
  }catch(e){note.textContent='状态未能刷新，当前显示可能过期：'+e.message;}finally{loading=false;if(pendingRefresh&&!closed){pendingRefresh=false;void refresh(true);}}
 }
 refresh(true);const timer=setInterval(refresh,2000);return()=>{closed=true;clearInterval(timer);};
}
