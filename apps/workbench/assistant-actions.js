import {el,button,post,notice,card,states,errorText} from './ui.js';

export function actionCard(parent,turn,{openGoal,refresh,openMemory}){
 const action=turn.assistant_action,goal=turn.linked_goal;
 if(!action||action.kind==='chat'||turn.status!=='SUCCEEDED')return;
 const goalStates={NEW:'等待规划',PLANNING:'正在规划',NEEDS_INPUT:'待补充能力或条件',REVIEW:'等待核对计划'};
 const c=card(goal?'此消息的目标 · '+(goalStates[goal.status]||states[goal.status]||goal.status):'识别到行动请求','');
 if(goal){
  if(goal.summary)c.append(el('p',goal.summary));
  if(goal.error)c.append(el('p',errorText(goal.error),'note'));
  if(goal.output!==null){c.append(el('pre',goal.output),el('p','输出来自已确认的执行回执，已保存本机产物。','note'));
   if(goal.memory_candidate_available===true)c.append(button('整理为待核对经验',async()=>{await post('/api/memory',{action:'propose_goal',goal_id:goal.id});await openMemory();}));}
  c.append(button('计划、进度与交付',()=>openGoal(goal.id),'primary'));
 }else if(turn.applied_action){
  c.append(el('p',action.kind==='amend'?'补充已应用，原目标与历史回执保持关联。':action.kind==='cancel'?'取消已记录。':'已找到原目标。'),button('打开原目标',()=>openGoal(turn.applied_action.id)));
 }else{
  c.append(el('p',action.kind==='goal'?action.goal:action.kind==='amend'?'补充后的目标：'+action.goal:action.kind==='cancel'?'建议取消关联目标。':'建议接续关联目标。'));
  c.append(el('p',action.kind==='goal'?'先生成可核对计划，尚未执行工具。':'确认前不改变原任务；已经执行的动作不会重复。','note'));
  const label={goal:'生成目标计划',amend:'应用补充并重新规划',cancel:'确认取消该目标',resume:'打开原目标接续'}[action.kind];
  c.append(button(label,async()=>{const result=await post('/api/assistant/action',{turn_id:turn.id});
   if(['goal','amend'].includes(action.kind)){try{await post('/api/goals/plan',{id:result.id,retry_unknown:false});}catch(e){notice(e.message+' 目标已保存，请在计划中接续。');}}
   await refresh();openGoal(result.id);
  },action.kind==='cancel'?'danger':'primary'));
 }
 parent.append(c);
}
