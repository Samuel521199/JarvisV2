import {mailApi} from './mail-client.js';
import {reviewMailOperation} from './mail-review.js';
import {el,button,field,input,notice} from './ui.js';

// Shared local draft/review component. Neither entry sends on save.
export function localDraftForm(body,{buffer,draftId='',draftRevision=0,onSaved=()=>{},onReviewed=()=>{},googleActions=true,reviewCommand=null}={}){
 const form=el('section');
 for(const [name,label] of [['to','收件人'],['subject','主题'],['body','正文']]){
  const control=name==='body'?el('textarea'):input();control.value=buffer[name];control.setAttribute('aria-label',label);
  control.maxLength=name==='body'?30000:name==='to'?254:200;if(name==='body')control.rows=8;
  control.oninput=()=>buffer[name]=control.value;form.append(field(label,control));
 }
 async function save(){const record=await mailApi.command({action:'draft',id:draftId,revision:draftRevision,value:buffer});draftId=record.id;draftRevision=record.revision;await onSaved(record);return record;}
 form.append(button('保存本地草稿',async()=>{await save();notice('草稿已加密保存；尚未发送，待办仍需明确结案。');},'primary'));
 if(googleActions)for(const [operation,label] of [['remote_draft','审阅 Google 草稿'],['send','审阅发送']]){
  form.append(button(label,async()=>{const record=await save();await reviewMailOperation(operation,{draft_id:record.id,revision:record.revision},onReviewed,reviewCommand);}));
 }
 body.append(form);return form;
}
