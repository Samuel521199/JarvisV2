import {el,button,field,select,post,modal,notice,run} from './ui.js';
const names={queued:'等待执行',running:'正在提取',succeeded:'候选已就绪',failed:'失败',unknown:'结果未知，未自动重试',cancelled:'已取消'};

export function extractionJobs(scope){
 const body=modal('知识提取任务'),list=el('div');body.append(el('p','只保存任务状态、用量和准确原文候选；模型草稿不作为记忆保存。中断后不会自动重复付费调用。','note'),list);
 async function refresh(){if(!list.isConnected)return;const r=await post('/api/knowledge-extraction',{action:'status',scope});if(!list.isConnected)return;list.replaceChildren();
  for(const job of r.jobs){const card=el('section',undefined,'card');card.append(el('strong',names[job.state]||job.state),el('p',`新增 ${job.added} 项 · 来源 r${job.source_revision}${job.error?' · '+job.error:''}`,'note'));
   if(['queued','running'].includes(job.state))card.append(button('取消提取',async()=>{await post('/api/knowledge-extraction',{action:'cancel',scope,request_id:job.id});await refresh();}));list.append(card);}
  if(!r.jobs.length)list.append(el('p','本范围尚无模型提取任务。','empty'));
  if(r.jobs.some(j=>['queued','running'].includes(j.state)))setTimeout(()=>run(refresh),1000);
 }
 body.append(button('刷新状态',refresh));run(refresh);
}

export function extractSource(source,settings){
 const body=modal('模型提取原文候选'),connections=settings.connections.filter(c=>c.enabled&&source.providers.includes(c.id)),provider=select(connections.map(c=>[c.id,c.label])),model=select([]),error=el('p',undefined,'form-error'),requestId=crypto.randomUUID();
 const models=()=>{model.replaceChildren();for(const m of connections.find(c=>c.id===provider.value)?.models.filter(m=>m.enabled)||[]){const o=el('option',m.label);o.value=m.id;model.append(o);}model.value=connections.find(c=>c.id===provider.value)?.model||model.value;};provider.onchange=models;models();
 body.append(el('p',`将此份原文“${source.title}”发送给你已允许的所选模型，最多调用一次。模型只挑选原文候选，仍需逐项审阅；不会自动成为事实。调用计入用量记录。`,'note'),field('已允许的接入方',provider),field('模型',model),error);
 const start=button('发送原文并提取候选',async()=>{start.disabled=true;try{const m=connections.find(c=>c.id===provider.value)?.models.find(m=>m.id===model.value);const reasoning=['off','none','minimal','low'].find(x=>m.reasoning_levels.includes(x))||'default';
  await post('/api/knowledge-extraction',{action:'start',scope:source.scope,id:source.id,revision:source.revision,provider:provider.value,model:model.value,reasoning,request_id:requestId});extractionJobs(source.scope);notice('任务已提交，聊天可以继续。完成后打开“知识候选 / 来源审阅”。');
 }catch(e){error.textContent=e.message;start.disabled=false;}});
 start.disabled=!connections.length||source.status!=='active';body.append(start,button('查看任务状态',()=>extractionJobs(source.scope)));
 if(!connections.length)body.append(el('p','请先为资料设置允许使用的模型接入方。','note'));
}
