import {el,button,post,modal,notice} from './ui.js';
import {commitmentForm,commitmentActions} from './commitments.js';
import {localDraftForm} from './mail-draft.js';
const labels={OPEN:'待处理',DUE:'已到提醒时间',DONE:'本人确认已处理',CANCELLED:'已取消'};
function item(row){return {...row,source_kind:'mail',source_note:row.source,cancelable:['OPEN','DUE'].includes(row.status)};}

export async function mailWorkSection(parent,message){
 const area=el('section',undefined,'card');area.append(el('strong','邮件待办与处理反馈'));parent.append(area);
 if(!message.account_generation||!message.source_digest){area.append(el('p','重新读取这封邮件后，即可建立有来源的待办。','note'));return;}
 async function refresh(){
  const data=await post('/api/mail-work',{action:'inspect',account_generation:message.account_generation,message_id:message.id});
  if(data.source_digest!==message.source_digest){area.replaceChildren(el('p','邮件缓存已更新，请重新读取后再安排。','note'));return;}
  area.replaceChildren(el('strong','邮件待办与处理反馈'));
  area.append(button('转为待办 / 设置提醒',()=>commitmentForm(refresh,null,{account_generation:data.account_generation,message_id:data.message_id,source_digest:data.source_digest})));
  for(const row of data.items){const line=el('article'),actions=el('div',undefined,'actions');line.append(el('p',row.title+' · '+labels[row.status]));commitmentActions(line,actions,item(row),refresh);line.append(actions);area.append(line);}
  area.append(el('p','邮件正文不授予权限。已阅、草稿保存、提交发送与本人确认完成分别记录。','note'));
 }
 try{await refresh();}catch(error){area.replaceChildren(el('p',error.message,'form-error'));}
}

export async function openMailTask(id,refresh=()=>{}){
 const data=await post('/api/mail-work',{action:'source',id}),body=modal('邮件待办处理'),row=data.task;
 const status=el('p',labels[row.status],'note');body.append(el('h3',row.title),status);
 if(data.source_status!=='available')body.append(el('p',({changed:'邮件缓存内容已变化，请回到邮件中重新核对；这里不展示旧正文。',disconnected:'原账号已断开或更换；不会展示其它账号的邮件。',missing:'来源缓存不可用。'}[data.source_status]||'来源待核对')+' 原待办保留，可改期、完成或取消。','note'));
 else{
  const message=data.message;body.append(el('h4',message.subject||'无主题'),el('p',message.from),el('pre',message.body||message.snippet,'mail-detail-body'));
  for(const effect of data.effects||[])body.append(el('p','邮件处理回执 · '+effect.operation+' · '+effect.status+(effect.error?' · '+effect.error:''),'note'));
  body.append(button('起草回复',()=>{
   const draftArea=el('section');body.append(draftArea);
   localDraftForm(draftArea,{buffer:{to:message.from.match(/<([^>]+)>/)?.[1]||message.from,subject:/^re:/i.test(message.subject)?message.subject:'Re: '+message.subject,body:''},onReviewed:async()=>{await refresh();},reviewCommand:(operation,payload)=>post('/api/mail-work',{action:'review_reply',id,operation,payload})});
  }));
 }
 const controls=el('section');body.append(controls);
 function paintFeedback(current){
  controls.replaceChildren();const actions=el('div',undefined,'actions');
  commitmentActions(controls,actions,item(current),async()=>{
   await refresh();const next=await post('/api/mail-work',{action:'source',id});status.textContent=labels[next.task.status];paintFeedback(next.task);notice('处理反馈已保存。');
  },{source:false});controls.append(actions);
 }
 paintFeedback(row);
 body.append(el('p','标记完成表示你本人确认，不等于系统已独立验证回复内容或对方已收到。','note'));
}
