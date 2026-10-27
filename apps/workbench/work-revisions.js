import {el,button,post,card,modal,closeModal,field,select} from './ui.js';
import {automaticRework,workClosure} from './rework-impact.js';

export function workRevisions(parent,data,open){
 const w=data.work,p=data.plan,t=data.task;
 recoveryChoice(parent,data,open);
 workClosure(parent,data.work_closure);
 if(w){
  const c=card('这件工作的负责人 · Jarvis 默认 Bot',w.cancelled?'整件工作已停止接续':'当前第 '+w.versions.length+' 版 · 已用 '+w.spent_cost_units+' 成本单位');
  c.append(el('p','各版本保留自己的任务、授权与评价。当前显示第 '+w.versions.find(v=>v.goal_id===p.id).ordinal+' 版。','note'));
  const budget=w.budget;
  if(budget){
   const summary=el('p',budget.enforced?'整件工作执行额度：'+budget.spent_units+' 已用 + '+budget.reserved_units+' 预留 / '+budget.limit_units+' 总额 · 可用 '+budget.available_units:'历史工作尚未设置共享执行额度；原已受理任务保持自己的限制。','work-budget-summary');c.append(summary);
   c.append(el('p','按工具动作计单位，含本机保存；不含模型、研发费用。未确认效果保留预留，不代表可以重试。','note'));
   if(!w.cancelled)c.append(button('调整整件工作执行额度',()=>{
    const b=modal('整件工作执行额度'),limit=el('input'),note=el('textarea'),error=el('p',undefined,'form-error');limit.type='number';limit.min='1';limit.max='1000';limit.step='1';limit.value=budget.limit_units??Math.max(budget.committed_units,20);limit.setAttribute('aria-label','执行总额');note.rows=3;note.maxLength=1000;
    let request=crypto.randomUUID();for(const n of [limit,note])n.addEventListener('input',()=>{request=crypto.randomUUID();});
    b.append(field('执行总额',limit),field('调整原因',note),el('p','总额不能低于已用与预留之和。调整额度不会批准新任务、恢复取消任务或增加原任务许可。','note'),error,button('保存执行额度',async()=>{try{await post('/api/goals',{action:'set_work_budget',id:p.id,revision:budget.revision,request_id:request,limit_units:Number(limit.value),note:note.value});closeModal();await open(p.id);}catch(e){error.textContent=e.message;}},'primary'));
   }));
  }
  for(const v of w.versions){const r=el('div',undefined,'row');r.append(el('span','第 '+v.ordinal+' 版 · '+({original:'原始要求',correction:'纠错',new_requirement:'新增要求',recovery:'来源恢复'}[v.kind])+(v.goal_id===w.current_goal?' · 当前':'')),button('打开第 '+v.ordinal+' 版',()=>open(v.goal_id)));c.append(r);if(v.note)c.append(el('p',v.note,'note'));}
  if(w.current_goal!==p.id)c.append(button('打开当前版本',()=>open(w.current_goal),'primary'));
  if(!t&&!p.cancel&&!w.cancelled&&w.current_goal===p.id&&w.versions.some(v=>v.goal_id===p.id&&v.parent_goal))c.append(button('重新核对已变化的复用依据',()=>{
   const b=modal('重新核对复用依据'),note=el('textarea'),error=el('p',undefined,'form-error');note.rows=3;note.maxLength=1000;
   b.append(field('说明为何前段结果仍然适用',note),el('p','仅更新尚未批准的计划。原反馈会保留；来源撤回或回执损坏时仍不能复用。','note'),error,button('记录核对并更新依据',async()=>{try{await post('/api/goals',{action:'review_rework_source',id:p.id,revision:p.revision,work_revision:w.revision,note:note.value});closeModal();await open(p.id);}catch(e){error.textContent=e.message;}},'primary'));
  }));
  if(!w.cancelled)c.append(button('停止整件工作接续',async()=>{await post('/api/goals',{action:'cancel_work',id:p.id,work_revision:w.revision});await open(p.id);},'danger'));
  parent.append(c);
 }
 const supported=t?.status==='SUCCEEDED'&&!p.cancel&&p.proposal?.steps.every((s,i)=>s.capability.startsWith('plugin.')&&(!i||s.source==='previous'));
 if(!supported||w&&(w.cancelled||w.current_goal!==p.id||w.remaining_followups===0))return;
 automaticRework(parent,data,open);
 parent.append(button('关联返工 / 追加要求',()=>{
  const b=modal('接续同一件工作'),g=el('textarea'),note=el('textarea'),error=el('p',undefined,'form-error');
  const kind=select([['new_requirement','新增要求 · 保留原评价'],['correction','纠错 · 原版本记为需要改进']],'new_requirement');
  const start=select(p.proposal.steps.map((s,i)=>[String(i+1),'从第 '+(i+1)+' 步重做：'+s.title]),'1');
  kind.setAttribute('aria-label','变更类型');start.setAttribute('aria-label','最早需要重做的步骤');
  g.value=p.request.goal;g.rows=4;g.maxLength=4000;note.rows=3;note.maxLength=1000;
  let request=crypto.randomUUID();for(const n of [g,note,kind,start])n.addEventListener('input',()=>{request=crypto.randomUUID();});
  b.append(el('p','报价要求继承：纠错填写“保持全部要求”；改变要求填写如“将要求「预算不超过100元」替换为「预算不超过90元」”。完整新要求仍须包含未改条件。选择从第 1 步重做，并在生成后选择“对照返工继承要求核验”。','note'),field('完整的新要求',g),field('变更原因',note),field('变更类型',kind),field('最早需要重做的步骤',start),
   el('p','前面的步骤保留已确认输出，从选中步骤到末尾重做。生成后请调整行动计划并重新约定验收；这里只记录要求，不会自动把文字要求变成工具规则。每件工作最多 3 次接续。','note'),error,
   button('生成关联计划',async()=>{try{const r=await post('/api/goals',{action:'rework',id:p.id,revision:p.revision,work_revision:w?.revision||1,request_id:request,kind:kind.value,note:note.value,goal:g.value,start_step:Number(start.value)});closeModal();await open(r.id);}catch(e){error.textContent=e.message;}},'primary'));
 }));
}

function recoveryChoice(parent,data,open){
 const w=data.work,p=data.plan,t=data.task;
 if(!w||w.cancelled||w.current_goal!==p.id||p.cancel||!w.remaining_followups||!t||!['READY','WAITING','SUCCEEDED'].includes(t.status)||!w.versions.some(v=>v.goal_id===p.id&&v.parent_goal))return;
 parent.append(button('分析来源失效与恢复',async()=>{
  const b=modal('核对来源并建立恢复版本'),error=el('p','正在核对已冻结的来源与反馈…','form-error');b.append(error);
  try{
   const review=await post('/api/goals',{action:'analyze_recovery',id:p.id,revision:p.revision,work_revision:w.revision});
   error.textContent='';const note=el('textarea'),keep=el('input'),save=button('建立恢复草案',async()=>{
    try{save.disabled=true;const r=await post('/api/goals',{action:'recover_work',id:p.id,revision:p.revision,work_revision:w.revision,request_id:request,note:note.value,keep_requirements:keep.checked,analysis_digest:review.analysis_digest});closeModal();await open(r.id);}catch(e){error.textContent=e.message;save.disabled=!keep.checked;}
   },'primary');let request=crypto.randomUUID();note.rows=3;note.maxLength=1000;keep.type='checkbox';keep.setAttribute('aria-label','保持全部当前要求');save.disabled=true;
   for(const n of [note,keep])n.addEventListener('input',()=>{request=crypto.randomUUID();save.disabled=!keep.checked||!note.value.trim();});
   b.append(el('p','只发现可证明的反馈变化；原话、有效要求和已确认回执保持原依据。','recovery-summary'));
   for(const f of review.feedback_changes)b.append(el('p','来源反馈：'+(f.note||'（无说明）')));
   b.append(el('p',review.retire_pending_task?'建立草案时会停止旧任务，保留已确认动作与已用成本。':'旧版本已执行，保留其状态、旧验收和交付。'),el('p','仍使用本工作总额度：已用 '+review.spent_units+'，停止旧任务后可用 '+review.available_after_retirement+'；完整重做需要 '+review.required_units+' 单位。'),field('保持全部当前要求',keep),el('p','反馈中的文字不会自动新增或撤销要求。建立草案不执行，新版必须重新核对恢复依据和验收；需要改要求时应另行明确建版。','note'),field('恢复说明',note),error,save);
  }catch(e){error.textContent=e.message;}
 }));
}

export function workBudgetChoice(parent,data){
 const p=data.plan;
 if(data.task||data.work||p.status!=='REVIEW')return ()=>({});
 const n=el('input');n.type='number';n.min=String(p.proposal.steps.length+1);n.max='1000';n.step='1';n.value=String((p.proposal.steps.length+1)*4);n.setAttribute('aria-label','整件工作执行总额');
 parent.append(field('整件工作执行总额',n),el('p','包括本版及后续关联版本的工具动作，每次本机保存也计 1 单位。默认可覆盖 4 次同规模执行；每版仍按原流程受理，不含模型和研发费用。','note'));
 return ()=>({budget_limit:Number(n.value)});
}
