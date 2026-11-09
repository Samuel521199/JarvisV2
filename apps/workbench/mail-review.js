import {mailApi} from './mail-client.js';
import {el,button,modal,closeModal,notice} from './ui.js';

export async function reviewMailOperation(operation,payload,onApproved=()=>{},reviewCommand=null){
 const value=await (reviewCommand?reviewCommand(operation,payload):mailApi.command({action:'review',operation,payload})),body=modal('核对 Gmail 操作');
 body.append(el('p','确认后才会向 Google 提交以下准确操作。','note'),el('pre',JSON.stringify(value.summary,null,2),'mail-review'));
 const confirm=button(operation==='send'?'确认发送这封邮件':'确认执行本次操作',async()=>{
  confirm.disabled=true;try{
   const job=await mailApi.command({action:'approve',review_id:value.id,request_id:crypto.randomUUID()});
   closeModal();notice('已提交邮件任务；请核对原回执，待办尚未自动完成。');await onApproved(job);
  }finally{confirm.disabled=false;}
 },'primary');body.append(confirm);
}
