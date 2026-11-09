import {el,button,field,input,modal,closeModal,post,notice} from './ui.js';
import {exactTime,offsetText} from './commitment-time.js';
const id=()=>crypto.randomUUID().replaceAll('-','');

export function commitmentForm(refresh,item=null){
 const body=modal(item?'调整待办时间':'新增个人待办'),form=el('form'),title=input(item?.title||''),source=el('textarea'),when=input(),offset=input(offsetText(-new Date().getTimezoneOffset())),error=el('p',undefined,'form-error'),save=el('button','保存','primary');
 title.required=true;title.maxLength=200;source.required=true;source.maxLength=2000;source.rows=3;when.type='datetime-local';when.step='60';offset.pattern='[+-](0[0-9]|1[0-4]):[0-5][0-9]';offset.required=true;save.type='submit';
 if(item){title.readOnly=true;source.value=item.source_note;source.readOnly=true;if(item.due_text){when.value=item.due_text.slice(0,16);offset.value=item.due_text.endsWith('Z')?'+00:00':item.due_text.slice(-6);}}
 form.append(field('待办事项',title),field('原始要求或来源说明（本人填写）',source),field('提醒时间（留空则只记待办）',when),field('固定UTC偏移，例如 +08:00',offset),el('p','按这里明确的时间记录，不自动推断模糊日期。Jarvis运行时，到期事项进入精灵和工作台共用的工作视图；离线期间到期的事项会在恢复后补投。标记已阅与标记完成分开。','note'),error,save);
 const recordId=item?.id||id();let previous='',requestId=id();
 form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{
  const value=item?{action:'reschedule',id:recordId,revision:item.revision,due_at:exactTime(when.value,offset.value)}:{action:'create',id:recordId,title:title.value,source:source.value,due_at:exactTime(when.value,offset.value)};
  const signature=JSON.stringify(value);if(previous&&signature!==previous)requestId=id();previous=signature;
  await post('/api/commitments',{...value,request_id:requestId});closeModal();await refresh();notice('待办已保存。');
 }catch(ex){error.textContent=ex.message;}finally{save.disabled=false;}};body.append(form);
}

export function commitmentActions(row,actions,item,refresh){
 row.append(el('small',item.due_text?'约定时间：'+item.due_text:'未设置提醒时间'));
 if(!item.cancelable)return;
 actions.append(button('改期',()=>commitmentForm(refresh,item)));
 for(const [action,label] of [['complete','标记完成'],['cancel','取消待办']]){
  const requestId=id();actions.append(button(label,async()=>{await post('/api/commitments',{action,id:item.id,revision:item.revision,request_id:requestId});await refresh();}));
 }
}
