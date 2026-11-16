import {voicePractice} from './english-voice.js';
import {el,button,field,post,markdown} from './ui.js';

const labels={life:'生活交流',communication:'日常沟通',work:'工作资料'};
export async function englishLearningView(parent,{route,ensureChat,refreshChat=async()=>{}}){
 let disposed=false,timer=null,state=null,draft='',material='',domain='auto',assistance='independent',selected=null,pending=null,working=false,recorded=null,voiceCleanup=()=>{},oralMode=false,gameScene='auto',gameSession=null,requestEpoch=0;
 const error=el('p',undefined,'form-error');
 function setBusy(value){parent.setAttribute('aria-busy',String(value));for(const n of parent.querySelectorAll('button,input,select,textarea')){if(value&&!n.disabled){n.disabled=true;n.dataset.englishBusy='true';}else if(!value&&n.dataset.englishBusy){n.disabled=false;delete n.dataset.englishBusy;}}}
 async function load(){if(working){timer=setTimeout(()=>load().catch(e=>error.textContent=e.message),1800);return;}const epoch=requestEpoch;const value=await post('/api/english-learning',{action:'status'});if(!disposed&&!working&&epoch===requestEpoch){state=value;render();}}
 async function act(value){
  if(working)return;requestEpoch++;working=true;setBusy(true);error.textContent='';
  try{state=await post('/api/english-learning',value);if(['game_resume','game_rebind'].includes(value.action)){const s=state.games?.sessions.find(s=>s.id===value.session_id);if(s){gameSession=s.id;selected=s.exercise_id;oralMode=s.mode==='oral';}}if(!disposed)render();await refreshChat();}
  catch(e){error.textContent=e.message;}finally{working=false;setBusy(false);}
 }
 async function submit(kind,ex=null,extra={}){
  if(working)return;requestEpoch++;working=true;setBusy(true);error.textContent='';
  try{
   if(!pending){const chat_id=ex?.chat_id||extra.chat_id||await ensureChat();pending={action:kind,request_id:'english-'+crypto.randomUUID(),chat_id,...route(),...(kind==='game_start'||kind==='game_next'?extra:['start','oral_start'].includes(kind)?{domain,study_text:material}:{exercise_id:ex.id,answer:draft,assistance})};}
   if(kind==='oral_answer'&&!pending.audio_id){const saved=await post('/api/english-learning',{action:'record',audio:recorded});pending.audio_id=saved.recording.id;}
   state=await post('/api/english-learning',pending);if(['game_start','game_next','start','oral_start'].includes(pending.action)){selected=pending.request_id;const session=state.games?.sessions.find(s=>s.exercise_id===selected);if(session)gameSession=session.id;}pending=null;recorded=null;draft='';if(!disposed)render();await refreshChat();
  }catch(e){error.textContent=e.message+'；请求若已受理，不会因再次核对而重复调用模型。';}
  finally{working=false;setBusy(false);}
 }
 async function listenNpc(ex){try{const r=await post('/api/english-learning',{action:'speak_npc',exercise_id:ex.id});if(disposed)return;const audio=el('audio');audio.controls=true;audio.src='data:audio/wav;base64,'+r.audio;parent.append(audio);await audio.play();}catch(e){error.textContent='角色朗读未完成：'+e.message;}}
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
  parent.append(el('h3','独立软件 · 英语城市'));
  const games=state.games;
  if(games?.policy){const enabled=el('input');enabled.type='checkbox';enabled.checked=games.policy.enabled;enabled.onchange=()=>act({action:'software_configure',enabled:enabled.checked,revision:games.policy.revision});parent.append(field('启用独立英语城市软件',enabled));}
  if(games?.due_targets.length)parent.append(el('p','Jarvis建议先复习：'+games.due_targets.map(r=>r.label).join('、')+'；可在下方普通练习选择错题复习。','note'));
  if(games?.available){
   parent.append(el('p','由独立英语城市软件提供剧情，Jarvis管理进度和学习记录。自己说或写来推进；剧情完成与能力掌握分别记录。','note'));
   const scene=el('select');for(const [id,name] of Object.entries({auto:'由Jarvis按复习与覆盖推荐',cafe:'街角咖啡店',arrange:'和朋友改约',work:'同事的新通知'}))scene.add(new Option(name,id));scene.value=gameScene;scene.onchange=()=>gameScene=scene.value;
   const play=button('开始情境游戏',()=>submit('game_start',null,{scene:gameScene==='auto'?games.recommended_scene:gameScene,mode:oralMode?'oral':'text'}),'primary');play.disabled=!state.config.enabled;
   parent.append(field('游戏场景',scene),play,el('p',oralMode?'本轮为口语内容练习：录音后确认转写。':'本轮为自由文字表达，也可勾选口语模式后开始。','note'));
  }else parent.append(el('p','情境软件未安装或未启用；普通英语学习仍可使用。','note'));
  const sessions=games?.sessions||[];
  const chosen=sessions.find(s=>s.id===gameSession)||sessions.find(s=>s.state==='ACTIVE'&&(s.mode==='oral')===oralMode)||sessions[0];
  if(sessions.length){const history=el('details');history.append(el('summary','已保存的剧情（'+sessions.length+'）'));for(const s of sessions)history.append(button(({cafe:'咖啡店',arrange:'改约沟通',work:'工作通知'})[s.scene]+' · '+(s.mode==='oral'?'口语':'文字')+' · '+(s.node+1),()=>{gameSession=s.id;oralMode=s.mode==='oral';selected=s.exercise_id;render();}));parent.append(history);}
  for(const session of chosen?[chosen]:[]){
   const names={cafe:'咖啡店',arrange:'改约沟通',work:'工作通知'},states={ACTIVE:'可继续',PAUSED:'已暂停',COMPLETED:'剧情完成',SOURCE_OR_SOFTWARE_UNAVAILABLE:'来源或软件变更，暂停采用'};
   parent.append(el('p',`${names[session.scene]} · ${session.mode==='oral'?'口语':'文字'} · 回合${session.node+1} · ${states[session.state]||session.state}`));
   if(session.state==='ACTIVE'&&!session.exercise_id)parent.append(button('继续这段剧情',()=>{oralMode=session.mode==='oral';submit('game_next',null,{chat_id:session.chat_id,session_id:session.id,revision:session.revision});}));
   if(session.state==='ACTIVE')parent.append(button('暂停这段剧情',()=>act({action:'game_pause',session_id:session.id,revision:session.revision})));
   if(session.state==='SOURCE_OR_SOFTWARE_UNAVAILABLE'&&games.available&&session.software_build===games.software.build)parent.append(button('核验后接续原进度',()=>act({action:'game_rebind',session_id:session.id,revision:session.revision})));
   if(session.state==='PAUSED')parent.append(button('恢复这段剧情',()=>{oralMode=session.mode==='oral';act({action:'game_resume',session_id:session.id,revision:session.revision});}));
  }
  if(games?.vocabulary_observations.length){const box=el('details');box.append(el('summary','单词与语块的易错观察（AI估计，可异议）'));for(const item of games.vocabulary_observations)box.append(el('p',`${item.word}：原答“${item.quote}”；${item.suggestion}。${item.reason}`));parent.append(box);}
  parent.append(el('h3','普通练习 · 开始 / 接续'));
  const choose=el('select');for(const [key,name] of Object.entries({auto:'按到期复习与新内容选择',...labels,mistakes:'复习错题与辅助作答'}))choose.add(new Option(name,key));choose.value=domain;choose.onchange=()=>domain=choose.value;
  const source=el('textarea');source.rows=3;source.maxLength=4000;source.value=material;source.placeholder='可选：粘贴希望读懂的工作资料；不填则使用标明的教学示例。';source.oninput=()=>material=source.value;
  const start=button('开始下一题',()=>submit(oralMode?'oral_start':'start'),'primary');start.disabled=!state.config.enabled;
  parent.append(field('练习场景',choose),field('本次资料（会发送给所选模型）',source),start);
  const due=(oralMode?state.oral_progress:state.progress).review.filter(x=>x.due_now);parent.append(el('p',`当前到期 ${due.length} 项。未复习不自动扣分；也可先练一个新场景。`,'note'));
  const waiting=state.exercises.filter(x=>!x.assessment&&(x.exercise.practice_mode==='oral')===oralMode&&(!x.exercise.game||state.games.sessions.some(s=>s.id===x.exercise.game.session_id&&s.state==='ACTIVE')));let current=waiting.find(x=>x.id===selected)||waiting[0];if(selected&&state.jobs.some(j=>j.id===selected&&j.state==='PENDING')&&!state.exercises.some(e=>e.id===selected)){current=null;parent.append(el('p','正在准备这一题，先保留原进度。','note'));}
  if(current){
   selected=current.id;parent.append(el('h3',current.exercise.game?'剧情回合 · 自由表达':'待作答'),markdown(current.exercise.prompt));if(current.exercise.game)parent.append(button('听角色说话（不揭示答案）',()=>listenNpc(current)));
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
   if(a.game)box.append(el('p','角色回应：'+a.game.npc_reply),el('p',a.game.transition.passed?'本回合任务条件已满足（不等于掌握）。':'本回合还需澄清：'+a.game.transition.missing.map(k=>a.game.requirements_text?.[k]||k).join('、')));
   box.append(markdown(ex.exercise.prompt),el('p','我的原答：'+a.answer),el('p',a.feedback),el('p','参考表达：'+a.correction),el('p','记忆提示：'+a.memory_cue));
   box.append(el('p',a.hints||a.exposed||a.assistance==='assisted'?'有辅助作答；不计独立表现。':'记录为独立作答；外部辅助依赖本人如实标记。','note'));
   if(a.speech){box.append(el('p','口语转写内容评价；未评发音。录音 '+a.speech.seconds.toFixed(1)+' 秒。'),button('回听原录音',async()=>{try{const r=await post('/api/english-learning',{action:'recording',exercise_id:ex.id});const audio=el('audio');audio.controls=true;audio.src='data:audio/wav;base64,'+r.audio;box.append(audio);}catch(e){error.textContent=e.message;}}));}
   box.append(button('听参考 / 跟读',()=>listen(ex)));
   box.append(button('这次评价不准确',()=>act({action:'dispute',assessment_id:a.id})),button('撤回这条学习记录',()=>act({action:'withdraw',exercise_id:ex.id})));parent.append(box);
  }
  parent.append(el('p','撤回后不再用于学习接续和统计；原聊天仍按聊天记录管理，需要清除时另行删除来源会话。','note'));
  for(const job of state.jobs.filter(x=>x.state!=='RECORDED'))parent.append(el('p',`${job.kind==='question'?'出题':'评价'}：${({PENDING:'处理中或等待核对',UNKNOWN:'结果未知，不自动重试',FAILED:'未完成，可查看原会话错误',INVALIDATED:'来源或设置已变更，结果不采用'})[job.state]||job.state}`,'note'));
  parent.append(error,button('刷新学习记录',load));setBusy(working);if(pending)parent.append(button('核对刚才的请求',()=>submit(pending.action)));
  if(state.jobs.some(j=>j.state==='PENDING'))timer=setTimeout(()=>load().catch(e=>{error.textContent=e.message;}),1800);
 }
 await load();return()=>{disposed=true;clearTimeout(timer);voiceCleanup();window.speechSynthesis?.cancel();};
}
