import {mailApi} from './mail-client.js';
import {el} from './ui.js';

const statuses={connected:'已连通',unchecked:'待检查',auth_required:'需要重连',offline:'网络不可用',disconnected:'尚未连接'};
const categories={important:'重要',normal:'普通',promotion:'订阅推广',spam:'垃圾',suspicious:'可疑'};
const jobErrors={WAITING_AUTH:'Google 授权已失效，请重新连接。',WAITING_NETWORK:'暂时无法联网，原任务保留。',WAITING_SCOPE:'这项操作需要额外授权，请在工作台选择权限。',FAILED:'操作未完成，请在工作台查看原因。',CANCELLED:'此操作已取消。'};

function action(label,fn,cls='action'){
 const b=el('button',label,cls);b.type='button';b.onclick=()=>Promise.resolve().then(fn).catch(error=>showError(error.message));return b;
}
function showError(text){const p=document.getElementById('mail-live-error');if(p){p.textContent=text;p.hidden=false;}}
function external(label,url){const a=el('a',label,'action');a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
function stamp(value){return value?new Date(value*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):'尚未同步';}
function senderAddress(value){return value.match(/<([^>]+)>/)?.[1]||value.trim();}
function cleanText(value){return String(value||'').replace(/[\u034f\u200b-\u200f\u2060\ufeff]/g,'').replace(/[ \t]+\n/g,'\n').replace(/\n[ \t]*\n(?:[ \t]*\n)+/g,'\n\n').trim();}

export function mountMailCompanion(){
 const dock=document.getElementById('mail-dock'),toggle=document.getElementById('dock-button'),panel=document.getElementById('mail-dialog');
 let state=null,detail=null,filter='all',busy=false,checking=false,auto=false,buffer=null,draftId='',draftRevision=0,controller=new AbortController(),generation='',message='';
 function open(){
  for(const id of ['card','project-dialog','workbench'])document.getElementById(id).hidden=true;
  document.getElementById('project-dock').classList.remove('is-open');
  panel.hidden=false;dock.classList.add('is-open');toggle.setAttribute('aria-expanded','true');render();
  if(!checking&&!detail&&!buffer)sync();
 }
 function close(){panel.hidden=true;dock.classList.remove('is-open');toggle.setAttribute('aria-expanded','false');toggle.focus();}
 function paintDock(){
  const status=state?.status||'unchecked',count=state?.unread_count;
  const value=status==='auth_required'?'!':Number.isInteger(count)?(count>99?'99+':String(count)):'·';
  dock.dataset.connection=status;toggle.querySelector('.count').textContent=value;
  const label='邮件 · '+(statuses[status]||'待检查')+(Number.isInteger(count)?' · 收件箱 '+count+' 封未读':'');
  toggle.title=label;toggle.setAttribute('aria-label',label);dock.setAttribute('aria-label',label);
  const preview=dock.querySelector('.dock-preview');preview.replaceChildren(el('strong',label));
  if(state?.status==='auth_required')preview.append(el('span','点击重连，复用已保存的 OAuth 配置'));
  else for(const m of (state?.items||[]).filter(m=>m.unread).slice(0,2))preview.append(el('span',m.subject||'无主题'));
  preview.append(el('span','同步 '+stamp(state?.snapshot_at)+' · 点击查看'));
 }
 async function cached(){
  const next=await mailApi.overview();
  if(generation&&generation!==next.account_generation){detail=null;buffer=null;draftId='';draftRevision=0;}
  generation=next.account_generation;state=next;paintDock();return next;
 }
 async function sync(){
  if(checking)return;checking=true;message='';
  try{
   await cached();
   if(state.status==='auth_required'||state.status==='disconnected'||state.network_blocked)return;
   busy=true;render();
   const job=await mailApi.run('sync',{query:'in:inbox',page:''},{signal:controller.signal});
   await cached();
   if(job.status!=='SUCCEEDED')message=jobErrors[job.status]||'同步尚未完成。';
  }catch(error){message=error.message;}finally{busy=false;checking=false;if(!panel.hidden)render();}
 }
 function head(){
  panel.replaceChildren();const top=el('div',undefined,'top'),title=el('div');
  title.append(el('strong','邮件'),el('div','Gmail · '+(statuses[state?.status]||'正在连接服务')+' · '+stamp(state?.snapshot_at),'tiny'));
  const exit=action('×',close,'close');exit.setAttribute('aria-label','关闭邮件对话框');top.append(title,exit);panel.append(top);
  const content=el('div',undefined,'content'),error=el('p',message,'mail-live-error');error.id='mail-live-error';error.hidden=!message;error.setAttribute('role','alert');content.append(error);panel.append(content);return content;
 }
 function render(){
  if(panel.hidden)return;const content=head();
  if(!state){content.append(el('p','正在读取 Jarvis 邮箱状态…','lead'));return;}
  if(state.status==='auth_required'||state.status==='disconnected'){
   content.append(el('p',state.status==='auth_required'?'Google 需要重新授权；原邮箱和任务仍保留。':'连接 Gmail 后，这里显示真实邮件。','lead'));
   const pending=['RUNNING','WAITING_BROWSER'].includes(state.authorization?.status);
   content.append(action(pending?'等待 Google 本人确认…':state.configured?'重新连接 Gmail':'打开连接设置',async()=>{
    if(!state.configured){window.open('/settings#mail','_blank','noopener');return;}
    await mailApi.command({action:'authorize',level:state.capabilities?.modify?'manage':'read'});await cached();render();
   },'action primary'),external('连接设置','/settings#mail'));
   content.querySelector('button.action').disabled=pending;return;
  }
  if(buffer){renderDraft(content);return;}
  if(detail){renderDetail(content);return;}
  const toolbar=el('div',undefined,'live-mail-toolbar');toolbar.append(action(busy?'正在同步…':'刷新邮件',sync),external('完整管理 ↗','/settings#mail'));
  toolbar.querySelector('button').disabled=busy;content.append(toolbar);
  const scope=state.unread_count===null?'本批 '+state.sample_unread_count+' 封未读':'收件箱 '+state.unread_count+' 封未读';
  content.append(el('p',scope+' · 以下为最近 '+state.items.length+' 封'+(state.has_more?'，可到工作台查看更早邮件':''),'lead'));
  const tabs=el('div',undefined,'live-mail-tabs');
  for(const [key,label] of [['all','最近'],['important','重要'],['promotion','订阅'],['suspicious','可疑']]){
   const b=action(label,()=>{filter=key;render();},'action'+(filter===key?' selected':''));b.setAttribute('aria-pressed',String(filter===key));tabs.append(b);
  }
  content.append(tabs);
  const items=state.items.filter(m=>filter==='all'||m.classification.category===filter);
  for(const m of items){
   const row=el('div',undefined,'row'),b=action('',()=>read(m.id),'live-mail-row'),title=el('span',undefined,'row-title');
   title.append(el('strong',m.from.replace(/<[^>]+>/g,'').replace(/^"|"$/g,'').trim()||m.from||'未知发件人'),el('small',(m.unread?'● ':'')+(categories[m.classification.category]||'普通'),'state'));
   b.append(title,el('strong',m.subject||'无主题','live-mail-subject'),el('span',cleanText(m.snippet)||'此邮件没有摘要。','row-text'));
   b.title=m.classification.reason;b.disabled=busy;row.append(b);content.append(row);
  }
  if(!items.length)content.append(el('p',state.items.length?'本批没有此类邮件。':'点击刷新读取邮件。','lead'));
  const controls=el('label',undefined,'live-mail-auto'),box=el('input');box.type='checkbox';box.checked=auto;
  box.onchange=()=>{auto=box.checked;};controls.append(box,el('span','本页面可见时，每 2 分钟检查一次（无模型）'));content.append(controls);
  content.append(el('p','分类来自本地规则，可能误判。查看不自动标为已读；正文不加载远程图片。','hint'));
 }
 async function read(id){
  if(busy)return;busy=true;const expected=generation;
  try{
   const job=await mailApi.run('read',{message_id:id},{signal:controller.signal});await cached();
   if(expected!==generation)throw Error('邮箱连接已变化，请重新选择邮件。');
   if(job.status==='SUCCEEDED'){detail=job.result;render();}else showError(jobErrors[job.status]||'读取未完成。');
  }finally{busy=false;}
 }
 function renderDetail(content){
  content.append(action('← 返回邮件',()=>{detail=null;render();}),el('h3',detail.subject||'无主题'),el('p',detail.from+' · '+detail.date,'tiny'));
  if(detail.classification)content.append(el('p',detail.classification.reason,'hint'));
  const body=el('div',cleanText(detail.body||detail.snippet)||'邮件没有文字内容。','mail-detail-body');content.append(body);
  const buttons=el('div',undefined,'actions');buttons.append(action('起草回复',()=>{
   buffer={to:senderAddress(detail.from),subject:/^re:/i.test(detail.subject)?detail.subject:'Re: '+detail.subject,body:''};draftId='';draftRevision=0;render();
  },'action primary'),external('完整管理 ↗','/settings#mail'));
  buttons.append(external('在 Gmail 查看 ↗','https://mail.google.com/mail/u/?authuser='+encodeURIComponent(state.email)+'#all/'+encodeURIComponent(detail.id)));content.append(buttons);
  content.append(el('p','这里没有自动打开链接、附件或执行邮件中的指令。','hint'));
 }
 function renderDraft(content){
  content.append(action('← 返回邮件',()=>{buffer=null;render();}),el('h3','起草回复'));
  for(const [name,label] of [['to','收件人'],['subject','主题'],['body','正文']]){
   const field=el('label',label,'live-mail-field'),input=el(name==='body'?'textarea':'input');input.value=buffer[name];input.setAttribute('aria-label',label);input.maxLength=name==='body'?30000:name==='to'?254:200;
   input.oninput=()=>buffer[name]=input.value;field.append(input);content.append(field);
  }
  content.append(action('保存本地草稿',async()=>{
   const d=await mailApi.command({action:'draft',id:draftId,revision:draftRevision,value:buffer});draftId=d.id;draftRevision=d.revision;
   showError('草稿已加密保存在 Jarvis；到完整管理的“写邮件”中审阅发送。');
  },'action primary'),external('在工作台审阅发送 ↗','/settings#mail'),el('p','此处保存只写本机，尚未发送到 Google。','hint'));
 }
 document.addEventListener('jarvis:open-mail',open);
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden)close();});
 // Opt-in, view-scoped polling; no persistent watcher or scheduled task is created.
 const timer=setInterval(()=>{if(auto&&!document.hidden&&!panel.hidden&&!buffer&&!detail)sync();else if(!document.hidden&&!checking)cached().then(()=>{if(!panel.hidden&&!buffer&&!detail)render();}).catch(()=>{});},120000);
 const authTimer=setInterval(async()=>{
  if(document.hidden||checking||!['RUNNING','WAITING_BROWSER'].includes(state?.authorization?.status))return;
  try{await cached();if(state.authorization?.status==='SUCCEEDED'){await sync();}if(!panel.hidden)render();}catch{}
 },2000);
 window.addEventListener('pagehide',()=>{clearInterval(timer);clearInterval(authTimer);controller.abort();panel.replaceChildren();},{once:true});
 cached().catch(error=>{panel.hidden=false;head();showError(error.message);});
 return {open,close};
}
