// Shared transport for workbench and companion; authority and effects remain in /api/mail.
import {get,post} from './ui.js';

export const mailApi={
 state:()=>get('/api/mail'),
 overview:()=>get('/api/mail/companion'),
 command:value=>post('/api/mail',value),
 async run(operation,payload,{signal,onProgress,timeout=65000}={}){
  if(signal?.aborted)throw new DOMException('Cancelled','AbortError');
  let job=await this.command({action:'job',request_id:crypto.randomUUID(),operation,payload});
  const end=Date.now()+timeout;
  while(['READY','RUNNING'].includes(job.status)){
   onProgress?.(job);
   if(signal?.aborted)throw new DOMException('Cancelled','AbortError');
   if(Date.now()>end)throw Error('邮件仍在处理中，可在工作台查看原任务；没有重新提交。');
   await new Promise(resolve=>setTimeout(resolve,800));
   if(signal?.aborted)throw new DOMException('Cancelled','AbortError');
   job=await this.command({action:'detail',id:job.id});
  }
  return job;
 }
};
