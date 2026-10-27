import {el,button,link,input,field,get,post,run,notice,modal,closeModal,card,details,download,errorText} from './ui.js';

const taskLabels={READY:'待执行',RUNNING:'执行中',WAITING:'等待接续',SUCCEEDED:'已完成',FAILED:'失败',CANCELLED:'已取消'};
const terminal=new Set(['SUCCEEDED','FAILED','CANCELLED']);
const packageLabels={CANARY:'灰度观察',STABLE:'基础观察已通过',REJECTED:'已隔离',RETIRED:'已退役'};

export function toolsView(parent,{attach=null}={}){
 const mount=el('section',undefined,'tools-workspace'),intro=card('本地工具','已发布的能力可以重复使用。输入和结果保存在本机，本次执行不调用模型。'),toolbar=el('div',undefined,'row'),search=input('','搜索工具或用途…'),list=el('div',undefined,'grid'),history=el('div'),detail=el('div',undefined,'tool-detail'),status=el('p',undefined,'note');
 let disposed=false,loading=false,selected=null,lastList='',data={items:[],recent:[]};
 search.type='search';search.setAttribute('aria-label','搜索本地工具');toolbar.append(search,button('刷新工具',load),link('创建新能力 →','/settings#coding'));intro.append(el('p','当前范围：个人纯文本工具。文字技能为模型提供方法；MCP 仍是独立的接入登记。','note'));mount.append(intro,toolbar,status,list,detail,el('h3','最近使用'),history);parent.append(mount);
 function render(){
  lastList=JSON.stringify(data);list.replaceChildren();const items=data.items.filter(t=>(t.name+t.capability+t.description).toLowerCase().includes(search.value.toLowerCase()));
  if(!items.length)list.append(el('p',data.items.length?'没有匹配的工具。':'还没有已发布工具。完成编码协作中的候选检查与发布后，会自动出现在这里。','empty'));
  for(const t of items){const c=card(t.name,t.description);c.classList.add('tool-card');c.prepend(el('span',!t.enabled?'已停用':packageLabels[t.status]||t.status,'badge'));c.append(el('p',t.capability,'mono'),el('p','版本 '+t.active.slice(4,16)+' · 已完成 '+t.observations+' 次运行','note'));if(t.error)c.append(el('p',errorText(t.error),'form-error'));const actions=el('div',undefined,'row'),use=button('使用工具',()=>useTool(t),'primary');use.disabled=!t.available;actions.append(use);
   if(!t.error&&['CANARY','STABLE'].includes(t.status))actions.append(button(t.enabled?'停用':'检查并恢复',async()=>{await post('/api/operations',{action:'release',operation:t.enabled?'disable':'activate',id:t.enabled?t.capability:t.active,revision:t.revision});await load();}));
   actions.append(button('版本与边界',()=>details(t.name,{能力:t.capability,包:t.active,上一版本:t.previous,状态:t.status,启用:!!t.enabled,范围:t.scope,边界:'仅文本输入输出；Windows 受限 Worker，无网络，无桌面或任意文件权限。两次运行只代表基础观察，不证明所有输入正确。'})));c.append(actions);list.append(c);
  }
  history.replaceChildren();for(const t of data.recent){const c=el('div',undefined,'tool-history-row');c.append(el('div',t.capability),el('span',taskLabels[t.status]||t.status,'badge'),button('输入与结果',()=>show(t.id)));history.append(c);}if(!data.recent.length)history.append(el('p','还没有使用记录。','empty'));
 }
 async function load(){if(loading||disposed)return;loading=true;try{const [next,runner]=await Promise.all([get('/api/tools'),get('/api/task-runner')]);if(disposed||!mount.isConnected)return;data=next;status.textContent=runner.status==='running'?'后台任务正在执行，聊天仍可继续。':runner.status==='failed'?'上次启动未完成：'+errorText(runner.error)+'；任务输入已保留，可查看后继续。':'按需执行；关闭面板不取消任务。';if(lastList!==JSON.stringify(data))render();if(selected)await show(selected,false);}finally{loading=false;}}
 async function start(id){await post('/api/tools/run',{id});notice('工具任务已启动；你可以继续聊天。');await show(id);await load();}
 function useTool(t){
  const b=modal('使用 · '+t.name),form=el('form'),text=el('textarea'),error=el('p',undefined,'form-error'),submit=el('button','运行本地工具','primary');let request=crypto.randomUUID();text.rows=8;text.maxLength=50000;text.setAttribute('aria-label','工具输入');text.placeholder='输入要处理的文本…';text.addEventListener('input',()=>{request=crypto.randomUUID();});submit.type='submit';
  form.append(el('p',t.description),field('输入文本',text),button('填入示例',()=>{text.value=t.sample_input;request=crypto.randomUUID();}),el('p','只授权这一次文本处理和结果文件。最多 2 个动作、10 分钟有效期；不联网、不消耗模型 token。输入与结果留在本机任务账本。','note'),error,submit);
  form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;text.disabled=true;try{const created=await post('/api/tools',{action:'submit',request_id:request,capability:t.capability,package_id:t.active,revision:t.revision,text:text.value});closeModal();await show(created.id);try{await start(created.id);}catch(e){notice(e.message+' 输入已保存，可在结果面板继续。');await load();}}catch(e){error.textContent=e.message;}finally{submit.disabled=false;text.disabled=false;}};b.append(form);
 }
 async function show(id,scroll=true){
  if(scroll)selected=id;const d=await post('/api/tools',{action:'detail',id});if(disposed||selected!==id)return;const signature=JSON.stringify(d);if(detail.dataset.signature===signature){if(scroll)detail.scrollIntoView({block:'nearest'});return;}detail.dataset.signature=signature;const t=d.task,unknown=d.actions.some(a=>a.status==='UNKNOWN'),used=d.actions.find(a=>a.step_id==='use'&&a.status==='CONFIRMED'),delivery=d.actions.find(a=>a.step_id==='deliver'&&a.status==='CONFIRMED');detail.replaceChildren();
  const head=el('div',undefined,'row');head.append(el('h3','本次工具任务'),el('span',taskLabels[t.status]||t.status,'badge'),button('收起结果',()=>{selected=null;delete detail.dataset.signature;detail.replaceChildren();}));detail.append(head,el('p',t.body.steps[0].capability+' · '+t.id,'note'));if(t.error)detail.append(el('p',errorText(t.error),'form-error'));
  const source=el('details');source.append(el('summary','查看本次输入'),el('pre',t.body.steps[0].arguments.text));detail.append(source);
  if(used&&typeof used.result?.text==='string'){const out=used.result.text;detail.append(el('h4',t.status==='SUCCEEDED'?'实际输出':'已取得输出 · 交付尚未完成'),el('pre',out,'tool-output'));const row=el('div',undefined,'row');row.append(button('复制结果',()=>navigator.clipboard.writeText(out)),button('导出文本',()=>download('jarvis-tool-result.txt',out)));if(attach)row.append(button('附入当前聊天',()=>{attach({name:t.body.steps[0].capability+'.txt',text:out});notice('已作为可见附件加入输入框，发送后才会提供给聊天模型。');}));detail.append(row);}
  if(delivery)detail.append(el('p','结果已写入本机产物目录；可在执行回执中查看路径与摘要。','note'));
  const actions=el('div',undefined,'row');actions.append(button('刷新结果',()=>show(id)));if(['READY','WAITING'].includes(t.status)&&!t.cancel&&!unknown)actions.append(button(t.status==='READY'?'开始此任务':'接续此任务',()=>start(id),'primary'));if(unknown)actions.append(button('核对已保存回执',async()=>{await post('/api/tools',{action:'reconcile',id});await show(id);await load();}));if(!terminal.has(t.status))actions.append(button('取消本次任务',async()=>{await post('/api/tools',{action:'cancel',id});await show(id);await load();}));actions.append(button('查看执行回执',()=>details('版本、权限与执行回执',d)));detail.append(actions);
  if(unknown)detail.append(el('p','结果未知时不会自动重跑。先核对本机回执；缺少回执时可以取消，重新明确发起一次文本处理。','note'));if(scroll)detail.scrollIntoView({block:'nearest',behavior:'smooth'});
 }
 search.oninput=render;run(load);const timer=setInterval(()=>{if(!document.hidden&&mount.isConnected)run(load);},3000);return()=>{disposed=true;clearInterval(timer);};
}
