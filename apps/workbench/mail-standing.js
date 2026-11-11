// Same policy, pending work and controls in the workbench and native web surface.
import {el,button,field,input,select,get,post,modal,notice,closeModal} from './ui.js';
import {mailApi} from './mail-client.js';
import {openMailTask} from './mail-work.js';

export const mailStandingApi={state:()=>get('/api/mail-standing'),command:value=>post('/api/mail-standing',value)};
const labels={DRAFT:'待核对启用',ACTIVE:'已启用',PAUSED:'已暂停',NEEDS_INPUT:'需要处理',CANCELLED:'已取消'};
const phases={REVIEW:'等待核对',WAITING:'等待下次检查',CHECKING:'正在检查邮件',BACKOFF:'等待退避后重试',WAITING_AUTH:'等待 Google 本人授权',WAITING_SCOPE:'等待邮箱权限',WAITING_NETWORK:'等待网络',NEEDS_INPUT:'需要处理',PAUSED:'已暂停',CANCELLED:'已取消'};
const errors={mail_watch_budget:'授权额度已用完；修改上限后重新核对，原用量保留。',mail_watch_partial:'本轮超过五页，请缩小搜索范围；没有宣称全部查完。',mail_watch_retry_exhausted:'已达有限重试上限；其他工作继续。',mail_source_changed:'原邮件来源有变化，请打开关联待办核对。',mail_account_changed:'原邮箱已断开或更换，原待办仍保留。',mail_watch_capacity:'已达保留历史或缓存容量，请核对后维护。'};

export async function reconnectMail(){
 const current=await mailApi.state(),caps=current.capabilities||{};
 if(['RUNNING','WAITING_BROWSER'].includes(current.authorization?.status)){notice('原 Google 授权仍在等待，请完成本人确认。');return;}
 await mailApi.command({action:'authorize',level:caps.modify?'manage':caps.draft?'compose':caps.send?'send':'read'});
 notice('已复用原配置发起 Google 授权；完成后原邮箱检查会自动接续。');
}

export async function mailStandingView(parent){
 const panel=el('section'),bar=el('div',undefined,'actions'),list=el('div');parent.append(panel);
 panel.append(el('h3','重要邮件持续助手'),el('p','定时只读检查 → 重要性规则 → 去重关联待办 → 本地提醒与有限跟进 → 原待办处理和反馈。','note'),bar,list);
 bar.append(button('+ 制定邮件安排',()=>mailStandingForm()),button('刷新',refresh),button('重新连接 Gmail',reconnectMail));
 async function refresh(){
  const data=await mailStandingApi.state();if(!panel.isConnected)return;list.replaceChildren();
  for(const w of data.items){
   const c=el('article',undefined,'card'),actions=el('div',undefined,'actions'),linked=Object.values(w.entries).filter(e=>e.todo_id);
   c.append(el('h4',w.title),el('p',labels[w.status]+' · '+(phases[w.phase]||w.phase)),el('p','已检查 '+w.checks_started+'/'+w.policy.max_checks+' 轮 · 已预留新建额度 '+w.new_items+'/'+w.policy.max_new_items+' · 关联待办 '+linked.length,'note'),el('p','范围：'+w.policy.query,'note'));
   if(w.last_checked)c.append(el('p','上次完整检查 '+new Date(w.last_checked*1000).toLocaleString(),'note'));
   if(w.error)c.append(el('p',errors[w.error]||w.error,'form-error'));
   if(w.notice_pending)c.append(el('p','通知已合并或正在安静时间内。','note'));
   const act=async action=>{await mailStandingApi.command({action,id:w.id,revision:w.config_revision,request_id:crypto.randomUUID()});await refresh();};
   if(w.status==='DRAFT')actions.append(button('核对并启用',()=>{
    const b=modal('确认邮件常设委托');b.append(el('h3',w.title),el('p','只对当前绑定账号按下面范围只读查信，使用现有分类规则；可自动建立本地待办。不会自动回复、标读、归档或删除邮件。邮件内容不会成为工具指令。'),el('pre',JSON.stringify(w.policy,null,2)),el('p','首次包含约定回看时段；到期时间使用你设置的默认延迟，不会假装已经理解邮件中的业务期限。安静时间只延后本地通知。','note'),button('确认范围并启用',async()=>{await act('approve');await openMailStanding();},'primary'));
   },'primary'));
   if(w.status==='ACTIVE')actions.append(button('立即检查',()=>act('check_now')),button('暂停',()=>act('pause')));
   if(['PAUSED','NEEDS_INPUT'].includes(w.status)&&w.granted)actions.append(button('按原范围接续',()=>act('resume')));
   if(['DRAFT','PAUSED','NEEDS_INPUT'].includes(w.status))actions.append(button('修改安排',()=>mailStandingForm(w)));
   if(w.status!=='CANCELLED')actions.append(button('取消持续检查',()=>act('cancel'),'danger'));
   for(const [i,e] of linked.entries())c.append(button('邮件待办 '+(i+1)+' · '+e.state+' · 已跟进 '+e.followups+' 次',()=>openMailTask(e.todo_id,()=>openMailStanding())));
   c.append(actions);list.append(c);
  }
  if(!data.items.length)list.append(el('p','尚未启用。连接 Gmail 后制定并核对一次安排即可；不会逐封重复请求创建本地待办的许可。','empty'));
 }
 await refresh();return refresh;
}

export async function openMailStanding(){const body=modal('Jarvis · 邮件与待办持续办事');await mailStandingView(body);}

export async function mailStandingForm(existing=null){
 const b=modal(existing?'修改邮件安排':'制定邮件持续安排'),form=el('form'),error=el('p',undefined,'form-error'),p=existing?.policy;
 const title=input(existing?.title||'重要邮件与待办'),query=input(p?.query||'in:inbox'),fields={};title.required=true;title.maxLength=100;query.required=true;query.maxLength=350;
 form.append(field('名称',title),field('Gmail 搜索范围',query));
 const numbers=[['interval_seconds','检查间隔（分钟）',15,60,5,1440],['lookback_hours','首次回看（小时）',24,1,1,168],['due_delay_seconds','新待办默认多久提醒（分钟）',60,60,1,10080],['followup_seconds','仍未处理时跟进间隔（小时）',24,3600,.25,168],['max_followups','每项最多跟进次数',3,1,0,5],['max_checks','本次授权最多检查轮数',672,1,1,1000],['max_new_items','最多预留新建待办数',20,1,1,100],['max_attempts','一次读取最多尝试次数',3,1,1,3],['notification_interval_seconds','通知最短间隔（分钟）',30,60,1,1440]];
 for(const [key,label,value,factor,min,max] of numbers){const n=input(String(p?p[key]/factor:value));n.type='number';n.required=true;n.min=String(min);n.max=String(max);n.step=key==='followup_seconds'?'.25':'1';fields[key]={n,factor};form.append(field(label,n));}
 const start=input(),end=input();
 for(const [n,v] of [[start,p?.quiet_start??1320],[end,p?.quiet_end??480]]){n.type='time';n.required=true;n.value=String(Math.floor(v/60)).padStart(2,'0')+':'+String(v%60).padStart(2,'0');}
 form.append(field('安静开始',start),field('安静结束（相同为关闭）',end),el('p','垃圾、回收站、可疑和推广内容不会自动建待办。重要性由 Gmail 标签、星标和现有发件人/关键词规则判断，可能误判；在邮箱分类规则中纠正。未结事项及用量在暂停、重启和修改后保留。','note'),error);
 const save=el('button','保存待核对安排','primary');save.type='submit';form.append(save);b.append(form);const requestId=crypto.randomUUID();
 form.onsubmit=async event=>{event.preventDefault();save.disabled=true;try{
  const minute=n=>Number(n.value.slice(0,2))*60+Number(n.value.slice(3,5));
  const policy={query:query.value,quiet_start:minute(start),quiet_end:minute(end),utc_offset_minutes:p?.utc_offset_minutes??-new Date().getTimezoneOffset()};
  for(const [key,{n,factor}] of Object.entries(fields))policy[key]=Number(n.value)*factor;
  const value={action:existing?'edit':'create',request_id:requestId,title:title.value,policy};if(existing)Object.assign(value,{id:existing.id,revision:existing.config_revision});
  await mailStandingApi.command(value);closeModal();notice('安排已保存；核对并启用后才会定时检查。');await openMailStanding();
 }catch(ex){error.textContent=errors[ex.code]||ex.message;}finally{save.disabled=false;}};
}
