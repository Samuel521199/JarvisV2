import {mountWorkBoard} from './work-board.js';
import {el,field,input,select,post,modal,closeModal,notice} from './ui.js';

const priorities=[['0','稍后'],['1','普通'],['2','优先'],['3','紧急']];
function editPriority(item,refresh){
 const body=modal('任务优先级'),form=el('form'),priority=select(priorities,String(item.priority)),importance=select([['0','较低'],['1','普通'],['2','重要'],['3','非常重要']],String(item.importance)),due=input(),reason=input('主人在工作状态中调整'),error=el('p',undefined,'form-error'),save=el('button','保存优先级','primary');
 priority.setAttribute('aria-label','执行优先级');importance.setAttribute('aria-label','重要性');due.type='datetime-local';reason.maxLength=200;reason.required=true;save.type='submit';
 if(item.due_at){const date=new Date(item.due_at*1000);due.value=new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);}
 form.append(el('p',item.title),field('执行优先级',priority),field('重要性',importance),field('期望完成时间（可空）',due),field('安排理由',reason),el('p','影响后续调度，不会强行中断已开始的动作；资源不足时会显示等待原因。','note'),error,save);
 form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{await post('/api/scheduler/priority',{id:item.id,revision:item.revision,priority:Number(priority.value),importance:Number(importance.value),due_at:due.value?new Date(due.value).getTime()/1000:null,reason:reason.value});closeModal();await refresh();notice('任务优先级已保存。');}catch(ex){error.textContent=ex.message;}finally{save.disabled=false;}};body.append(form);
}

export function workStatusView(body,options={}){return mountWorkBoard(body,{...options,editPriority});}
