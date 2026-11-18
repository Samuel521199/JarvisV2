import {mountModel} from './model-library-embed.js';
import {registerWorkspaceEditor,workspaceMutation,workspaceChanged,selectWorkspaceChat} from './workspace-events.js';
import {conversationMenu} from './workspace-menus.js';
import {foldWorkbench} from './presentation.js';
import {conversationGroups} from './conversation-groups.js';
import {surfaceIntent} from './surface-intent.js';
import {watchReply} from './work-client.js';
import {observeNativeUpdate,savePresentationState,takePresentationState} from './native-upgrade.js';
import {basisEditor,deliveryReviewView} from './delivery-review.js';
import {workStatusView} from './work-status.js';
import {mailboxView,updateMailIndicator,mailIntent} from './mailbox.js';
import {$,el,button,iconButton,icon,link,field,input,get,post,run,notice,modal,closeModal,contextMenu,confirmAction,details,download,initModal,applyPreferences,savePreferences,splitters,states,errorText,markdown} from './ui.js';
import {ModelPicker} from './model-picker.js';
import {Projects} from './projects.js';
import {SessionFolders} from './session-folders.js';
const compact=location.pathname==='/conversation';
if(compact)document.documentElement.classList.add('conversation-surface');
const sessionFolders=new SessionFolders();
import {memoryView,retrievalLabel} from './memory.js';
import {toolsView} from './tools.js';
import {speechTranscriber,speechOutput} from './speech-input.js';
import {microphone,audioBase64} from './speech-recorder.js';
import {englishLearningView} from './english-learning.js';
import {goalsView} from './goals.js';
import {actionCard} from './assistant-actions.js';
import {brandState,cinema,enterCinema,setSound,unlockSound,soundState} from './brand.js';
import {projectBrand,brandLabels} from './brand-state.js';
const restoredPresentation=takePresentationState();
let connected=true,away=false,presentationVisible=restoredPresentation.visible!==false;
function captureConversation(){
 return {visible:presentationVisible,nav:!document.body.classList.contains('nav-hidden'),
  scroll:$('messages').scrollTop,selection:[$('message').selectionStart,$('message').selectionEnd],
  focused:document.activeElement===$('message'),chat:chatId};
}
function restoreConversation(){
 if(restoredPresentation.chat!==chatId)return;
 if(restoredPresentation.nav===true)workspaceVisibility(true,false);
 if(Number.isFinite(restoredPresentation.scroll))$('messages').scrollTop=restoredPresentation.scroll;
 if(Array.isArray(restoredPresentation.selection)&&restoredPresentation.selection.length===2)
  $('message').setSelectionRange(...restoredPresentation.selection);
 if(restoredPresentation.focused&&presentationVisible&&document.hasFocus())$('message').focus({preventScroll:true});
}
function syncBrand(){const state=projectBrand({connected,away,control:snapshot?.status.control||'ready',pending:busy,turns:chat?.turns||[]});brandState(state);const readout=$('brand-readout');if(readout)readout.textContent=brandLabels[state];const control=$('core-state');if(control){control.dataset.status=connected?snapshot?.status.control:'offline';control.setAttribute('aria-label','工作状态与资源');control.dataset.tooltip='工作状态与资源';}}
document.addEventListener('jarvis-cinema',e=>{away=!!e.detail?.away;syncBrand();});
let snapshot,skills=[],chats=[],projects=[],chat=null,chatId=null,projectId='',picker,busy=false,active=null,lastTurns='',polling=false;
const drafts=new Map(),transitioningChats=new Set();let attachments=[];
const deliveryEditor=basisEditor($('basis-anchor'),()=>remember());
function remember(){drafts.set(chatId||'new:'+projectId,{delivery_basis:deliveryEditor.value(),text:$('message').value,requirements:$('requirements').value,skill:$('skill').value,enabled:$('skills-enabled').checked,attachments:[...attachments],memory:$('memory-enabled')?.checked!==false,selection:picker?{...picker.selection}:null,reasoning:$('reasoning').value,mode:$('message-mode').value});if(chatId&&!transitioningChats.has(chatId)&&!chat?.archived&&!chat?.removed&&!projects.find(p=>p.id===projectId)?.removed)sessionFolders.remember(chatId,drafts.get(chatId));}
function restore(){const d=drafts.get(chatId||'new:'+projectId)||sessionFolders.adopt(chat)||{};deliveryEditor.restore(d.delivery_basis,chat);$('message-mode').value=d.mode||'auto';$('message').value=d.text||'';$('requirements').value=d.requirements||'';$('requirements-state').textContent=d.requirements?'已设置':'未设置';$('skill').value=d.skill||'auto';$('skills-enabled').checked=d.enabled!==false;attachments=d.attachments||[];if(d.selection&&picker){picker.selection=d.selection;picker.refresh();$('reasoning').value=d.reasoning||'default';}if($('memory-enabled'))$('memory-enabled').checked=d.memory===undefined?chat?.memory_enabled!==0:d.memory!==false;renderAttachments();}
let panelCleanup=()=>{};
function panel(title){if(document.body.classList.contains('mobile-nav')&&(innerWidth<=700||compact))workspaceVisibility(false);panelCleanup();panelCleanup=()=>{};$('panel-title').textContent=title;$('inspector').hidden=false;$('right-divider').hidden=false;$('panel-content').replaceChildren();return $('panel-content');}
const projectUI=new Projects({panel,refresh:async()=>{workspaceChanged();await refreshLists();},hideChats:hideChats,newChat:p=>newChat(p.id),selectProject:async p=>{clearVoice();remember();projectId=p.id;chatId=null;chat=null;lastTurns='';restore();render();await projectUI.explorer(p);},attach:addAttachment});
function selectedProject(){return projects.find(p=>p.id===projectId&&!p.removed);}
async function refreshLists(){[projects,chats]=await Promise.all([get('/api/projects'),get('/api/chats')]);if(chatId){const item=chats.find(c=>c.id===chatId);if(item){chat={...chat,...item};projectId=item.project_id;}}renderSidebar();updateContext();if(picker)renderMessages();}
function chatRow(item){
 const row=el('div',undefined,'chat-row'+(item.id===chatId?' active':''));row.dataset.chatId=item.id;
 const choose=button(item.title,()=>switchChat(item));choose.title=item.title;choose.classList.add('chat-choice');if(item.pinned)choose.prepend(icon('pin'));if(item.id===chatId)choose.setAttribute('aria-current','page');
 const menu=iconButton('more','会话菜单：'+item.title,()=>chatMenu(item,menu));menu.setAttribute('aria-haspopup','menu');menu.setAttribute('aria-expanded','false');row.append(choose,menu);row.addEventListener('contextmenu',e=>{e.preventDefault();chatMenu(item,menu);});return row;
}
const sidebarUiVersion='1.1.0',sidebarStorageKey='jarvis.sidebar.v1',independentKey='$independent';
const collapsedProjects=new Set(),visibleCounts=new Map();
try{const saved=JSON.parse(localStorage.getItem(sidebarStorageKey)||'{}');if(Array.isArray(saved.collapsed))for(const id of saved.collapsed.slice(0,2000))if(typeof id==='string'&&id.length<100)collapsedProjects.add(id);}catch{}
function saveSidebar(){try{localStorage.setItem(sidebarStorageKey,JSON.stringify({collapsed:[...collapsedProjects].slice(0,2000)}));}catch{notice('当前浏览器无法保存折叠偏好，本页仍可正常使用。');}}
function toggleGroup(key){if(collapsedProjects.has(key))collapsedProjects.delete(key);else collapsedProjects.add(key);saveSidebar();renderSidebar();Array.from(document.querySelectorAll('[data-collapse-key]')).find(b=>b.dataset.collapseKey===key)?.focus();}
function groupToggle(key,name,count,kind,listId){const b=button('',()=>toggleGroup(key),'sidebar-group-toggle');b.dataset.collapseKey=key;b.setAttribute('aria-expanded',String(!collapsedProjects.has(key)));b.setAttribute('aria-controls',listId);b.setAttribute('aria-label',(collapsedProjects.has(key)?'展开':'折叠')+name+'，'+count+' 个会话');b.append(icon('chevron'),icon(kind),el('span',name,'project-name'),el('span',String(count),'sidebar-count'));return b;}
function appendChats(list,items,key,limit){const size=visibleCounts.get(key)||limit;for(const c of items.slice(0,size))list.append(chatRow(c));if(items.length>size)list.append(button('显示更多（还有 '+(items.length-size)+' 个）',()=>{visibleCounts.set(key,size+limit);renderSidebar();},'sidebar-more'));if(size>limit&&items.length>limit)list.append(button('收起更多会话',()=>{visibleCounts.delete(key);renderSidebar();},'sidebar-more'));}
function renderSidebar(){
 const pList=$('project-list'),cList=$('chat-list');pList.replaceChildren();cList.replaceChildren();
 const groups=conversationGroups(projects,chats),visible=groups.filter(g=>g.project).map(g=>g.project),independent=groups.find(g=>g.id==='$independent').chats;
 $('navigation').dataset.sidebarUi=sidebarUiVersion;
 const controls=$('sidebar-controls');if(!controls.children.length){controls.append(el('span','项目与会话'),iconButton('collapseRows','折叠全部项目与独立会话',()=>{for(const p of projects.filter(p=>!p.removed))collapsedProjects.add(p.id);collapsedProjects.add(independentKey);saveSidebar();renderSidebar();}),iconButton('expandRows','展开全部项目与独立会话',()=>{collapsedProjects.clear();saveSidebar();renderSidebar();}));}
 const independentHeading=$('independent-heading');independentHeading.hidden=false;independentHeading.replaceChildren(groupToggle(independentKey,'独立会话',independent.length,'chat','chat-list'),iconButton('plus','新建独立会话',()=>newChat()));
 if(!visible.length)pList.append(el('p','打开文件夹，开始一个项目','note'));
 let section=null;
 for(const p of visible){
  if(p.section&&p.section!==section){section=p.section;pList.append(el('div',section,'section-heading'));}
  const group=el('section',undefined,'project-group'),row=el('div',undefined,'project-row'),list=el('div',undefined,'project-chats');list.id='chats-'+p.id;group.dataset.projectId=p.id;
  const expanded=!collapsedProjects.has(p.id);
  const items=groups.find(g=>g.id===p.id).chats,choose=groupToggle(p.id,p.name,items.length,'folder',list.id);choose.title=p.name;
  if(p.pinned)choose.classList.add('is-pinned');
  const menu=iconButton('more','项目菜单：'+p.name,()=>projectUI.menu(p,chats,menu,projects));menu.setAttribute('aria-haspopup','menu');menu.setAttribute('aria-expanded','false');
  row.append(choose,menu,iconButton('plus','在 '+p.name+' 中新建对话',()=>newChat(p.id)));row.addEventListener('contextmenu',e=>{e.preventDefault();projectUI.menu(p,chats,menu,projects);});
  list.hidden=!expanded;
  appendChats(list,items,p.id,6);
  if(!list.children.length)list.append(button('新建对话',()=>newChat(p.id),'empty-project-chat'));
  group.append(row,list);pList.append(group);
 }
 appendChats(cList,independent,independentKey,10);if(!independent.length)cList.append(el('p','还没有独立会话','note'));
 cList.hidden=collapsedProjects.has(independentKey);
}

function updateContext(){
 const p=projects.find(item=>item.id===projectId);
 $('workspace-label').textContent=p?p.name+(p.removed?' · 已移除':''):chatId?'独立会话 · 未关联项目':'尚未选择项目';
 $('workspace-context').title=p?p.path:chatId?'查看当前会话文件夹':'选择项目文件夹';
 $('workspace-action-label').textContent=p?'查看文件':chatId?'会话文件':'选择位置';
 $('chat-title').textContent=chat?.title||'当前对话';
}
async function switchChat(item,voice=null){if(chatId!==item.id){if(!voice||voice!==voiceSession)clearVoice();pendingPreview=null;if($('panel-content').querySelector('iframe[src^="/model-library/view/"]'))$('close-panel').click();}remember();chatId=item.id;projectId=item.project_id;chat=await get('/api/chats/'+chatId);sessionFolders.adopt(chat);lastTurns='';restore();render();if(document.body.classList.contains('mobile-nav'))workspaceVisibility(false);history.replaceState(null,'','#chat='+chatId);selectWorkspaceChat(chatId);if(compact)parent.postMessage({type:'jarvis:conversation:changed',chat_id:chatId},location.origin);}
async function newChat(project=''){remember();const created=await post('/api/chats',{project_id:project});workspaceChanged();collapsedProjects.delete(project||independentKey);saveSidebar();await refreshLists();await switchChat(chats.find(c=>c.id===created.id));$('message').focus();}

function syncComposerLock(){const pending=transitioningChats.has(chatId),unavailable=!!(chat?.archived||chat?.removed||projects.find(p=>p.id===projectId)?.removed);if((pending||unavailable)&&voiceSession&&voiceSession.phase!=='draft')clearVoice();$('composer').inert=pending;$('composer').setAttribute('aria-busy',String(pending));$('message').readOnly=unavailable;$('voice').disabled=!$('voice').onclick||pending||busy||unavailable;$('send').disabled=pending||busy||unavailable;}
function draftHasInputs(){return $('message').value||$('requirements').value||attachments.length||deliveryEditor.value()?.enabled;}
function unsavedConversation(){return chatId&&sessionFolders.items.has(chatId)?sessionFolders.dirty(chatId):!!draftHasInputs();}
async function holdWorkspaceDrafts(ids,purpose){
 const reloading=purpose==='reload';
 if(reloading&&(!document.documentElement.hasAttribute('data-presentation-ready')||busy||document.querySelector('dialog[open]')||!$('inspector').hidden))
  throw Error('请先完成正在提交的消息，或收起正在使用的表单和工具面板。');
 if(!ids.length&&projectUI.dirty())throw Error('项目文件仍有未保存修改，请先保存或还原再切换视图。');
 if((!ids.length||ids.includes(chatId))&&$('messages').querySelector('form[data-commitment-dirty]'))throw Error('当前反馈表单仍有未保存修改，请先完成或取消。');
 if(!ids.length&&!chatId&&draftHasInputs()){
  const key='new:'+projectId;remember();const created=await post('/api/chats',{project_id:projectId});drafts.set(created.id,drafts.get(key));await refreshLists();await switchChat(chats.find(c=>c.id===created.id));
 }
 const targets=ids.length?ids:[...new Set([...sessionFolders.items.keys(),...(chatId?[chatId]:[])])];
 if(targets.some(id=>transitioningChats.has(id)))throw Error('相关会话正在保存或整理，请稍候。');
 if(chatId&&targets.includes(chatId))remember();targets.forEach(id=>transitioningChats.add(id));syncComposerLock();
 const release=()=>{targets.forEach(id=>transitioningChats.delete(id));syncComposerLock();};
 try{
  await sessionFolders.settle(targets);
  if(reloading&&unsavedConversation())throw Error('当前草稿还没有可核对的保存回执。');
  if(reloading&&compact)savePresentationState(captureConversation());
  return release;
 }catch(error){release();throw error;}
}
async function hideChats(ids,action){return workspaceMutation(ids,action);}
async function changeChat(item,patch){const apply=async()=>{await post('/api/chat/update',{id:item.id,patch});await refreshLists();render();};return hideChats([item.id],apply);}

function chatMenu(item,anchor){return conversationMenu(item,anchor,{change:changeChat,folders:sessionFolders,panel});}
async function historyPanel(){
 await refreshLists();const body=panel('归档与已删除');
 body.append(el('p','归档、删除会话和移除项目均可恢复，原内容和文件保留。','note'));
 for(const p of projects.filter(x=>x.removed&&!x.validation_archive)){
  const card=el('div',undefined,'card');
  card.append(el('h3',p.name),el('p','已移除项目 · '+p.path),button('恢复项目',async()=>{await post('/api/project/update',{id:p.id,patch:{removed:false}});workspaceChanged();await historyPanel();}));body.append(card);
 }
 for(const chat of chats.filter(c=>!c.validation_archive&&(c.removed||c.archived))){
  const card=el('div',undefined,'card'),parent=projects.find(p=>p.id===chat.project_id);
  card.append(el('h3',chat.title),el('p',(chat.removed?'已删除':'已归档')+' · '+(parent?.name||'独立会话')),
   button(parent?.removed?'恢复项目及会话':'恢复会话',async()=>{
    if(parent?.removed)await post('/api/project/update',{id:parent.id,patch:{removed:false}});
    await post('/api/chat/update',{id:chat.id,patch:{removed:false,archived:false}});
    workspaceChanged();await historyPanel();
   }));body.append(card);
 }
 const validation=chats.filter(chat=>chat.validation_archive);
 const validationProjects=projects.filter(project=>project.validation_archive);
 if(validation.length||validationProjects.length){
  const archive=el('details',undefined,'work-coverage');
  archive.append(el('summary','测试归档（'+validation.length+' 个会话，'+validationProjects.length+' 个项目）'));
  archive.addEventListener('toggle',()=>{
   if(!archive.open||archive.children.length>1)return;
   for(const project of validationProjects){
    const entry=el('p');entry.append(button(project.name,()=>projectUI.explorer(project)));archive.append(entry);
   }
   for(const chat of validation){
    const entry=el('p');entry.append(link(chat.title,'/#chat='+encodeURIComponent(chat.id)));archive.append(entry);
   }
  });
  body.append(archive);
 }
 if(body.children.length===1)body.append(el('p','还没有归档、已删除的会话或已移除的项目。','empty'));
}
function render(){renderSidebar();updateContext();renderMessages();}
function renderMessages(){deliveryEditor.update(chat);syncComposerLock();const signature=JSON.stringify(chat?.turns||[])+(chat?.archived||0)+(chat?.removed||0)+(projects.find(p=>p.id===projectId)?.removed||0);if(lastTurns===signature){syncBrand();return;}if(lastTurns&&$('messages').querySelector('form[data-commitment-dirty]')){syncBrand();return;}lastTurns=signature;const content=$('messages'),nearBottom=content.scrollHeight-content.scrollTop-content.clientHeight<80;content.replaceChildren();active=chat?.turns.find(t=>['READY','RUNNING'].includes(t.status))?.id||null;if(!chat?.turns?.length){const welcome=el('div',undefined,'welcome'),brand=el('div',undefined,'jarvis-welcome-brand');const readout=el('div','待命','brand-state');readout.id='brand-readout';brand.append(el('jarvis-logo'),el('div','JARVIS','jarvis-wordmark'),readout);welcome.append(brand,el('h1','今天，一起做点什么？'));content.append(welcome);}for(const t of chat?.turns||[]){const user=el('article',undefined,'message user');user.append(el('div','你','speaker'),el('div',t.request.text,'bubble'));if(t.request.attachments?.length)user.append(el('p','附入：'+t.request.attachments.map(a=>a.name).join('、'),'note'));user.append(button('整理为候选记忆',async()=>{await post('/api/memory',{action:'propose',turn_id:t.id});await openMemory();},'message-meta'));const reply=el('article',undefined,'message assistant'+(['READY','RUNNING'].includes(t.status)?' pending':''));reply.append(el('div','✦ Jarvis','speaker'));reply.append(t.reply?markdown(t.reply):el('p',t.error?errorText(t.error):states[t.status]||t.status,['READY','RUNNING'].includes(t.status)?'busy-dot':''));const model=picker.profile({provider:t.provider||t.request.provider,model:t.model||t.request.model});reply.append(button((t.provider==='local-library'?'本机模型库':model.m?.label||t.model||'自动路由')+' · '+(states[t.status]||t.status)+' · 详情',()=>details('本轮模型与技能记录',t),'message-meta'));if(t.guidance){try{reply.append(el('span','✧ '+JSON.parse(t.guidance).name,'badge'));}catch{}}if(t.memory_context?.retrieval?.version)reply.append(el('span',retrievalLabel(t.memory_context.retrieval)+' · '+(t.memory_context.facts?.length||0)+' 条记忆','badge'));else if(t.memory_context?.facts?.length)reply.append(el('span','已使用 '+t.memory_context.facts.length+' 条有效记忆','badge'));if(t.reply)reply.append(button('复制',()=>navigator.clipboard.writeText(t.reply),'message-meta'),button('导出回答',()=>download('jarvis-answer.md',t.reply),'message-meta'),button('朗读回答（前450字）',()=>{const body=panel('本机朗读');const speaker=speechOutput(body,notice);panelCleanup=()=>speaker.close();speaker.play({purpose:'chat',chat_id:t.chat_id||chatId,exercise_id:null,source_id:t.id});},'message-meta'));deliveryReviewView(reply,t);if(t.provider==='local-library'&&t.assistant_action?.kind==='library_preview')showPreviewChoices(reply,t);else actionCard(reply,t,{openGoal:id=>openGoals(false,id),refresh:refreshChat,openMemory});content.append(user,reply);watchReply(reply,t.attention);}const unavailable=!!(chat?.archived||chat?.removed||projects.find(p=>p.id===projectId)?.removed);$('message').readOnly=unavailable;if(unavailable)content.append(el('p','此会话已归档、删除或所属项目已移除，请从左下角恢复后继续。','note'));$('send').disabled=busy||unavailable;$('send').hidden=false;$('send').title=active?'发送后续消息（将按顺序处理）':'发送消息';$('send').setAttribute('aria-label',$('send').title);$('cancel-response').hidden=!active;syncBrand();if(nearBottom||active)content.scrollTop=content.scrollHeight;}
function renderAttachments(){const list=$('attachments');list.replaceChildren();for(const [i,a] of attachments.entries())list.append(button(a.name+' ×',()=>{attachments.splice(i,1);renderAttachments();remember();}));}
function addAttachment(a){if(attachments.length>=4||attachments.reduce((n,x)=>n+x.text.length,0)+a.text.length>12000)throw Error('附件最多 4 个，合计不超过 12,000 字。');attachments.push(a);renderAttachments();remember();}
async function filesAttached(files){for(const file of files){if(!/\.(txt|md|py|js|ts|html|css|json|rs|csv|toml|yaml)$/i.test(file.name)||file.size>48000)throw Error('请选择支持的 UTF-8 文本文件，单个最多 48 KB。');const text=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());if(text.includes('\0'))throw Error('无法附入二进制文件。');addAttachment({name:file.name,text});}}
let pendingPreview = null;
function openLibraryPreview(choice){
 const content=panel(choice.title);
 mountModel(content,choice);
 content.append(link('在完整查看器中打开','/model-library/view/'+choice.asset+'/'+choice.version));
}
function showPreviewChoices(reply,turn){
 const action=turn.assistant_action;
 for(const choice of action.choices)reply.append(button(choice.title,()=>openLibraryPreview(choice),'message-meta'));
}
function openRequestedPreview(){
 if(!pendingPreview)return;
 const turn=chat?.turns.find(t=>t.id===pendingPreview);
 if(!turn||['READY','RUNNING'].includes(turn.status))return;
 pendingPreview=null;
 const action=turn.assistant_action;
 if(turn.provider==='local-library'&&action?.kind==='library_preview'&&action.auto_open&&action.choices.length===1){
  openLibraryPreview(action.choices[0]);
 }
}
function workspaceVisibility(open,focus=true){
 document.body.classList.toggle('nav-hidden',!open);
 document.body.classList.toggle('mobile-nav',open);
 const toggle=document.querySelector('[data-action=navigation]');
 toggle.setAttribute('aria-expanded',String(open));
 if(focus){if(open)$('close-workspace').focus();else toggle.focus();}
}
async function send(){
 if(busy||transitioningChats.has(chatId)||chat?.archived||chat?.removed||projects.find(p=>p.id===projectId)?.removed)return;
 const speechId=voiceSubmission();
 if(speechId===false)return;
 const navigation=$('message-mode').value==='auto'&&!attachments.length?surfaceIntent($('message').value):null;
 if(navigation){
  if(compact)parent.postMessage({type:'jarvis:companion:navigate',target:navigation},location.origin);
  else if(navigation==='work')panelCleanup=workStatusView(panel('工作状态'));
  else if(navigation==='mail')panelCleanup=await mailboxView(panel('Gmail 邮件助手'),{attach:addAttachment});
  else if(navigation==='mail-standing'){const {mailStandingView}=await import('./mail-standing.js');await mailStandingView(panel('邮件与待办持续办事'));}
  else{workspaceVisibility(true);await refreshLists();}
  clearVoice();$('message').value='';remember();return;
 }
 if($('message-mode').value==='auto'&&$('skills-enabled').checked&&skills.some(s=>s.id==='gmail'&&s.enabled)&&(mailIntent($('message').value)||$('skill').value==='gmail')){panelCleanup=await mailboxView(panel('Gmail 邮件助手'),{attach:addAttachment});notice('已打开 Gmail 助手；可直接检查连接、读取邮件或进行授权。');return;}
 if($('message-mode').value==='goal'){openGoals(true);return;}
 if(busy||!$('message').value.trim())return;
 const sourceId=chatId, sourceProject=projectId, sourceKey=sourceId||'new:'+sourceProject;
 let request={request_id:crypto.randomUUID(),text:$('message').value,provider:picker.selection.provider,model:picker.selection.model,reasoning:$('reasoning').value,skill:$('skills-enabled').checked?$('skill').value:'none',requirements:$('requirements').value,attachments:attachments.map(x=>({...x})),memory_enabled:$('memory-enabled').checked,assistant_mode:$('message-mode').value!=='chat'};
 request=deliveryEditor.apply(request);
 remember();busy=true;syncBrand();$('send').disabled=true;
 try{
  const targetId=sourceId||(await post('/api/chats',{project_id:sourceProject})).id;
  const sent=speechId?(await post('/api/speech',{action:'submit',id:speechId,command:{...request,chat_id:targetId}})).submission:await post('/api/chat/send',{...request,chat_id:targetId});
  if(chatId===sourceId&&projectId===sourceProject){pendingPreview=sent.request_id;clearVoice();}
  if(sent.status==='queued')notice('消息已保存，将按会话顺序处理。明确任务控制可通过工作状态直接操作。');
  if(sent.memory_capture?.state==='pending')notice('这条“记住”请求已存为候选，请到个人记忆与知识中核对；尚未写成正式事实。');
  else if(['excluded','unavailable'].includes(sent.memory_capture?.state))notice('这条内容未自动保存为记忆候选；可到个人记忆与知识中检查或手动整理。');
  const draft=drafts.get(sourceKey);if(draft){draft.text='';draft.attachments=[];if(draft.delivery_basis)draft.delivery_basis.enabled=false;drafts.set(targetId,draft);if(sourceKey!==targetId)drafts.delete(sourceKey);}
  if(chatId===sourceId&&projectId===sourceProject){deliveryEditor.commit();chatId=targetId;history.replaceState(null,'','#chat='+chatId);$('message').value='';attachments=[];renderAttachments();await refreshChat();remember();}
  await refreshLists();
 }finally{busy=false;syncBrand();syncComposerLock();}
}
async function refreshChat(){if(!chatId)return;const target=chatId,value=await get('/api/chats/'+target);if(chatId!==target)return;chat=value;sessionFolders.adopt(chat);updateContext();renderMessages();openRequestedPreview();}
async function openMemory(){await memoryView(panel('个人记忆与知识'),{settings:snapshot.settings,scope:projectId||'personal',projects,chatId});}
function pending(title,text){const body=panel(title);body.append(el('h3',title),el('p',text,'note'),link('在设置中查看模块状态','/settings#modules'));}
function openGoals(fromDraft=false,initialId=null){panelCleanup=goalsView(panel('目标与行动计划'),{settings:snapshot.settings,initialId,scope:projectId||'personal',memoryEnabled:$('memory-enabled').checked,initialGoal:fromDraft?$('message').value:'',inputText:fromDraft?attachments.map(a=>a.text).join('\n'):'',route:{...picker.selection,reasoning:$('reasoning').value},attach:addAttachment});}
let voiceSession=null;
const voiceLabels={idle:'开始语音输入',opening:'取消打开麦克风',recording:'停止录音并转写',transcribing:'取消转写'};
const voicePhase=phase=>{
 const button=$('voice');
 button.setAttribute('aria-label',voiceLabels[phase]);
 button.title=voiceLabels[phase];
 button.dataset.voicePhase=phase;
 button.setAttribute('aria-pressed',String(phase==='recording'));
};
function voiceStatus(text,error=false){
 $('voice-status').textContent=text;
 $('voice-status').classList.toggle('form-error',error);
 $('voice-feedback').hidden=!text&&!$('voice-choices').children.length;
}
function clearVoice(text='',error=false){
 const session=voiceSession;voiceSession=null;
 session?.capture?.close();session?.input?.cancel();
 clearTimeout(session?.timer);
 $('voice-choices').replaceChildren();
 voicePhase('idle');voiceStatus(text,error);
}
function localVoicePreview(){
 return $('message-mode').value==='auto'&&!attachments.length&&!deliveryEditor.value().enabled;
}
function voiceSubmission(){
 const session=voiceSession;
 if(!session)return null;
 if(session.phase==='opening'||session.phase==='recording'){
  voiceStatus('再点麦克风停止录音。');return false;
 }
 if(session.phase==='transcribing'||session.pending){
  voiceStatus('正在处理语音，请稍候。');return false;
 }
 if(session.receipt&&$('message').value.trim().length>3000){
  voiceStatus('语音草稿最多 3000 字，请缩短后发送。',true);return false;
 }
 if(session.required&&session.checkedText===$('message').value){
  voiceStatus('请选择模型候选，或修改模型名和 LOD 后发送。');return false;
 }
 if(session.chosenText===$('message').value&&!localVoicePreview()){
  voiceStatus('请在自动助手模式下单独发送模型预览指令。',true);return false;
 }
 return session.chat===chatId?session.receipt:null;
}

async function suggestVoiceModel(session){
 const text=$('message').value,lookup=Symbol();
 session.lookup=lookup;
 session.required=false;session.checkedText=text;
 $('voice-choices').replaceChildren();
 if(!text.trim()||text.length>180||!localVoicePreview()){session.pending=false;return;}
 session.pending=true;
 try{
  const result=await post('/api/speech',{action:'library_candidates',id:session.receipt,chat_id:session.chat,text});
  if(voiceSession!==session||session.lookup!==lookup||text!==$('message').value||!localVoicePreview())return;
  session.required=result.needs_confirmation;
  for(const item of result.choices){
   $('voice-choices').append(button(item.title+' · '+item.label+' · '+item.asset,()=>{
    if(voiceSession!==session||text!==$('message').value)return;
    $('message').value=item.text;session.chosenText=item.text;
    session.required=false;session.pending=false;
    $('voice-choices').replaceChildren();
    voiceStatus('已选模型，按发送打开。');
    remember();$('message').focus();
   }));
  }
  if(result.choices.length)voiceStatus('可选模型，也可直接修改文字。');
  else if(session.required)voiceStatus('请核对模型名和 LOD 档位。');
 }catch(error){
  if(voiceSession===session&&session.lookup===lookup)voiceStatus('模型候选暂不可用，可手动修改文字。',true);
 }finally{if(session.lookup===lookup)session.pending=false;}
}
function rememberMessage(){
 remember();
 const session=voiceSession;
 if(!session?.receipt)return;
 clearTimeout(session.timer);
 $('voice-choices').replaceChildren();
 session.chosenText=null;session.required=false;session.checkedText=null;session.lookup=null;
 session.pending=localVoicePreview();
 if(session.pending)session.timer=setTimeout(()=>void suggestVoiceModel(session),250);
}

async function useVoiceClip(session,bytes){
 session.phase='transcribing';voicePhase('transcribing');
 voiceStatus('正在本机转写…');
 try{
  if(!session.chat){
   const created=await post('/api/chats',{project_id:session.project});
   if(voiceSession!==session||chatId||projectId!==session.project)return;
   remember();
   drafts.set(created.id,drafts.get('new:'+session.project));
   session.chat=created.id;
   await switchChat({id:created.id,project_id:session.project},session);
   workspaceChanged();void run(refreshLists);
  }
  if(voiceSession!==session||chatId!==session.chat)return;
  session.input=speechTranscriber({purpose:'chat',chat_id:session.chat,exercise_id:null});
  const result=await session.input.transcribe(audioBase64(bytes));
  if(voiceSession!==session||!result)return;
  const draft=$('message');
  const combined=draft.value.trim()?draft.value+'\n'+result.text:result.text;
  if(combined.length>3000){clearVoice('合并后的语音草稿超过 3000 字，请缩短已有草稿后重试。',true);return;}
  draft.value=combined;
  session.receipt=result.id;session.phase='draft';
  voicePhase('idle');voiceStatus('已转写，编辑后可直接发送。');
  remember();draft.focus();draft.setSelectionRange(draft.value.length,draft.value.length);
  await suggestVoiceModel(session);
 }catch(error){
  if(voiceSession===session)clearVoice(error.message,true);
 }
}

function toggleVoice(){
 if(voiceSession?.phase==='recording'){voiceSession.capture.stop();return;}
 if(voiceSession&&voiceSession.phase!=='draft'){clearVoice('已取消语音输入。');return;}
 if($('voice').disabled||busy)return;
 clearVoice();
 const session={chat:chatId,project:projectId,phase:'opening'};
 voiceSession=session;voicePhase('opening');voiceStatus('正在打开麦克风…');
 session.capture=microphone({
  onStart(){
   if(voiceSession!==session)return;
   session.phase='recording';voicePhase('recording');
   voiceStatus('正在录音 · 再点麦克风停止');
  },
  onRecording:bytes=>{if(voiceSession===session)void useVoiceClip(session,bytes);},
  onError:message=>{if(voiceSession===session)clearVoice(message,true);}
 });
 void session.capture.start();
}
async function openEnglishLearning(){
 const content=panel('英语学习 · 记录、复习与进步');
 panelCleanup=await englishLearningView(content,{route:()=>({provider:picker.selection.provider,model:picker.selection.model,reasoning:$('reasoning').value}),ensureChat:async()=>{if(!chatId||projectId||chat?.archived||chat?.removed)await newChat('');return chatId;},refreshChat:async()=>{await refreshLists();await refreshChat();}});
}
function openTools(){panelCleanup=toolsView(panel('本地工具'),{attach:addAttachment});}
function taskPanel(){const body=panel('任务与自主研发');body.append(button('使用已发布本地工具',openTools),link('发起编码与自主研发 →','/settings#coding')); body.append(el('p','这里展示新核心的真实任务账本；普通对话不会自动派发执行任务。','note'));for(const x of [...snapshot.developments,...snapshot.tasks]){const c=el('div',undefined,'card');c.append(el('h3',x.id),el('p',(states[x.status]||x.status)+' · '+(x.phase||x.error||'任务')),button('查看记录',()=>details('任务记录',x)));body.append(c);}if(!snapshot.tasks.length&&!snapshot.developments.length)body.append(el('p','暂无任务记录。','empty'));}
function topTools(){const tools=$('top-tools');const add=(name,label,fn)=>tools.append(iconButton(name,label,fn));add('calendar','目标与行动计划',()=>openGoals());add('mail','Gmail · 连接与邮件管理',async()=>{panelCleanup=await mailboxView(panel('Gmail 邮件助手'),{attach:addAttachment});});tools.lastElementChild.id='mail-button';get('/api/mail').then(updateMailIndicator).catch(()=>{});add('explorer','资源管理器',()=>projectUI.explorer(selectedProject()));add('archive','模型库 · 模型、部件与人物',()=>window.open('/model-library','_blank','noopener'));add('save','会话专属文件夹与保存状态',()=>sessionFolders.view(panel('会话专属文件夹'),chatId));if(!compact)document.querySelector('.topbar').append(iconButton('leave','收回桌面精灵',async()=>{remember();await foldWorkbench(chatId||'');}));add('cpu','工作状态与资源',()=>{panelCleanup=workStatusView(panel('工作状态'));});add('refresh','刷新状态',async()=>{snapshot=await get('/api/snapshot');connected=true;await refreshLists();await refreshChat();notice('已刷新本机状态。');});add('sound','切换交互音效',async()=>{const old=soundState(),value=!(old.enabled&&old.unlocked);setSound(value);if(value)await unlockSound();snapshot.settings.ui=await savePreferences({sound:value});const b=document.querySelector('[aria-label="切换交互音效"]');b.setAttribute('aria-pressed',String(value));notice(value?'交互音效已开启。':'交互音效已关闭。');});add('tools','技能与工具',()=>{openTools();$('panel-content').prepend(link('文字技能与 MCP 管理 →','/settings#skill'));});add('file','AI 资料范围',()=>{const body=panel('AI 资料范围');body.append(el('p','发送范围：你的消息、会话要求、附件，以及当前接入方获准的有效记忆与兼容历史。纠正记忆、切换接入方或关闭记忆会重新装配历史窗口。','note'),el('p','打开项目仅授权本地浏览与编辑，不会自动递归读取文件或导入知识库。','note'),el('h3','当前附件'));for(const a of attachments)body.append(el('p',a.name+' · '+a.text.length+' 字'));if(!attachments.length)body.append(el('p','当前没有附入文件。','empty'));});add('chat','英语学习 · 跨会话记录与复习',()=>openEnglishLearning());add('memory','个人记忆与知识',openMemory);add('lock','隐私遮屏',()=>{const body=modal('已遮挡当前会话');body.append(el('p','仅遮挡工作台显示；此功能不替代系统锁屏或身份验证。','note'),button('返回工作台',closeModal));});add('star','Logo 动效与启动预览',()=>window.open('/brand/','_blank','noopener'));add('settings','设置',()=>window.open('/settings','_blank','noopener'));}
async function boot(){initModal();registerWorkspaceEditor(holdWorkspaceDrafts);splitters();snapshot=await get('/api/snapshot');applyPreferences(snapshot.settings.ui);setSound(!!snapshot.settings.ui.sound);$('version').textContent='v'+snapshot.status.release;picker=new ModelPicker(snapshot.settings,remember);skills=await get('/api/skills');for(const s of skills){const option=new Option(s.name+(s.state!=='ready'?' · 待接入':''),s.id);option.disabled=!s.enabled||s.state!=='ready';$('skill').add(option);}topTools();const memorySwitch=el('input');memorySwitch.id='memory-enabled';memorySwitch.type='checkbox';memorySwitch.checked=true;memorySwitch.onchange=remember;$('requirements').parentElement.after(field('使用获准记忆',memorySwitch));document.querySelector('[aria-label="切换交互音效"]').setAttribute('aria-pressed',String(!!snapshot.settings.ui.sound));const coreButton=document.querySelector('[aria-label="工作状态与资源"]');coreButton.id='core-state';coreButton.dataset.status=snapshot.status.control;await refreshLists();const hash=new URLSearchParams(location.hash.slice(1)).get('chat');const found=chats.find(c=>c.id===hash);if(found)await switchChat(found);else render();$('new-chat').onclick=()=>run(()=>newChat());$('open-folder').onclick=()=>run(()=>projectUI.openFolder());$('create-project').onclick=()=>run(()=>projectUI.openFolder('new'));for(const id of ['skill','skills-enabled','reasoning','message-mode'])$(id).addEventListener('change',remember);$('workspace-context').onclick=()=>run(()=>selectedProject()?projectUI.explorer(selectedProject()):chatId?sessionFolders.view(panel('会话专属文件夹'),chatId):projectUI.openFolder());$('history').onclick=()=>run(historyPanel);$('session-tasks').onclick=taskPanel;$('plan-goal').onclick=()=>run(()=>openGoals(true));$('close-panel').onclick=()=>{panelCleanup();panelCleanup=()=>{};$('inspector').hidden=true;$('right-divider').hidden=true;document.body.classList.remove('panel-focus');};$('focus-panel').onclick=()=>document.body.classList.toggle('panel-focus');document.querySelector('[data-action=navigation]').onclick=()=>workspaceVisibility(document.body.classList.contains('nav-hidden'));$('close-workspace').onclick=()=>workspaceVisibility(false);document.addEventListener('pointerdown',e=>{if(innerWidth<=700&&document.body.classList.contains('mobile-nav')&&!$('navigation').contains(e.target)&&!e.target.closest('[data-action=navigation],#model-popover,dialog'))workspaceVisibility(false);});$('chat-form').onsubmit=e=>{e.preventDefault();run(send);};$('message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();run(send);}};$('message').oninput=rememberMessage;$('requirements').oninput=()=>{$('requirements-state').textContent=$('requirements').value?'已设置':'未设置';remember();};$('cancel-response').onclick=()=>run(async()=>{await post('/api/chat/cancel',{request_id:active});await refreshChat();});$('add-attachment').onclick=()=>$('attachment-input').click();$('attachment-input').onchange=()=>run(async()=>{await filesAttached($('attachment-input').files);$('attachment-input').value='';});$('chat-form').ondragover=e=>e.preventDefault();$('chat-form').ondrop=e=>{e.preventDefault();run(()=>filesAttached(e.dataTransfer.files));};$('attach-current').onclick=()=>run(()=>{if(!projectUI.file)throw Error('请先在资源管理器打开文本文件。');addAttachment({name:projectUI.file.path,text:projectUI.file.draft});});$('voice').onclick=toggleVoice;syncComposerLock();if(!compact&&!Object.hasOwn(restoredPresentation,'chat'))enterCinema();
 restoreConversation();document.documentElement.setAttribute('data-presentation-ready','');
 const update=observeNativeUpdate({capture:captureConversation});void update();
 window.addEventListener('beforeunload',e=>{if(projectUI.dirty()||unsavedConversation()){e.preventDefault();e.returnValue='';}});setInterval(async()=>{if(document.hidden||!presentationVisible||polling)return;polling=true;try{const health=await get('/api/health');snapshot.status.control=health.control;connected=true;sessionFolders.retryInterrupted();if(chatId)await refreshChat();syncBrand();}catch(e){connected=false;syncBrand();notice('与本机服务的连接中断，正在等待恢复；不会重新发送消息。');}finally{polling=false;}},1800);}
document.addEventListener('jarvis-sound',()=>{const b=document.querySelector('[aria-label="切换交互音效"]');if(b)b.setAttribute('aria-pressed',String(soundState().enabled));});
const channel=new BroadcastChannel('jarvis-workbench-settings');
channel.onmessage=()=>run(async()=>{if(!picker)return;snapshot=await get('/api/snapshot');applyPreferences(snapshot.settings.ui);setSound(!!snapshot.settings.ui.sound);picker.settings=snapshot.settings;picker.refresh();skills=await get('/api/skills');for(const option of $('skill').options){const item=skills.find(x=>x.id===option.value);if(item)option.disabled=!item.enabled||item.state!=='ready';}});
window.addEventListener('message',event=>{
 if(!compact||event.origin!==location.origin||event.source!==parent||event.data?.type!=='jarvis:conversation:select')return;
 run(async()=>{await refreshLists();const item=chats.find(c=>c.id===event.data.chat_id);if(item)await switchChat(item);});
});
if(compact)new MutationObserver(()=>{parent.postMessage({type:'jarvis:conversation:changed',chat_id:chatId||null},location.origin);}).observe($('chat-title'),{childList:true});
run(boot);

window.addEventListener('jarvis:workspace-changed',()=>{if(picker)run(refreshLists);});
window.addEventListener('jarvis:workbench-select',event=>{const id=event.detail;if(/^chat-[a-f0-9]{32}$/.test(id||''))run(async()=>{await refreshLists();const item=chats.find(c=>c.id===id);if(item)await switchChat(item);});});

window.addEventListener('jarvis:workbench-visibility',event=>{presentationVisible=event.detail===true;if(!presentationVisible&&voiceSession?.phase!=='draft')clearVoice();if(presentationVisible&&picker)run(async()=>{await refreshLists();await refreshChat();});});

window.addEventListener('message',event=>{
 if(compact&&event.origin===location.origin&&event.source===parent&&event.data?.type==='jarvis:conversation:hidden'&&voiceSession?.phase!=='draft')clearVoice();
});
window.addEventListener('pagehide',()=>clearVoice());
