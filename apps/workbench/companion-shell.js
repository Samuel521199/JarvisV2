import {$,el,button,get,run,initModal,applyPreferences} from './ui.js';
import {mountMailCompanion} from './mail-companion.js';
import {workApi} from './work-client.js';
import {workStatusView} from './work-status.js';
import {conversationGroups} from './conversation-groups.js';

let frame=null,selected='',mode='',cleanup=()=>{},mail=null,refreshing=false,groups=[];
const collapsed=new Set(),placementKey='jarvis.companion.placement.v1',selectionKey='jarvis.companion.chat.v1';
function rememberSelection(id){selected=id;try{localStorage.setItem(selectionKey,id);}catch{}}
function hide(){
 cleanup();cleanup=()=>{};mode='';$('card').hidden=true;$('project-dialog').hidden=true;
 $('robot').setAttribute('aria-expanded','false');$('project-button').setAttribute('aria-expanded','false');
 if(mail&&!$('mail-dialog').hidden)mail.close();
}
function card(title,next){
 hide();mode=next;$('card').hidden=false;$('presence-title').textContent=title;
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
function work(key=null){card(key?'Jarvis · 工作详情':'Jarvis · 当前工作','work');cleanup=workStatusView($('card-content'),{focusKey:key,onOpenChat:openChat});}
function renderProjects(){
 const panel=$('project-dialog');panel.replaceChildren();
 const head=el('div',undefined,'top');head.append(el('strong','项目与会话'),button('×',hide,'close'));head.lastChild.setAttribute('aria-label','关闭项目与会话');panel.append(head);
 const list=el('div',undefined,'project-list');panel.append(list);
 for(const group of groups){
  const row=el('section',undefined,'project-group'),heading=button('',()=>{collapsed.has(group.id)?collapsed.delete(group.id):collapsed.add(group.id);renderProjects();},'project-heading');
  heading.title=group.path||group.title;heading.setAttribute('aria-expanded',String(!collapsed.has(group.id)));
  heading.append(el('span',collapsed.has(group.id)?'▸':'▾','chevron'),el('span',group.project?'▱':'◌','folder'),el('span',group.title),el('span',String(group.chats.length),'count-small'));row.append(heading);
  if(!collapsed.has(group.id)){
   if(group.path)row.append(el('small',group.path,'project-path'));
   for(const chat of group.chats){const b=button('',()=>openChat(chat.id),'project-chat'+(chat.id===selected?' active':''));b.append(el('span',chat.title,'chat-title'));b.title=chat.title;row.append(b);}
   if(!group.chats.length)row.append(el('span','暂无会话','project-row-empty'));
  }list.append(row);
 }
 panel.append(el('p','与工作台使用相同项目、会话与专属文件夹。','foot'));
}
async function projects(){
 hide();mode='projects';$('project-dialog').hidden=false;$('project-button').setAttribute('aria-expanded','true');$('project-dialog').textContent='正在读取项目与会话…';
 const [p,c]=await Promise.all([get('/api/projects'),get('/api/chats')]);if(mode!=='projects')return;groups=conversationGroups(p,c);renderProjects();
}
function paint(data){
 const items=data.items.filter(i=>!['finished','failed','cancelled'].includes(i.state)||i.attention?.unread),active=items.filter(i=>i.state==='running').length;
 $('unread-total').textContent=String(data.unread_count);$('work-summary').textContent=active+' 项正在运行 · '+data.unread_count+' 项未读结果';
 const uncertain=data.activity.participants.some(p=>p.state==='unknown'),executing=active||data.activity.participants.some(p=>p.state==='busy');
 $('presence-state').textContent=uncertain?'部分状态待核对':executing?'正在工作':'已接入项待命';$('presence-dot').dataset.state=uncertain?'unknown':executing?'running':data.unread_count?'unread':'idle';
 const target=$('task-docks');if(target.contains(document.activeElement))return;target.replaceChildren();
 for(const item of items.slice(0,12)){
  const dock=el('aside',undefined,'task-dock');dock.dataset.state=item.state;
  const label=item.title+' · '+data.labels[item.state]+(item.attention.unread?' · 未读':'');
  const b=button('',()=>item.source==='dialogue'?openChat(item.chat_id):work(item.attention.key),'task-icon');b.title=label;b.setAttribute('aria-label',label);
  b.append(el('span',({running:'◌',finished:'✓',failed:'!',cancelled:'−',needs_input:'?'}[item.state]||'◇'),'task-symbol'));if(item.attention.unread)b.append(el('span','', 'unread-dot'));
  const preview=el('div',undefined,'task-preview');preview.append(el('strong',item.title),el('span',data.labels[item.state]+(item.reason?' · '+item.reason:'')));dock.append(b,preview);target.append(dock);
 }
 if(items.length>12)target.append(button('还有 '+(items.length-12)+' 项',()=>work(),'more-work'));
}
async function refresh(){
 if(refreshing||document.hidden)return;refreshing=true;
 try{paint(await workApi.state());$('error').hidden=true;}
 catch(error){$('presence-state').textContent='连接待恢复';$('presence-dot').dataset.state='unknown';$('error').textContent='本机状态读取失败，保留当前卡片：'+error.message;$('error').hidden=false;}
 finally{refreshing=false;}
}
async function boot(){
 initModal();const config=await get('/api/snapshot');applyPreferences(config.settings.ui);
 try{const id=localStorage.getItem(selectionKey);if(/^chat-[0-9a-f]{32}$/.test(id||''))selected=id;}catch{}
 let placement='right';try{placement=localStorage.getItem(placementKey)||'right';}catch{}
 if(!['left','right','desktop'].includes(placement))placement='right';$('placement').value=placement;document.querySelector('main').dataset.place=placement;
 $('placement').onchange=()=>{document.querySelector('main').dataset.place=$('placement').value;try{localStorage.setItem(placementKey,$('placement').value);}catch{}};
 mail=mountMailCompanion();$('dock-button').onclick=()=>mail.open();$('robot').onclick=()=>mode==='chat'&&!$('card').hidden?hide():openChat();$('project-button').onclick=()=>run(projects);$('work-button').onclick=()=>work();$('close-card').onclick=hide;
 $('open-full').onclick=()=>window.open(mode==='chat'&&selected?'/#chat='+encodeURIComponent(selected):'/','_blank','noopener');
 document.addEventListener('jarvis:mail-opened',()=>{cleanup();cleanup=()=>{};mode='mail';$('card').hidden=true;$('project-dialog').hidden=true;$('robot').setAttribute('aria-expanded','false');$('project-button').setAttribute('aria-expanded','false');});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('modal').open)hide();});
 window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==frame?.contentWindow)return;const message=event.data;
  if(message?.type==='jarvis:conversation:changed'&&typeof message.chat_id==='string'&&/^chat-[0-9a-f]{32}$/.test(message.chat_id))rememberSelection(message.chat_id);
  if(message?.type!=='jarvis:companion:navigate')return;
  if(message.target==='work')work();else if(message.target==='projects')run(projects);else if(message.target==='mail')mail.open();
 });
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});if(location.pathname==='/companion/native')await import('./native-presence.js');await refresh();const timer=setInterval(refresh,5000);
 window.addEventListener('pagehide',()=>{clearInterval(timer);cleanup();},{once:true});
}
if(location.pathname==='/companion/native-robot')import('./native-presence.js');else run(boot);
