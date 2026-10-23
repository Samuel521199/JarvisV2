import {el,button,field,input,post,modal,closeModal,notice,card,errorText} from './ui.js';
import {routeChoice,openDevelopment} from './development.js';

const labels={NEW:'等待起草',DRAFTING:'正在设计规格',REVIEW:'规格待核对',NEEDS_INPUT:'仍有待解决问题',WAITING:'等待接续',DEVELOPING:'研发已关联',REJOINED:'已返回原目标',CANCELLED:'已取消'};

export function renderGoalGrowth(parent,data,settings,changed){
 const p=data.plan,g=data.growth;
 async function start(mode,retry=false){await post('/api/goal-growth/run',{id:p.id,mode,retry_unknown:retry});await changed();}
 if(!g){if(!p.cancel&&p.status==='NEEDS_INPUT'&&!p.planning_round&&!data.task){const c=card('现有能力不够时，让 Jarvis 设计新能力','先提出规格与用例，再核对、编程、检查和发布。当前仅支持纯文本处理。');c.append(button('为这个目标设计能力',async()=>{await post('/api/goal-growth',{action:'prepare',id:p.id,revision:p.revision});await changed();try{await start('draft');}catch(e){notice(e.message+' 申请已保存，可稍后接续。');}},'primary'));parent.append(c);}return;}
 const c=card('这个目标的能力成长',labels[g.status]||g.status),steps=el('div',undefined,'growth-steps');
 for(const [name,yes] of [['发现缺口',true],['规格核对',!!g.draft],['编码与检查',!!g.development_id],['候选审阅',!!g.development?.release_id],['返回原目标',g.status==='REJOINED'],['目标交付',data.task?.status==='SUCCEEDED']])steps.append(el('span',name,yes?'reached':''));c.append(steps);
 if(g.error)c.append(el('p',errorText(g.error),'form-error'));
 if(g.draft){c.append(el('p',g.draft.summary));for(const q of g.draft.questions)c.append(el('p',q,'note'));}
 if(!p.cancel&&!g.development_id&&['NEW','WAITING'].includes(g.status))c.append(button(g.error==='model_unknown'?'确认可能重复计费，重新起草':'开始 / 接续规格设计',()=>start('draft',g.error==='model_unknown')));
 if(!p.cancel&&!g.development_id&&['NEW','WAITING','REVIEW','NEEDS_INPUT'].includes(g.status))c.append(button('查看 / 修改规格与用例',()=>edit(false)));
 if(!p.cancel&&g.status==='REVIEW')c.append(button('核对规格并开始研发',()=>edit(true),'primary'));
 if(g.development_id){const d=g.development;c.append(el('p','研发状态：'+d.status+' · '+d.phase+(d.error?' · '+errorText(d.error):''),'note'),button('研发进度、源码与审阅发布',()=>openDevelopment(g.development_id,changed)));
  if(!p.cancel&&g.status!=='REJOINED'&&d.status==='SUCCEEDED')c.append(button('回到原目标继续规划',()=>start('rejoin'),'primary'));
  if(['FAILED','CANCELLED'].includes(d.status))c.append(el('p','本次研发已结束，不自动重置预算或重复创建。可以核对原因后补充目标，另建计划。','note'));
 }
 if(g.status==='REJOINED')c.append(el('p','新能力已经纳入原目标。下面的计划仍需核对并确认执行；研发样本成功不等于原目标已经完成。','note'));
 parent.append(c);

 function casesEditor(title,cases){
  const box=el('fieldset'),list=el('div');box.append(el('legend',title),list);const values=structuredClone(cases);
  function draw(){list.replaceChildren();for(const [i,v] of values.entries()){const row=el('div',undefined,'goal-case'),text=el('textarea'),expected=el('textarea');text.rows=expected.rows=2;text.maxLength=expected.maxLength=4000;text.value=v.input;expected.value=v.expected;text.oninput=()=>v.input=text.value;expected.oninput=()=>v.expected=expected.value;row.append(field('输入 '+(i+1),text),field('预期输出 '+(i+1),expected),button('移除此用例',()=>{values.splice(i,1);draw();}));list.append(row);}const add=button('+ 添加用例',()=>{values.push({input:'',expected:''});draw();});add.disabled=values.length>=6;list.append(add);}draw();return {node:box,value:()=>values};
 }
 function edit(begin){
  const draft=g.draft||{schema:'jarvis.capability-draft.v1',supported:false,summary:'',description:'',public_cases:[],evaluation_cases:[],questions:[]},b=modal(begin?'核对后启动此目标的研发':'编辑能力规格'),form=el('form'),summary=el('textarea'),description=el('textarea'),questions=el('textarea'),supported=input(''),reviewed=input(''),error=el('p',undefined,'form-error'),submit=el('button',begin?'保存并开始受限研发':'保存规格','primary');
  summary.value=draft.summary;summary.maxLength=2000;summary.rows=2;description.value=draft.description;description.maxLength=4000;description.rows=5;questions.value=draft.questions.join('\n');questions.rows=2;supported.type=reviewed.type='checkbox';supported.checked=draft.supported;reviewed.required=begin;
  const pub=casesEditor('公开示例 · 发给规划和编码模型',draft.public_cases),held=casesEditor('隔离验收用例 · 不发给后续规划和编码模型',draft.evaluation_cases);
  form.append(field('能力说明',summary),field('精确行为、边界与输出格式',description),field('目标可由纯文本工具完整完成',supported),pub.node,held.node,field('未解决问题（每行一项）',questions),el('p','这些期望可能由规格模型提出。请核对或修正；独立运行测试不能证明测试标准本身正确。两组输入不能重复。研发仅用公开示例，样本交付不替代原目标交付。','note'));
  let routes,limits;
  if(begin){const rp=routeChoice(settings,'研发规划 · 首选'),rb=routeChoice(settings,'研发规划 · 备选',true),cp=routeChoice(settings,'编码 · 首选'),cb=routeChoice(settings,'编码 · 备选',true),calls=input('4'),attempts=input('2'),seconds=input('1800');
   for(const [n,min,max] of [[calls,2,8],[attempts,1,3],[seconds,30,1800]]){n.type='number';n.min=min;n.max=max;n.required=true;}
   form.append(rp.node,rb.node,cp.node,cb.node,field('最多模型调用',calls),field('最多候选轮次',attempts),field('时限 / 秒（包含审阅等待）',seconds),field('我已核对行为与用例，允许本次研发及发布后返回原目标重新规划',reviewed));
   routes=()=>({plan:[rp.value(),rb.value()].filter(Boolean),code:[cp.value(),cb.value()].filter(Boolean)});limits=()=>({max_model_calls:Number(calls.value),max_attempts:Number(attempts.value),max_seconds:Number(seconds.value)});
   form.append(el('p','发布后最多再调用 2 次原目标规划模型，生成新计划待核对；不会自动执行原目标，也不会安装依赖、修改核心或调用桌面。','note'));
  }
  form.append(error,submit);submit.type='submit';form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{
   const saved=await post('/api/goal-growth',{action:'edit',id:p.id,revision:g.revision,draft:{...draft,summary:summary.value,description:description.value,supported:supported.checked,public_cases:pub.value(),evaluation_cases:held.value(),questions:questions.value.split('\n').map(x=>x.trim()).filter(Boolean)}});g.revision=saved.revision;g.draft=saved.draft;
   if(begin){const accepted=await post('/api/goal-growth',{action:'begin',id:p.id,revision:saved.revision,acceptance_reviewed:reviewed.checked,routes:routes(),limits:limits()});closeModal();await changed();try{await post('/api/development-runner',{id:accepted.development_id,network_enabled:true,retry_unknown:false});}catch(e){notice(e.message+' 研发已保存，请在进度中继续。');}}else closeModal();await changed();
  }catch(e){error.textContent=e.message;}finally{submit.disabled=false;}};b.append(form);
 }
}
