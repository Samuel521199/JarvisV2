import {voicePractice} from './english-voice.js';
import {el,button,field,post,markdown} from './ui.js';

const labels={life:'生活交流',communication:'日常沟通',work:'工作资料'};
export async function englishLearningView(parent,{route,ensureChat,refreshChat=async()=>{}}){
 let disposed=false,timer=null,state=null,draft='',material='',domain='auto',assistance='independent',selected=null,pending=null,working=false,recorded=null,voiceCleanup=()=>{},oralMode=false;
 const error=el('p',undefined,'form-error');
 async function load(){state=await post('/api/english-learning',{action:'status'});if(!disposed)render();}
 async function act(value){
  if(working)return;working=true;error.textContent='';
  try{state=await post('/api/english-learning',value);if(!disposed)render();await refreshChat();}
  catch(e){error.textContent=e.message;}finally{working=false;}
 }
 async function submit(kind,ex=null){
  if(working)return;working=true;error.textContent='';
  try{
   if(!pending){const chat_id=await ensureChat();pending={action:kind,request_id:'english-'+crypto.randomUUID(),chat_id,...route(),...(['start','oral_start'].includes(kind)?{domain,study_text:material}:{exercise_id:ex.id,answer:draft,assistance})};}
   if(kind==='oral_answer'&&!pending.audio_id){const saved=await post('/api/english-learning',{action:'record',audio:recorded});pending.audio_id=saved.recording.id;}
   state=await post('/api/english-learning',pending);pending=null;recorded=null;draft='';if(!disposed)render();await refreshChat();
  }catch(e){error.textContent=e.message+'；请求若已受理，不会因再次核对而重复调用模型。';}
  finally{working=false;}
 }
 async function listen(ex){try{const r=await post('/api/english-learning',{action:'speak',exercise_id:ex.id});if(disposed)return;const audio=el('audio');audio.controls=true;audio.src='data:audio/wav;base64,'+r.audio;parent.append(audio);await audio.play();}catch(e){error.textContent='本机英文朗读未完成：'+e.message;}}
 function render(){
  clearTimeout(timer);voiceCleanup();voiceCleanup=()=>{};parent.replaceChildren();parent.append(el('p','先尝试表达 → 看纠错与记忆提示 → 换情境再用 → 隔天回忆。每次少量练习；评分是AI对文字任务的估计，可以提出异议。','note'));
  const enabled=el('input');enabled.type='checkbox';enabled.checked=state.config.enabled;
  enabled.onchange=()=>act({action:'configure',enabled:enabled.checked,revision:state.config.revision});
  parent.append(field('保存并使用个人跨会话学习记录',enabled),el('p','仅英语学习面板的作答进入学习记录；普通聊天保持原方式。关闭后停止使用与新增，已有记录保留。不会自动创建提醒。','note'));
  const table=el('table'),head=el('tr');for(const name of ['场景','有效评价','独立 / 辅助','隔天变式'])head.append(el('th',name));table.append(head);
  for(const [key,row] of Object.entries((oralMode?state.oral_progress:state.progress).domains)){const tr=el('tr');for(const value of [labels[key],row.attempts,`${row.independent} / ${row.assisted}`,row.delayed_variants])tr.append(el('td',String(value)));table.append(tr);}
  const mode=el('input');mode.type='checkbox';mode.checked=oralMode;mode.onchange=()=>{oralMode=mode.checked;render();};parent.append(field('口语内容练习（录音后确认转写）',mode));
  parent.append(table,el('p',(oralMode?state.oral_progress:state.progress).trends.length?'以下为同技能、同难度的AI评分变化；不是等级认证或因果效果证明。':'尚无足够可比的延迟样本，暂不判断学习进步。','note'));
  for(const t of (oralMode?state.oral_progress:state.progress).trends)parent.append(el('p',`${t.target} · 难度${t.difficulty}：前3次 ${t.earlier_mean_out_of_6}/6 → 最近3次 ${t.later_mean_out_of_6}/6（独立变式）。`));
  if(state.withheld_assessments)parent.append(el('p',`${state.withheld_assessments}条评价因争议、低置信或来源失效不参与调整。`,'note'));
  parent.append(el('h3','开始 / 接续'));
  const choose=el('select');for(const [key,name] of Object.entries({auto:'按到期复习与新内容选择',...labels,mistakes:'复习错题与辅助作答'}))choose.add(new Option(name,key));choose.value=domain;choose.onchange=()=>domain=choose.value;
  const source=el('textarea');source.rows=3;source.maxLength=4000;source.value=material;source.placeholder='可选：粘贴希望读懂的工作资料；不填则使用标明的教学示例。';source.oninput=()=>material=source.value;
  const start=button('开始下一题',()=>submit(oralMode?'oral_start':'start'),'primary');start.disabled=!state.config.enabled;
  parent.append(field('练习场景',choose),field('本次资料（会发送给所选模型）',source),start);
  const due=(oralMode?state.oral_progress:state.progress).review.filter(x=>x.due_now);parent.append(el('p',`当前到期 ${due.length} 项。未复习不自动扣分；也可先练一个新场景。`,'note'));
  const waiting=state.exercises.filter(x=>!x.assessment&&(x.exercise.practice_mode==='oral')===oralMode);let current=waiting.find(x=>x.id===selected)||waiting[0];
  if(current){
   selected=current.id;parent.append(el('h3','待作答'),markdown(current.exercise.prompt));
   if(current.exercise.hint)parent.append(el('p','提示：'+current.exercise.hint));if(current.exercise.reference){parent.append(el('p','参考：'+current.exercise.reference),button('听参考表达 / 跟读',()=>listen(current)));}
   const answer=el('textarea');answer.rows=4;answer.maxLength=3000;answer.value=draft;answer.placeholder='尝试你的英文表达；阅读题可按题目要求作答。';answer.oninput=()=>draft=answer.value;
   const help=el('input');help.type='checkbox';help.checked=assistance==='assisted';help.onchange=()=>assistance=help.checked?'assisted':'independent';
   if(oralMode){const voice=el('div');voiceCleanup=voicePractice(voice,{onRecording:value=>{recorded=value;},onError:message=>error.textContent=message});parent.append(voice);}
   const actions=el('div',undefined,'row'),send=button('提交这次实际作答',()=>{if(oralMode&&!recorded&&!pending){error.textContent='请先录音并确认转写；文字练习可关闭口语模式。';return;}submit(oralMode?'oral_answer':'answer',current);},'primary');send.disabled=!state.config.enabled;
   actions.append(send,button('给我提示',()=>act({action:'hint',exercise_id:current.id})),button('查看参考答案',()=>act({action:'reveal',exercise_id:current.id})),button('撤回这道题',()=>act({action:'withdraw',exercise_id:current.id})));
   parent.append(field('我的回答',answer),field('这次用了翻译、他人帮助或其他提示',help),actions);
   for(const other of waiting.filter(x=>x.id!==selected).slice(0,5))parent.append(button('接续：'+other.exercise.prompt.slice(0,40),()=>{selected=other.id;draft='';render();}));
  }
  parent.append(el('h3','学习卡与错题'));
  for(const ex of state.exercises.filter(x=>x.assessment).slice(0,20)){
   const a=ex.assessment,box=el('details');
   if(!!a.speech!==oralMode)continue;box.append(el('summary',`${labels[ex.exercise.target.split('.')[0]]||ex.exercise.target} · ${a.disputed?'已提出异议':a.meaning+' / '+a.form+' / '+a.appropriacy} · ${new Date(a.created*1000).toLocaleString()}`));
   box.append(markdown(ex.exercise.prompt),el('p','我的原答：'+a.answer),el('p',a.feedback),el('p','参考表达：'+a.correction),el('p','记忆提示：'+a.memory_cue));
   box.append(el('p',a.hints||a.exposed||a.assistance==='assisted'?'有辅助作答；不计独立表现。':'记录为独立作答；外部辅助依赖本人如实标记。','note'));
   if(a.speech){box.append(el('p','口语转写内容评价；未评发音。录音 '+a.speech.seconds.toFixed(1)+' 秒。'),button('回听原录音',async()=>{try{const r=await post('/api/english-learning',{action:'recording',exercise_id:ex.id});const audio=el('audio');audio.controls=true;audio.src='data:audio/wav;base64,'+r.audio;box.append(audio);}catch(e){error.textContent=e.message;}}));}
   box.append(button('听参考 / 跟读',()=>listen(ex)));
   box.append(button('这次评价不准确',()=>act({action:'dispute',assessment_id:a.id})),button('撤回这条学习记录',()=>act({action:'withdraw',exercise_id:ex.id})));parent.append(box);
  }
  parent.append(el('p','撤回后不再用于学习接续和统计；原聊天仍按聊天记录管理，需要清除时另行删除来源会话。','note'));
  for(const job of state.jobs.filter(x=>x.state!=='RECORDED'))parent.append(el('p',`${job.kind==='question'?'出题':'评价'}：${({PENDING:'处理中或等待核对',UNKNOWN:'结果未知，不自动重试',FAILED:'未完成，可查看原会话错误',INVALIDATED:'来源或设置已变更，结果不采用'})[job.state]||job.state}`,'note'));
  parent.append(error,button('刷新学习记录',load));if(pending)parent.append(button('核对刚才的请求',()=>submit(pending.action)));
  if(state.jobs.some(j=>j.state==='PENDING'))timer=setTimeout(()=>load().catch(e=>{error.textContent=e.message;}),1800);
 }
 await load();return()=>{disposed=true;clearTimeout(timer);voiceCleanup();window.speechSynthesis?.cancel();};
}
