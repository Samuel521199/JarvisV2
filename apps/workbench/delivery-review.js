import {el} from './ui.js';

export function basisEditor(before,onChange){
 const box=el('details',undefined,'delivery-basis-editor'),summary=el('summary','资料与计划核对（可选）');box.append(summary);
 const enable=document.createElement('input');enable.type='checkbox';enable.id='delivery-basis-update';
 const label=el('label');label.append(enable,document.createTextNode('随本次消息更新核对依据'));box.append(label);
 const fields={};
 for(const [key,title] of [['facts','明确提供的事实'],['plans','已确认的计划（含时间与限制）']]){
  const wrap=el('label',title),area=document.createElement('textarea');area.id='delivery-basis-'+key;area.rows=3;area.maxLength=6000;area.setAttribute('aria-label',title);wrap.append(area);box.append(wrap);fields[key]=area;
  area.addEventListener('input',()=>{enable.checked=true;onChange();});
 }
 const state=el('p',undefined,'note');box.append(state,el('p','每行一条，后续回复沿用。内容会随消息发送；清空两栏并勾选更新会停止后续核对。核对不会设置提醒、执行计划或修改回答。','note'));before.before(box);
 let revision=0;
 enable.addEventListener('change',()=>onChange());
 function update(chat){
  const current=chat?.delivery_basis||{revision:0,entries:[]};
  if(!enable.checked){revision=current.revision;for(const k of ['facts','plans'])fields[k].value=current.entries.filter(x=>x.kind===k).map(x=>x.quote).join('\n');}
  state.textContent=enable.checked&&revision!==current.revision?'依据已被更新，请先取消勾选以载入当前版本，再重新核对。':'当前依据版本 '+current.revision+'；影子检查只提供核对线索。';
  const disabled=!!(chat?.archived||chat?.removed);enable.disabled=disabled;for(const x of Object.values(fields))x.disabled=disabled;
 }
 return {
  value:()=>({enabled:enable.checked,expected_revision:revision,facts:fields.facts.value,plans:fields.plans.value}),
  restore(value,chat){enable.checked=!!value?.enabled;if(enable.checked){revision=value.expected_revision;fields.facts.value=value.facts;fields.plans.value=value.plans;}update(chat);},
  update,
  commit(){enable.checked=false;},
  apply(request){
   if(!enable.checked)return request;
   const facts=fields.facts.value.split('\n').map(x=>x.trim()).filter(Boolean),plans=fields.plans.value.split('\n').map(x=>x.trim()).filter(Boolean);
   const text=request.text+'\n\n本次明确更新交付核对依据（资料声明，不是新的外部动作要求）：\n事实：\n'+(facts.join('\n')||'无')+'\n已确认计划：\n'+(plans.join('\n')||'无');
   if(text.length>12000)throw Error('消息与核对依据合计超过12000字，请精简后发送。');
   return {...request,text,delivery_basis:{expected_revision:revision,facts,plans}};
  }
 };
}

export function deliveryReviewView(parent,turn){
 const basis=turn.delivery_basis,review=turn.delivery_review;if(!basis)return;
 const labels={EXCERPT_MATCH:'来源摘录格式匹配',PROSE_UNVERIFIED:'原文已找到，全文语义未核实',REVIEW:'可能改写或遗漏，待核对',NO_BASIS:'核对依据已清空',UNAVAILABLE:'核对暂不可用',NOT_APPLICABLE:'本轮不适用正文核对'};
 const box=el('details',undefined,'delivery-review');box.dataset.reviewState=review?.stale?'STALE':review?.state||'PENDING';
 box.append(el('summary','交付核对：'+(review?.stale?'依据或回复已变化，此为历史核对':labels[review?.state]||(['READY','RUNNING'].includes(turn.status)?'等待回复':'本轮未核对'))));
 box.append(el('p','依据版本 '+basis.revision+'。此检查不会拦截或改写回答；逐字缺失也可能只是合理改写，全文真实性与建议质量仍需核对。','note'));
 const list=el('ul');for(const entry of basis.entries){const missing=review?.checks?.some(c=>c.id===entry.id&&c.status==='literal_not_found');list.append(el('li',(entry.kind==='plans'?'计划：':'事实：')+entry.quote+(missing?'〔回复中未找到原文〕':'')));}box.append(list);
 if(review?.method==='source_excerpt'){const failures=review.checks.filter(c=>c.status!=='passed');box.append(el('p',failures.length?'摘录的来源、当前范围或正文一致性存在差异，请对照原文。':'仅当前摘录与正文格式匹配，不等于综合质量合格。','note'));}
 parent.append(box);
}
