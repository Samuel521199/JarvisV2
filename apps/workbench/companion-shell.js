import {workspaceBrowser} from './workspace-browser.js';
import {expandWorkbench} from './presentation.js';
import {$,el,button,get,run,initModal,applyPreferences} from './ui.js';
import {mountMailCompanion} from './mail-companion.js';
import {workApi} from './work-client.js';
import {workStatusView} from './work-status.js';
import {conversationGroups} from './conversation-groups.js';
import {workGroups} from './work-groups.js';
import {mountCompanionFace} from './companion-face.js';
import {observeNativeUpdate,takePresentationState} from './native-upgrade.js';

const nativeRobot = location.pathname === '/companion/native-robot';
const nativeDock = location.pathname === '/companion/native';
const motionChannel = nativeRobot || nativeDock ? new BroadcastChannel('jarvis-companion-motion') : null;
const setFaceMotion = nativeDock ? null : mountCompanionFace($('robot'), $('presence-dot'));

function observeAppearance(initial) {
 const settings = new BroadcastChannel('jarvis-workbench-settings');
 let revision = 0, motionOff;
 function apply(ui) {
  applyPreferences(ui);
  motionOff = !!ui.motion_off;
  setFaceMotion?.(!motionOff);
  motionChannel?.postMessage({motionOff});
 }
 if (motionChannel) motionChannel.onmessage = ({data}) => {
  if (data?.request !== 'motion') return;
  motionChannel.postMessage({motionOff});
  window.dispatchEvent(new Event('jarvis:native:sync-status'));
 };
 settings.onmessage = async () => {
  const request = ++revision;
  try {
   const fresh = await get('/api/snapshot');
   if (request === revision) apply(fresh.settings.ui);
  } catch {
   // Keep the displayed preference until a read succeeds.
  }
 };
 apply(initial);
 window.addEventListener('pagehide', () => { ++revision;settings.close();motionChannel?.close(); }, {once:true});
}

let frame=null,selected='',mode='',cleanup=()=>{},mail=null,refreshing=false,workspaceView=null;
let refreshPending=false,dockSignature='',workContext=null;
const restored=takePresentationState();
let checkUpdate=()=>{};
function captureDock(){
 if(document.querySelector('dialog[open]'))throw Error('请先处理当前弹窗。');
 if(frame&&!frame.contentDocument?.documentElement.hasAttribute('data-presentation-ready'))
  throw Error('正在等待对话视图就绪。');
 const frameChat=frame&&new URLSearchParams(frame.contentWindow.location.hash.slice(1)).get('chat');
 return {mode,selected:mode==='chat'&&frameChat?frameChat:selected,work:mode==='work'?{...workContext,
   tab:document.querySelector('.work-tab[aria-selected=true]')?.dataset.bucket,
   query:document.querySelector('.work-search')?.value||'',
   scroll:document.querySelector('.work-projects')?.scrollTop||0}:null,
  projects:workspaceView?.captureLayout(),mail:mail?.captureLayout()};
}
const collapsed=new Set(),placementKey='jarvis.companion.placement.v1',selectionKey='jarvis.companion.chat.v1';
function rememberSelection(id){selected=id;try{localStorage.setItem(selectionKey,id);}catch{}}
function hide(){
 workspaceView?.close();workspaceView=null;cleanup();cleanup=()=>{};mode='';$('card').hidden=true;$('project-dialog').hidden=true;
 $('robot').setAttribute('aria-expanded','false');$('project-button').setAttribute('aria-expanded','false');
 if(mail&&!$('mail-dialog').hidden)mail.close();
}
function card(title,next){
 hide();mode=next;$('card').hidden=false;$('presence-title').textContent=title;
 $('card').dataset.mode=next;
 $('robot').setAttribute('aria-expanded',String(next==='chat'));
 $('conversation-host').hidden=next!=='chat';$('card-content').hidden=next==='chat';$('card-content').replaceChildren();
}
function chooseChat(id){rememberSelection(id);frame?.contentWindow.postMessage({type:'jarvis:conversation:select',chat_id:id},location.origin);}
function openChat(id=selected){
 card('Jarvis · 当前对话','chat');rememberSelection(id||'');
 if(!frame){
  frame=el('iframe');frame.title='Jarvis 共用聊天';frame.src='/conversation'+(selected?'#chat='+encodeURIComponent(selected):'');
  frame.addEventListener('load',()=>{
   const loadedChat=new URLSearchParams(frame.contentWindow.location.hash.slice(1)).get('chat');
   if(selected&&selected!==loadedChat)chooseChat(selected);
  });$('conversation-host').append(frame);
 }else if(selected)chooseChat(selected);
}
function work(key=null,project=null,initialTab=null,resume={}){
 card(key?'Jarvis · 工作详情':'Jarvis · 当前工作','work');workContext={key,project};
 cleanup=workStatusView($('card-content'),{focusKey:key,focusProject:project,initialTab,onOpenChat:openChat,resume});
}
async function projects(resume={}){
 hide();mode='projects';$('project-dialog').hidden=false;$('project-button').setAttribute('aria-expanded','true');
 workspaceView=workspaceBrowser($('project-dialog'),{onOpenChat:openChat,onClose:hide,selected:()=>selected,resume});await workspaceView.ready;
}
function paint(data){
 const projection=workGroups(data.items),active=projection.units.filter(i=>i.state==='running').length;
 const unread=projection.unread_count;$('unread-total').textContent=unread>99?'99+':String(unread);$('unread-total').hidden=unread===0;$('work-summary').textContent=active+' 项正在进行 · '+unread+' 项工作有未读反馈';
 const uncertain=data.activity.participants.some(p=>p.state==='unknown'),executing=active||data.activity.participants.some(p=>p.state==='busy');
 $('presence-state').textContent=uncertain?'部分状态待核对':executing?'正在工作':'已接入项待命';$('presence-dot').dataset.state=uncertain?'unknown':executing?'running':unread?'unread':'idle';
 const projects=[];
 for(const project of projection.projects){
  const unreadUnits=project.units.filter(unit=>unit.unread);
  if(!unreadUnits.length)continue;
  const {title,state,bucket}=unreadUnits[0];
  projects.push({id:project.id,projectTitle:project.title,count:unreadUnits.length,state,bucket,
   preview:title+' · '+(data.labels[state]||'工作反馈'),
   readings:unreadUnits.flatMap(unit=>unit.members).filter(item=>item.attention?.unread).map(item=>({attention:item.attention}))});
 }
 paintUnreadDocks(projects);
}
function paintUnreadDocks(projects){
 const visible=projects.slice(0,5),remaining=projects.length-visible.length;
 const signature=JSON.stringify([visible,remaining]);
 if(signature===dockSignature)return;
 const target=$('task-docks'),focused=document.activeElement;
 const hadFocus=target.contains(focused);
 let restoreFocus;
 target.replaceChildren();
 for(const item of visible){
  const dock=el('aside',undefined,'task-dock');dock.dataset.state=item.state;
  const label=item.projectTitle+' · '+item.count+' 项未读';
  const b=button('',()=>work(null,item.id,item.bucket),'task-icon');
  b.title=label;b.setAttribute('aria-label',label);b.dataset.projectId=item.id;
  b.append(el('span',({running:'◌',finished:'✓',failed:'!',cancelled:'−',needs_input:'?'}[item.state]||'◇'),'task-symbol'),
   el('span',item.count>99?'99+':String(item.count),'count'));
  const preview=el('div',undefined,'task-preview');
  const read=button('标记已读',async()=>{
   read.disabled=true;
   try{await workApi.viewedGroup({members:item.readings});await refresh(true);}
   finally{read.disabled=false;}
  },'task-read');
  read.title='只收起当前提醒，保留工作记录';read.setAttribute('aria-label','将“'+item.projectTitle+'”的当前未读提醒标记已读');read.dataset.projectId=item.id;
  preview.append(el('strong',item.projectTitle),el('span',item.preview),read);dock.append(b,preview);target.append(dock);
  if(hadFocus&&focused.dataset.projectId===item.id)restoreFocus=b;
 }
 if(remaining){
  const more=button('其余 '+remaining+' 个未读项目',()=>work(),'more-work');target.append(more);
  if(hadFocus&&focused.classList.contains('more-work'))restoreFocus=more;
 }
 if(hadFocus)(restoreFocus||$('work-button')).focus({preventScroll:true});
 dockSignature=signature;
}
async function refresh(afterReceipt=false){
 if(document.hidden)return;
 if(refreshing){refreshPending||=afterReceipt;return;}
 refreshing=true;
 try{paint(await workApi.state());$('error').hidden=true;}
 catch(error){$('presence-state').textContent='连接待恢复';$('presence-dot').dataset.state='unknown';$('error').textContent='本机状态读取失败，保留当前卡片：'+error.message;$('error').hidden=false;}
 finally{
  refreshing=false;
  if(refreshPending){refreshPending=false;void refresh(true);}
 }
}
async function boot(){
 initModal();const config=await get('/api/snapshot');observeAppearance(config.settings.ui);
 try{const id=localStorage.getItem(selectionKey);if(/^chat-[0-9a-f]{32}$/.test(id||''))selected=id;}catch{}
 let placement='right';try{placement=localStorage.getItem(placementKey)||'right';}catch{}
 if(!['left','right','desktop'].includes(placement))placement='right';$('placement').value=placement;document.querySelector('main').dataset.place=placement;
 $('placement').onchange=()=>{document.querySelector('main').dataset.place=$('placement').value;try{localStorage.setItem(placementKey,$('placement').value);}catch{}};
 mail=mountMailCompanion();$('dock-button').onclick=()=>run(()=>{workspaceView?.close();workspaceView=null;mail.open();});$('robot').onclick=()=>run(()=>mode==='chat'&&!$('card').hidden?hide():openChat());$('project-button').onclick=()=>run(projects);$('work-button').onclick=()=>run(()=>work());$('close-card').onclick=()=>run(hide);
 $('open-full').onclick=()=>run(async()=>{await expandWorkbench(selected);hide();});
 document.addEventListener('jarvis:mail-opened',()=>{cleanup();cleanup=()=>{};mode='mail';$('card').hidden=true;$('project-dialog').hidden=true;$('robot').setAttribute('aria-expanded','false');$('project-button').setAttribute('aria-expanded','false');});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('modal').open)run(hide);});
 window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==frame?.contentWindow)return;const message=event.data;
  if(message?.type==='jarvis:conversation:changed'&&typeof message.chat_id==='string'&&/^chat-[0-9a-f]{32}$/.test(message.chat_id))rememberSelection(message.chat_id);
  if(message?.type!=='jarvis:companion:navigate')return;
  if(message.target==='work')work();else if(message.target==='projects')run(projects);else if(message.target==='mail')mail.open();else if(message.target==='mail-standing')run(async()=>{const {openMailStanding}=await import('./mail-standing.js');await openMailStanding();});
 });
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});if(nativeDock)await import('./native-presence.js');
 if(restored.mode==='chat')openChat(/^chat-[0-9a-f]{32}$/.test(restored.selected||'')?restored.selected:selected);
 else if(restored.mode==='work'&&restored.work){
  const {key,project,tab}=restored.work;work(key,project,tab,restored.work);
 }else if(restored.mode==='projects')await projects(restored.projects);
 else if(restored.mode==='mail'&&restored.mail)mail.restoreLayout(restored.mail);
 checkUpdate=observeNativeUpdate({capture:captureDock});
 await refresh();void checkUpdate();
 const timer=setInterval(()=>{void refresh();void checkUpdate();},5000);
 window.addEventListener('jarvis:work-viewed',()=>refresh(true));
 window.addEventListener('jarvis:workspace-selection',event=>rememberSelection(event.detail));
 window.addEventListener('pagehide',()=>{clearInterval(timer);cleanup();},{once:true});
}
if (nativeRobot) {
 motionChannel.onmessage = ({data}) => {
  if (typeof data?.motionOff === 'boolean') setFaceMotion(!data.motionOff);
 };
 motionChannel.postMessage({request:'motion'});
 window.addEventListener('pagehide', () => motionChannel.close(), {once:true});
 void import('./native-presence.js').then(()=>{const update=observeNativeUpdate();void update();});
} else run(boot);
