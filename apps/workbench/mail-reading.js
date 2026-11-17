import {mailApi} from './mail-client.js';
import {el,button,field,input,select,modal,closeModal,notice} from './ui.js';

if(!document.querySelector('link[href="/mail-reading.css"]')){const style=el('link');style.rel='stylesheet';style.href='/mail-reading.css';document.head.append(style);}
const names={read:'标为已读',unread:'标为未读',trash:'移入垃圾箱',untrash:'移回邮件',archive:'归档',undo:'撤销整理'};
export async function refreshMailCounts(){const job=await mailApi.run('counts',{});return job.status==='SUCCEEDED';}

export async function openMailMessage(id,{state,onDisplay,onChanged,visible=()=>true,signal}={}){
 let detail;
 try{detail=await mailApi.command({action:'cached_message',message_id:id});}
 catch(error){if(!String(error.message).includes('mail_body_not_cached'))throw error;}
 if(!detail){const job=await mailApi.run('read',{message_id:id},{signal});if(job.status!=='SUCCEEDED')throw Error('正文未读取完成：'+(job.error||job.status)+'。原任务保留，未重复提交。');detail=job.result;}
 if(detail.account_generation&&detail.account_generation!==state.account_generation)throw Error('邮箱已变化，请重新选择邮件。');
 if(!visible())return detail;await onDisplay(detail);
 await new Promise(resolve=>requestAnimationFrame(resolve));
 if(visible()&&!document.hidden&&state.view_preferences?.mark_read_on_open&&state.capabilities?.modify&&!state.network_blocked
     &&state.status!=='auth_required'&&state.health!=='auth_required'&&detail.labels?.includes('UNREAD')){
  // The visible row click and saved UI choice mean "open and mark read".
  // Reuse the exact review/approval and its account-generation/STOP guards.
  const review=await mailApi.command({action:'review',operation:'change',payload:{message_id:id,change:'read'}});
  if(!visible())return detail;
  const job=await mailApi.command({action:'approve',review_id:review.id,request_id:crypto.randomUUID()});
  const done=await mailApi.wait(job,{signal});
  if(done.status==='SUCCEEDED'){detail={...detail,...done.result.message};await refreshMailCounts();await onChanged?.(detail,done);}
  else throw Error('正文已打开，已读同步'+(done.status==='UNKNOWN'?'结果未知，未重试':'尚未完成：'+(done.error||done.status))+'；请查看原回执。');
 }
 return detail;
}

export function readingPreference(container,state,changed){
 const label=el('label',undefined,'mail-reading-switch'),box=el('input');box.type='checkbox';box.checked=!!state.view_preferences?.mark_read_on_open;
 box.disabled=!state.capabilities?.modify;label.append(box,el('span','打开正文后标为已读'+(box.disabled?' · 需 Gmail 管理权限':'')));
 box.onchange=async()=>{box.disabled=true;try{await mailApi.command({action:'view_preferences',revision:state.view_preferences?.revision||0,mark_read_on_open:box.checked,account_generation:state.account_generation});await changed();}catch(error){box.checked=!!state.view_preferences?.mark_read_on_open;notice(error.message);}finally{box.disabled=!state.capabilities?.modify;}};
 container.append(label);
}

async function reviewMany(entries,title,onComplete){
 if(!entries.length||entries.length>20)throw Error('每批请选择 1–20 封邮件。');
 const reviews=[];for(const entry of entries)reviews.push(await mailApi.command({action:'review',...entry}));
 const body=modal(title),status=el('p','逐封保留回执；遇到未知结果就停止，不重复提交。','note'),list=el('div',undefined,'mail-batch-review');
 body.append(el('p','账号：'+reviews[0].summary.account),el('p','只处理下面明确列出的邮件。移入垃圾箱可撤销，本次不会永久删除。','note'),list,status);
 for(const review of reviews)list.append(el('p',review.summary.subject||review.summary.original_job||'邮件'),el('small',review.summary.sender||''));
 const confirm=button('确认本批 '+reviews.length+' 项操作',async()=>{
  confirm.disabled=true;const completed=[];
  try{for(const [index,review] of reviews.entries()){
   status.textContent='处理中 '+(index+1)+' / '+reviews.length;
   const job=await mailApi.command({action:'approve',review_id:review.id,request_id:crypto.randomUUID()});
   const done=await mailApi.wait(job);completed.push(done);
   if(done.status!=='SUCCEEDED'){status.textContent='已停止：'+done.status+' · 原任务 '+done.id+'。剩余未提交。';if(completed.some(j=>j.status==='SUCCEEDED'))await refreshMailCounts().catch(()=>false);await onComplete(completed);return;}
  }await refreshMailCounts();closeModal();await onComplete(completed);notice('本批操作完成，可从原回执撤销整理。');}
  catch(error){status.textContent=error.message+'；已处理项保留，未自动重试。';if(completed.some(j=>j.status==='SUCCEEDED'))await refreshMailCounts().catch(()=>false);await onComplete(completed);}
 },'danger');body.append(confirm);
}
export function changeMailBatch(messages,change,onComplete){return reviewMany(messages.map(m=>({operation:'change',payload:{message_id:m.id,change}})),(names[change]||change)+' · '+messages.length+' 封',onComplete);}
export function undoMailBatch(jobs,onComplete){return reviewMany(jobs.filter(j=>j.status==='SUCCEEDED').map(j=>({operation:'undo',payload:{job_id:j.id}})),'撤销上一批整理',onComplete);}

export function mailReaderActions(container,detail,state,changed){
 const row=el('div',undefined,'mail-reader-actions');
 for(const [change,label] of [['read','标为已读'],['unread','标为未读'],['archive','归档'],['trash','移入垃圾箱']]){
  const b=button(label,()=>changeMailBatch([detail],change,changed),change==='trash'?'danger':'');b.disabled=!state.capabilities?.modify||state.network_blocked||state.status==='auth_required'||state.health==='auth_required';row.append(b);
 }container.append(row);
}

export async function mailFolderEditor(changed){
 const state=await mailApi.state(),body=modal('个性化邮件整理 · 本地 0 云端 token'),kind=select([['subject','标题包含'],['sender','发件人完整邮箱'],['domain','发件人域名']]),pattern=input('','例如：invoice / 项目名 / example.com'),folder=input('','你的分类名称'),list=el('div');let editing=null;
 body.append(el('p','只匹配标题和发件人，不上传正文、不调用云端模型；分类是提示，不代表邮件可信。保存后可立即纠正或撤销。','note'),field('匹配字段',kind),field('匹配内容',pattern),field('归入分类',folder),button('保存本地分类规则',async()=>{await mailApi.command({action:'folder_rule',id:editing?.id||'',revision:editing?.revision||0,field:kind.value,pattern:pattern.value.trim(),folder:folder.value.trim(),priority:50,enabled:true,account_generation:state.account_generation});closeModal();await changed();},'primary'),list);
 for(const rule of state.rules||[]){const row=el('div',undefined,'mail-rule-row');row.append(el('strong',rule.folder||rule.category),el('span',rule.pattern||rule.sender),...(rule.kind==='folder_rule'?[button('修改规则',()=>{editing=rule;kind.value=rule.field;pattern.value=rule.pattern;folder.value=rule.folder;pattern.focus();})]:[]),button('撤销规则',async()=>{await mailApi.command({action:'remove_rule',id:rule.id,revision:rule.revision});row.remove();await changed();}));list.append(row);}
}
