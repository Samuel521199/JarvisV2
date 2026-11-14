import {el,button} from './ui.js';

export function planningAdvice(parent,advice,openGoal){
 if(!advice)return;
 const panel=el('details',undefined,'planning-advice'),count=(advice.offered||[]).length;
 panel.append(el('summary',`本次经验参考 · ${count} 条 · ${advice.current?'引用已重验':'需要重新核对'}`));
 if(advice.inherited_from){
  panel.append(el('p','保留上游工作的经验依赖；没有把旧建议重新提供给本次模型。','note'));
  if(openGoal)panel.append(button('查看上游工作',()=>openGoal(advice.inherited_from)));
 }else panel.append(el('p',advice.model_dispatched?'已有真实模型派发回执。提供参考不等于模型实际采用或已经证明有帮助。':'尚无匹配的模型派发回执，不能计作已经使用。','note'));
 if(!advice.current)panel.append(el('p','来源、适用条件或反证发生变化，需重新核对相关工作。','form-error'));
 const exposure=advice.message_exposure;
 if(exposure){
  panel.append(el('p',`装配输入体积：不含经验卡 ${exposure.without_advice_bytes.toLocaleString()} 字节 → 本次 ${exposure.full_bytes.toLocaleString()} 字节，增加 ${exposure.added_bytes.toLocaleString()} 字节。`,'note'));
  panel.append(el('p','这是消息体积，不是 token、实际费用或经验贡献；装配不等于已派发。','note'));
 }
 const observation=advice.observation;
 if(observation){
  panel.append(el('p',observation.condition_score==null?'本任务条件评分尚未确定。':`本任务已声明条件得分 ${observation.condition_score} / 100。`));
  panel.append(el('p',observation.review_required?'已有失效或反证记录，请先定位原因；不自动判定经验导致失败。':'评分只覆盖已声明检查条件，经验贡献仍未证明。','note'));
 }
 if((advice.model_calls||[]).length)panel.append(el('p',`模型回执 ${(advice.model_calls||[]).length} 条；详细成本沿用原模型用量记录。`,'note'));
 const references=el('details');references.append(el('summary','查看本次引用编号'));
 for(const ref of advice.offered||[])references.append(el('p',`${ref.source_id} · 修订 ${ref.source_revision}`,'note'));
 panel.append(references);parent.append(panel);
}
