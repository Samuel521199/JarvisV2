// One component/transport for the workbench and the companion work card.
import {el,button,field,input,select,get,post,modal,notice,details,closeModal} from './ui.js';
let detailCleanup=()=>{};
const labels={DRAFT:'待核对启用',ACTIVE:'已启用',PAUSED:'已暂停',NEEDS_INPUT:'需要处理',DONE:'计划已结束',CANCELLED:'已取消'};
export const standingApi={state:()=>get('/api/standing-work'),command:value=>post('/api/standing-work',value)};
export function scheduleHint(text=''){
 if(/不要|取消|解释|是什么|如果|怎么实现|[“”"]/.test(text))return null;
 const m=text.match(/每(?:隔)?\s*(\d+)\s*(分钟|小时|天)/);
 if(m){const n=Number(m[1])*({分钟:60,小时:3600,天:86400}[m[2]]);return n>=60&&n<=2592000?n:null;}
 return /每天|每日/.test(text)?86400:/每小时/.test(text)?3600:/每周/.test(text)?604800:null;
}
function stamp(value){return new Date(value*1000).toLocaleString();}

export async function standingView(parent,{goalId='',onChanged=()=>{}}={}){
 const panel=el('section'),list=el('div'),bar=el('div',undefined,'actions');parent.append(panel);panel.append(el('h3','持续办事'),el('p','核对一次固定计划与授权，后台按约定推进；可随时暂停或取消。','note'),bar,list);
 bar.append(button('+ 新建持续安排',()=>standingForm({goalId,onSaved:refresh}),'primary'),button('邮件与待办',async()=>{const {openMailStanding}=await import('./mail-standing.js');await openMailStanding();}),button('刷新',refresh));
 async function refresh(){
  const data=await standingApi.state();if(!panel.isConnected)return;list.replaceChildren();
  for(const row of data.items){
   const card=el('article',undefined,'card'),actions=el('div',undefined,'actions');
   card.append(el('h4',row.title),el('p',labels[row.status]+' · 已开始 '+row.runs_started+'/'+row.policy.max_runs+' 次 · 已预留 '+row.reserved_units+'/'+row.policy.max_action_units+' 行动单位'),el('p','下次 '+stamp(row.next_at)+(row.notice_pending?' · 通知已合并或等待安静时间结束':''),'note'));
   if(row.error)card.append(el('p','待处理：'+row.error,'form-error'));
   const act=async action=>{await standingApi.command({action,id:row.id,revision:row.revision,request_id:crypto.randomUUID()});await refresh();await onChanged();};
   if(row.status==='DRAFT'||row.status==='PAUSED'&&!row.granted)actions.append(button('核对计划并启用',()=>{
    const body=modal('核对持续办事授权');
    body.append(el('p',row.title),el('p','仅执行下面固定输入和固定版本的本地文字工具；不自动收集新资料，不发送邮件或操作桌面。运行期云模型预算为 0，规划/研发另走原审阅。'));
    for(const p of row.plans){body.append(el('h4',p.request.goal),el('pre',p.proposal.input_text));for(const s of p.proposal.steps)body.append(el('p',s.title+' · '+s.capability));body.append(el('pre',JSON.stringify(p.acceptance,null,2)));}
    body.append(el('p','开始 '+row.policy.start_at+'；间隔 '+row.policy.interval_seconds+' 秒；最多 '+row.policy.max_runs+' 次，'+row.policy.max_action_units+' 行动单位；最多尝试 '+row.policy.max_attempts+' 次。当前动作可能完成后才停下，后续动作会暂停。'),button('确认授权并启用',async()=>{await act('approve');await openStanding();},'primary'));
   }));
   if(row.status==='ACTIVE')actions.append(button('暂停后续动作',()=>act('pause')));
   if(['PAUSED','NEEDS_INPUT'].includes(row.status)&&row.granted)actions.append(button('重新核对并接续',()=>act('resume')));
   if(['PAUSED','NEEDS_INPUT'].includes(row.status)&&row.current_run)actions.append(button('取消本轮并修改安排',()=>act('abandon_run')));
   if(['DRAFT','PAUSED'].includes(row.status)&&!row.current_run)actions.append(button('修改安排',()=>standingForm({existing:row,onSaved:refresh})));
   if(!['DONE','CANCELLED'].includes(row.status))actions.append(button('取消此安排',()=>act('cancel'),'danger'));
   actions.append(button('查看授权、来源与历史',()=>details('持续办事记录',row)));
   for(const run of row.runs.slice(0,5)){
    const line=el('section');line.append(el('p','第 '+run.ordinal+' 次 · '+run.status+' · '+(run.error||'原任务回执已关联')));
    for(const id of run.goals)line.append(button('检查计划、补能力或关联返工',async()=>{detailCleanup();const b=modal('原任务 · 计划与结果');const {goalsView}=await import('./goals.js');const snapshot=await get('/api/snapshot');detailCleanup=goalsView(b,{initialId:id,settings:snapshot.settings});document.getElementById('modal').addEventListener('close',()=>detailCleanup(),{once:true});}));
    if(['VERIFIED','NEEDS_REVIEW'].includes(run.status))line.append(button('反馈 / 纠正 / 撤回经验',()=>{
     const b=modal('处理反馈'),kind=select([['accept','确认本次声明范围完成'],['reject','结果不合适，暂停后续'],['withdraw','撤回此前反馈和经验']],'accept'),note=input('', '说明适用条件或需要纠正的地方');
     b.append(field('反馈',kind),field('说明',note),el('p','反馈不覆盖失败验收。候选经验保留来源，不自动变成人格、喜好或长期事实。','note'),button('保存反馈',async()=>{await standingApi.command({action:'feedback',id:row.id,revision:row.revision,request_id:crypto.randomUUID(),run_id:run.id,kind:kind.value,note:note.value});await openStanding();},'primary'));
    }));
    if(run.learning_candidate)line.append(el('p','工作方法候选 · '+run.learning_candidate.state+' · '+run.learning_candidate.note,'note'));
    card.append(line);
   }
   card.append(actions);list.append(card);
  }
  if(!data.items.length)list.append(el('p','还没有持续安排。先从聊天或行动计划生成可核对的计划，再指定执行时间和验收要求。','empty'));
 }
 await refresh();return refresh;
}

export async function openStanding(options={}){detailCleanup();detailCleanup=()=>{};const body=modal('Jarvis · 持续办事');await standingView(body,options);}

export async function standingForm({goalId='',existing=null,suggestion=null,onSaved=()=>{}}={}){
 detailCleanup();detailCleanup=()=>{};
 const rows=await get('/api/goals'),choices=rows.filter(r=>!r.id.startsWith('standing-')&&['REVIEW','ACCEPTED'].includes(r.status)),body=modal(existing?'修改持续安排':'制定持续办事安排');
 if(!choices.length&&!existing){body.append(el('p','先生成一份完整行动计划，再来安排持续执行。'));return;}
 const title=input(existing?.title||'我的持续安排'),plans=el('div'),selected=[];
 const pick=select(choices.map(p=>[p.id,p.goal.slice(0,100)]),goalId||choices[0]?.id),form=el('form'),error=el('p',undefined,'form-error');
 async function add(id,expected=''){
  if(selected.length>=8)throw Error('最多八项计划');
  const detail=await post('/api/goals',{action:'detail',id}),p=detail.plan;
  if(!p.proposal?.steps?.length||p.proposal.questions.length)throw Error('这份计划仍有待解决问题。');
  const box=el('section',undefined,'card'),expect=el('textarea');expect.value=expected;expect.rows=3;expect.required=true;expect.maxLength=12000;
  const item={id,step:p.proposal.steps.length,expect};selected.push(item);
  box.append(el('strong',p.request.goal),el('pre',p.proposal.input_text),field('最后一个工具的精确预期输出（作为本次声明的验收要求）',expect),button('移除此项',()=>{selected.splice(selected.indexOf(item),1);box.remove();}));plans.append(box);
 }
 const cfg=existing?.policy,now=new Date(Date.now()+60000),start=input(),interval=select([['0','仅一次'],['3600','每小时'],['86400','每天'],['604800','每周'] ],String(cfg?.interval_seconds??0));
 start.type='datetime-local';start.step='1';const initial=cfg?new Date(cfg.start_at):now;start.value=new Date(initial.getTime()-initial.getTimezoneOffset()*60000).toISOString().slice(0,19);start.required=true;
 const count=input(String(cfg?.max_runs??3)),units=input(String(cfg?.max_action_units??20)),attempts=input(String(cfg?.max_attempts??3)),frequency=input(String((cfg?.notification_interval_seconds??300)/60)),quietStart=input(),quietEnd=input();
 for(const n of [count,units,attempts,frequency])n.type='number';
 count.min='1';count.max='100';units.min='1';units.max='1000';attempts.min='1';attempts.max='3';frequency.min='1';frequency.max='1440';
 for(const [n,value] of [[quietStart,cfg?.quiet_start??1320],[quietEnd,cfg?.quiet_end??480]]){n.type='time';n.value=String(Math.floor(value/60)).padStart(2,'0')+':'+String(value%60).padStart(2,'0');}
 if(suggestion)body.append(el('p','来自本轮请求：'+suggestion.quote+'；周期与首次时间仍需你核对。','note'));
 if(goalId){const d=await post('/api/goals',{action:'detail',id:goalId});const hint=suggestion?.interval_seconds||scheduleHint(d.plan.request.goal);if(hint&&[3600,86400,604800].includes(hint)&&!cfg)interval.value=String(hint);}
 form.append(field('名称',title),field('选择已生成的计划',pick),button('添加这一项',()=>add(pick.value)),plans,field('首次时间',start),field('重复周期',interval),field('最多运行次数',count),field('总行动单位上限',units),field('每项最多尝试次数',attempts),field('通知最短间隔（分钟）',frequency),field('安静开始',quietStart),field('安静结束（相同表示关闭）',quietEnd),el('p','采用当前设备的固定UTC偏移；跨夏令时需重新核对。错过多次只补一轮。输入和工具版本固定，来源改变会暂停。等待与运行不调用云模型。','note'),error);
 const save=el('button','保存待核对安排','primary');save.type='submit';form.append(save);body.append(form);
 if(existing)for(const p of existing.plans)await add(p.id,p.acceptance.criteria[0].expected);else if(goalId)await add(goalId);
 const requestId=crypto.randomUUID();
 form.onsubmit=async event=>{event.preventDefault();save.disabled=true;try{
  if(!selected.length)throw Error('至少添加一项计划');
  const minute=n=>Number(n.value.slice(0,2))*60+Number(n.value.slice(3,5));
  const policy={start_at:new Date(start.value).toISOString().replace('.000Z','Z'),interval_seconds:Number(interval.value),max_runs:Number(count.value),max_action_units:Number(units.value),max_attempts:Number(attempts.value),quiet_start:minute(quietStart),quiet_end:minute(quietEnd),utc_offset_minutes:-new Date(start.value).getTimezoneOffset(),notification_interval_seconds:Number(frequency.value)*60,cloud_model_budget_usd:0};
  const command={action:existing?'edit':'create',request_id:requestId,title:title.value,policy,plans:selected.map(p=>({goal_id:p.id,acceptance:{coverage:'complete',criteria:[{id:'output',step_id:'step-'+p.step,check:'text_equals',expected:p.expect.value}],requirements:[{id:'declared-output',text:'结果精确符合本人填写的预期文本',kind:'literal',criterion_ids:['output']}]}}))};
  if(existing)Object.assign(command,{id:existing.id,revision:existing.revision});
  await standingApi.command(command);closeModal();await onSaved();notice('安排已保存，核对并启用后才会执行。');await openStanding();
 }catch(ex){error.textContent=ex.message;}finally{save.disabled=false;}};
}
