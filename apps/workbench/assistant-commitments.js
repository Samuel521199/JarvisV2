import {el,button,card,field,input,post,get,details} from './ui.js';
import {exactTime,offsetText} from './commitment-time.js';

export function commitmentCard(parent,turn,refresh){
 const candidate=turn.assistant_action.commitment,view=turn.commitment_action||{mode:'UNAVAILABLE',message:'待刷新受理状态'};
 const c=card(view.mode==='APPLIED'?'本地待办受理回执':'本地待办候选','');
 if(view.mode==='APPLIED'){
  const row=view.receipt.current;
  c.append(el('strong',row.title),el('p',({OPEN:'已保存，等待约定时间或后续处理',DUE:'已到期并进入本地工作视图',DONE:'主人已标记完成',CANCELLED:'已取消'})[row.status]),
   el('p',(row.due_text?'约定时间：'+row.due_text:'未设置提醒时间')+' · 当前版本 '+row.revision,'note'),
   button('查看待办记录',async()=>details('待办记录',await get('/api/commitments/'+row.id))));
  parent.append(c);return;
 }
 c.append(el('strong',candidate.title),el('blockquote',candidate.quote),el('p',view.message,'note'));
 if(['UNAVAILABLE','NOT_REQUEST'].includes(view.mode)){parent.append(c);return;}
 const form=el('form'),when=input(),offset=input(offsetText(-new Date().getTimezoneOffset())),error=el('p',undefined,'form-error'),save=el('button',candidate.operation==='cancel'?'确认取消此待办':candidate.operation==='complete'?'确认标记完成':'保存此本地待办','primary');
 form.dataset.commitmentDraft='1';
 form.oninput=form.onchange=()=>{form.dataset.commitmentDirty='1';};
 when.type='datetime-local';when.step='60';when.required=!!view.needs_time;offset.required=true;save.type='submit';
 if(view.due_at){when.value=view.due_at.slice(0,16);offset.value=view.due_at.endsWith('Z')?'+00:00':view.due_at.slice(-6);}
 if(['create','reschedule'].includes(candidate.operation))form.append(field('明确提醒时间',when),field('固定UTC偏移，例如 +08:00',offset));
 form.append(el('p','此操作只保存或修改本机待办，不发送邮件或外部通知。已阅与完成仍分别记录。','note'),error,save,
  button('放弃补充并刷新',async()=>{delete form.dataset.commitmentDirty;if(form.contains(document.activeElement))document.activeElement.blur();await refresh();}));
 form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{
  const result=await post('/api/assistant/commitment',{turn_id:turn.id,due_at:['create','reschedule'].includes(candidate.operation)?exactTime(when.value,offset.value):null});
  if(result.mode!=='APPLIED')throw Error(result.message||'尚未受理，请补充时间。');
  delete form.dataset.commitmentDirty;
  if(form.contains(document.activeElement))document.activeElement.blur();await refresh();
 }catch(ex){error.textContent=ex.message;}finally{save.disabled=false;}};
 c.append(form);parent.append(c);
}
