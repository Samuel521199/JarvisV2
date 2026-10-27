import {el,button,post,card,modal,closeModal,field,select} from './ui.js';

export function automaticRework(parent,data,open){
 const p=data.plan,w=data.work;
 parent.append(button('修改计划并自动分析返工范围',()=>{
  const b=modal('修改整份计划并分析影响'),g=el('textarea'),input=el('textarea'),note=el('textarea'),error=el('p',undefined,'form-error'),result=el('div');
  const candidate=structuredClone(p.proposal),kind=select([['new_requirement','新增要求'],['correction','纠正旧结果']],'new_requirement');
  g.value=p.request.goal;g.maxLength=4000;g.rows=3;input.value=candidate.input_text;input.maxLength=12000;input.rows=4;note.maxLength=1000;note.rows=2;
  let reviewed=null,request=crypto.randomUUID();
  const clear=()=>{reviewed=null;request=crypto.randomUUID();result.replaceChildren();};
  b.addEventListener('input',clear);b.addEventListener('change',clear);
  b.append(field('修改后的完整目标',g),field('修改后的原始输入',input),field('本次修改说明',note),field('本次修改类型',kind));
  if(w?.versions.some(v=>v.start_step>1))b.append(el('p','当前工作曾复用更早的前段。本分析只覆盖当前计划；若完整目标或输入发生变化，需要另行核对完整计划，不能只重做当前后段。','note'));
  for(const [i,s] of candidate.steps.entries()){
   const c=card('原计划步骤 '+(i+1),s.title),cap=select(p.catalog.filter(r=>r.capability.startsWith('plugin.')).map(r=>[r.capability,r.name]),s.capability),expected=el('textarea');
   expected.value=s.expected;expected.maxLength=1000;expected.rows=2;
   cap.addEventListener('change',()=>s.capability=cap.value);expected.addEventListener('input',()=>s.expected=expected.value);
   c.append(field('第 '+(i+1)+' 步能力',cap),field('第 '+(i+1)+' 步预期',expected));b.append(c);
  }
  function payload(){return {id:p.id,revision:p.revision,work_revision:w?.revision||1,goal:g.value,proposal:{...candidate,input_text:input.value}};}
  const reasons={goal_changed:'目标文字变化：无法证明影响只在后段，从头重做',input_changed:'原始输入变化：从头重做',step_or_binding_changed:'步骤描述、能力或工具版本变化：从最早变化处重做'};
  b.append(el('p','按输入、步骤和工具版本计算。只保留逐项相同且仍有效的前段；不能自动证明自然语言含义。分析不执行，生成后仍沿用原验收与执行流程。','note'),error,button('分析修改影响',async()=>{
   error.textContent='';reviewed=null;result.replaceChildren();
   try{const value=payload(),analysis=await post('/api/goals',{action:'analyze_rework',...value});
    // Edits made while the request was in flight invalidate the displayed review.
    if(JSON.stringify(value)!==JSON.stringify(payload()))return;
    reviewed={value,analysis};
    result.append(el('p','从第 '+analysis.start_step+' 步重做 · 保留 '+analysis.reused_steps.length+' 步 · 预计 '+analysis.planned_cost_units+' 执行单位（含保存）','impact-summary'));
    if(analysis.ancestor_prefix_reused)result.append(el('p','更早版本的前段继续受原来源核对约束；这次分析不会跳过那些约束。','note'));
    for(const reason of analysis.reasons)result.append(el('p',reasons[reason]||reason,'note'));
    result.append(button('按分析结果生成关联计划',async()=>{
     try{if(!reviewed)return;const r=await post('/api/goals',{action:'rework_auto',...reviewed.value,analysis_digest:reviewed.analysis.analysis_digest,request_id:request,kind:kind.value,note:note.value});closeModal();await open(r.id);}catch(e){error.textContent=e.message;}
    },'primary'));
   }catch(e){error.textContent=e.message;}
  }),result);
 }));
}

export function workClosure(parent,value){
 if(!value)return;
 const states={COMPLETE:'当前版本已按约定结案',NEEDS_REVIEW:'当前版本待核对与受理',IN_PROGRESS:'当前版本仍在执行或等待',NEEDS_EVIDENCE:'当前版本尚未结案',STOPPED:'工作已停止接续'};
 const c=card('整件工作的结案状态',states[value.state]||value.state);
 if(value.condition_score!==null)c.append(el('p','当前版约定条件检查：'+value.condition_score+'% · 不代表综合质量分','note'));
 const reasons={current_version_not_admitted:'新计划尚未执行',shared_budget_not_adopted:'历史工作需接入共享额度',budget_evidence_invalid:'额度依据不完整',budget_overcommitted:'已用和预留超过工作额度，需核查账本',unresolved_effects:'仍有执行效果待核对',work_or_version_stopped:'已停止，不自动重启',UNSPECIFIED:'缺少事前验收条件',SATISFIED:'已有条件通过，但未覆盖完整要求',NEEDS_CORRECTION:'收到纠正或条件未通过',INVALIDATED:'来源或执行依据已失效',UNAVAILABLE:'评价依据暂不可用',WAITING_EVIDENCE:'仍缺验证证据',current_execution_pending:'执行尚未完成'};
 for(const r of value.reasons)c.append(el('p',reasons[r]||r,'note'));
 c.append(el('p','所有历史入口都查看当前版本；旧版结果和评价保留。结案可因迟到反馈或来源撤回重新打开。','note'));parent.append(c);
}
