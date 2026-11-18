import {workspaceBrowser} from './workspace-browser.js';
import {expandWorkbench} from './presentation.js';
import {$,el,button,get,run,initModal,applyPreferences} from './ui.js';
import {mountMailCompanion} from './mail-companion.js';
import {workApi} from './work-client.js';
import {workStatusView} from './work-status.js';
import {conversationGroups} from './conversation-groups.js';
import {workGroups} from './work-groups.js';
import {mountCompanionFace} from './companion-face.js';

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
 card('Jarvis · 对话','chat');rememberSelection(id||'');
 if(!frame){
  frame=el('iframe');frame.title='Jarvis 共用聊天';frame.src='/conversation'+(selected?'#chat='+encodeURIComponent(selected):'');
  frame.addEventListener('load',()=>{if(selected)chooseChat(selected);});$('conversation-host').append(frame);
 }else if(selected)chooseChat(selected);
}
function work(key=null,project=null){card(key?'Jarvis · 工作详情':'Jarvis · 当前工作','work');cleanup=workStatusView($('card-content'),{focusKey:key,focusProject:project,onOpenChat:openChat});}
async function projects(){
 hide();mode='projects';$('project-dialog').hidden=false;$('project-button').setAttribute('aria-expanded','true');
 workspaceView=workspaceBrowser($('project-dialog'),{onOpenChat:openChat,onClose:hide,selected:()=>selected});await workspaceView.ready;
}
function paint(data){
 const projection=workGroups(data.items),active=projection.units.filter(i=>i.state==='running').length;
 const unread=projection.unread_count;$('unread-total').textContent=unread>99?'99+':String(unread);$('unread-total').hidden=unread===0;$('work-summary').textContent=active+' 项正在进行 · '+unread+' 项工作有未读反馈';
 const uncertain=data.activity.participants.some(p=>p.state==='unknown'),executing=active||data.activity.participants.some(p=>p.state==='busy');
 $('presence-state').textContent=uncertain?'部分状态待核对':executing?'正在工作':'已接入项待命';$('presence-dot').dataset.state=uncertain?'unknown':executing?'running':unread?'unread':'idle';
 const target=$('task-docks');if(target.contains(document.activeElement))return;target.replaceChildren();
 const projects=projection.projects.map(p=>({...p,units:p.units.filter(u=>u.bucket!=='history')})).filter(p=>p.units.length);
 for(const project of projects.slice(0,5)){
  const item=project.units[0],count=project.units.filter(u=>u.unread).length;
  const dock=el('aside',undefined,'task-dock');dock.dataset.state=item.state;
  const label=project.title+' · '+project.units.length+' 项工作'+(count?' · '+count+' 项未读':'');
  const b=button('',()=>work(null,project.id),'task-icon');b.title=label;b.setAttribute('aria-label',label);
  b.append(el('span',({running:'◌',finished:'✓',failed:'!',cancelled:'−',needs_input:'?'}[item.state]||'◇'),'task-symbol'));if(count)b.append(el('span',String(count>99?'99+':count),'count'));
  const preview=el('div',undefined,'task-preview');preview.append(el('strong',project.title),el('span',item.title+' · '+(data.labels[item.state]||'工作反馈')));dock.append(b,preview);target.append(dock);
 }
 if(projects.length>5)target.append(button('其余 '+(projects.length-5)+' 个项目',()=>work(),'more-work'));
}
async function refresh(){
 if(refreshing||document.hidden)return;refreshing=true;
 try{paint(await workApi.state());$('error').hidden=true;}
 catch(error){$('presence-state').textContent='连接待恢复';$('presence-dot').dataset.state='unknown';$('error').textContent='本机状态读取失败，保留当前卡片：'+error.message;$('error').hidden=false;}
 finally{refreshing=false;}
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
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});if(nativeDock)await import('./native-presence.js');await refresh();const timer=setInterval(refresh,5000);
 window.addEventListener('jarvis:work-viewed',refresh);
 window.addEventListener('jarvis:workspace-selection',event=>rememberSelection(event.detail));
 window.addEventListener('pagehide',()=>{clearInterval(timer);cleanup();},{once:true});
}
if (nativeRobot) {
 motionChannel.onmessage = ({data}) => {
  if (typeof data?.motionOff === 'boolean') setFaceMotion(!data.motionOff);
 };
 motionChannel.postMessage({request:'motion'});
 window.addEventListener('pagehide', () => motionChannel.close(), {once:true});
 import('./native-presence.js');
} else run(boot);
