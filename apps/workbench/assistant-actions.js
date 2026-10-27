import {el,button,post,notice,card,states,errorText} from './ui.js';
import {outcomeView,completionView} from './ui.js';
import {workClosure} from './rework-impact.js';

export function actionCard(parent,turn,{openGoal,refresh,openMemory}){
 const action=turn.assistant_action,goal=turn.linked_goal;
 if(!action||action.kind==='chat'||turn.status!=='SUCCEEDED')return;
 const goalStates={NEW:'等待规划',PLANNING:'正在规划',NEEDS_INPUT:'待补充能力或条件',REVIEW:'等待核对计划',SUCCEEDED:'执行完成'};
 const closureStates={COMPLETE:'当前版已结案',NEEDS_REVIEW:'当前版待核对',IN_PROGRESS:'当前版进行中',NEEDS_EVIDENCE:'当前版待核验',STOPPED:'已停止接续'};
 const c=card(goal?.work_closure?'此消息关联的工作 · '+closureStates[goal.work_closure.state]:goal?'此消息的目标 · '+(goalStates[goal.status]||states[goal.status]||goal.status):'识别到行动请求','');
 if(goal){
  workClosure(c,goal.work_closure);
  if(goal.work){c.append(el('p','负责人：Jarvis 默认 Bot · 共 '+goal.work.versions.length+' 个关联版本','note'));if(goal.work.current_goal!==goal.id)c.append(el('p','下面保留原版本结果，最新进展见当前版本。','note'),button('打开当前工作版本',()=>openGoal(goal.work.current_goal),'primary'));}
  if(goal.summary)c.append(el('p',goal.summary));
  if(goal.error)c.append(el('p',errorText(goal.error),'note'));
  if(goal.output!==null){c.append(el('pre',goal.output),el('p','以下为已确认执行回执中的输出；当前文件状态见结果核对。','note'));
   if(goal.memory_candidate_available===true)c.append(button('整理为待核对经验',async()=>{await post('/api/memory',{action:'propose_goal',goal_id:goal.id});await openMemory();}));}
  outcomeView(c,goal.outcome,{taskId:goal.task_id,refresh});
  completionView(c,goal.completion,{refresh});
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
