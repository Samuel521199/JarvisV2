import {el,button,iconButton,get,post,field,input,notice} from './ui.js';
import {Projects} from './projects.js';
import {SessionFolders} from './session-folders.js';
import {conversationMenu} from './workspace-menus.js';
import {workspaceMutation,updateWorkspaceChat,workspaceChanged} from './workspace-events.js';
import {expandWorkbench} from './presentation.js';

export function workspaceBrowser(container,{onOpenChat,onClose,selected=()=>''}={}){
 let projects=[],chats=[],tab='active',query='',disposed=false,detail=null;const collapsed=new Set(),limits=new Map(),folders=new SessionFolders();
 const panel=title=>{detail={title};render();return container.querySelector('.workspace-detail-content');};
 const refresh=async()=>{[projects,chats]=await Promise.all([get('/api/projects'),get('/api/chats')]);if(!disposed)render();};
 const changed=async()=>{detail=null;workspaceChanged();await refresh();};
 const change=async(item,patch)=>{await updateWorkspaceChat(item,patch);await changed();};
 const create=async p=>{const c=await post('/api/chats',{project_id:p?.id||''});await changed();onOpenChat(c.id);};
 const projectUI=new Projects({panel,refresh:changed,newChat:create,selectProject:p=>showProject(p),attach:()=>notice('请在对话中明确选择要附入的文件。'),hideChats:(ids,action)=>workspaceMutation(ids,action)});
 function chatRow(chat,parent){
  const row=el('div',undefined,'workspace-chat'+(selected()===chat.id?' active':''));row.dataset.chatId=chat.id;
  const open=button('',()=>onOpenChat(chat.id),'workspace-chat-open');open.append(el('strong',chat.title),el('small',(parent?.name||'独立会话')+' · '+new Date(chat.updated*1000).toLocaleDateString()+' · '+chat.id.slice(-6)));open.title=chat.title;row.append(open);
  if(chat.removed||chat.archived||parent?.removed)row.append(button('恢复',async()=>{await workspaceMutation([chat.id],async()=>{if(parent?.removed)await post('/api/project/update',{id:parent.id,patch:{removed:false}});await post('/api/chat/update',{id:chat.id,patch:{removed:false,archived:false}});});await changed();}));
  const menu=iconButton('more','会话菜单：'+chat.title,()=>conversationMenu(chat,menu,{change,folders,panel}));row.append(menu);row.oncontextmenu=e=>{e.preventDefault();menu.click();};return row;
 }
 function showProject(p){
  const body=panel(p.name),members=chats.filter(c=>c.project_id===p.id),actions=el('div',undefined,'workspace-actions');
  body.append(el('p',p.description||'尚未填写项目说明','workspace-description'),el('p',p.path,'workspace-path'),el('p',members.filter(c=>!c.archived&&!c.removed).length+' 个当前会话 · '+members.filter(c=>c.archived&&!c.removed).length+' 个归档会话','note'));
  actions.append(button('新建对话',()=>create(p)),button('查看项目文件',()=>projectUI.explorer(p)),button('编辑项目',()=>projectUI.edit(p)));
  const more=button('项目管理',()=>projectUI.menu(p,chats,more,projects));actions.append(more,button('在工作台展开',()=>expandWorkbench(selected())));body.append(actions);
  for(const chat of members.filter(c=>!c.removed).slice(0,30))body.append(chatRow(chat,p));
 }
 function render(){
  if(disposed)return;const searchFocus=container.querySelector('.workspace-search')===document.activeElement;container.replaceChildren();
  const head=el('header',undefined,'top');head.append(el('strong',detail?.title||'项目与会话'),iconButton('expand','展开工作台',()=>expandWorkbench(selected())),iconButton('close','关闭项目与会话',onClose));container.append(head);
  if(detail){const content=el('div',undefined,'workspace-detail-content');content.append(button('← 返回项目与会话',()=>{if(projectUI.dirty())throw Error('项目文件仍有未保存修改，请先保存或还原。');detail=null;render();}));container.append(content);return;}
  const tools=el('div',undefined,'workspace-toolbar'),search=input(query,'搜索项目或会话');search.classList.add('workspace-search');search.setAttribute('aria-label','搜索项目或会话');search.oninput=()=>{query=search.value;render();};tools.append(search,button('新建会话',()=>create(null)),button('打开 / 新建项目',()=>projectUI.openFolder()));container.append(tools);
  const tabs=el('nav',undefined,'workspace-tabs');for(const [key,label] of [['active','当前'],['archived','已归档'],['removed','已删除']]){const b=button(label,()=>{tab=key;render();});b.setAttribute('aria-pressed',String(key===tab));tabs.append(b);}container.append(tabs);
  const list=el('div',undefined,'workspace-list'),needle=query.trim().toLocaleLowerCase();container.append(list);let total=0;
  const parentMap=new Map(projects.map(p=>[p.id,p]));
  if(tab!=='active'){
   if(tab==='removed')for(const p of projects.filter(p=>p.removed&&(!needle||(p.name+' '+p.path).toLocaleLowerCase().includes(needle)))){const r=el('div',undefined,'workspace-removed-project');r.append(el('strong',p.name),el('small','已移除项目 · 原文件保留'),button('恢复项目',async()=>{await workspaceMutation([],()=>post('/api/project/update',{id:p.id,patch:{removed:false}}));await changed();}));list.append(r);total++;}
   const items=chats.filter(c=>(tab==='removed'?c.removed:!c.removed&&c.archived)&&(!needle||(c.title+' '+(parentMap.get(c.project_id)?.name||'')).toLocaleLowerCase().includes(needle)));
   for(const c of items.slice(0,limits.get(tab)||30)){list.append(chatRow(c,parentMap.get(c.project_id)));total++;}if(items.length>(limits.get(tab)||30))list.append(button('显示更多',()=>{limits.set(tab,(limits.get(tab)||30)+30);render();}));
  }else{
   for(const p of [...projects.filter(p=>!p.removed),{id:'',name:'独立会话'}]){
    const members=chats.filter(c=>c.project_id===p.id&&!c.archived&&!c.removed),items=members.filter(c=>!needle||(p.name+' '+c.title).toLocaleLowerCase().includes(needle));
    if(needle&&!items.length&&!p.name.toLocaleLowerCase().includes(needle))continue;
    const section=el('section',undefined,'workspace-group'),row=el('div',undefined,'workspace-project-row'),toggle=button('',()=>{collapsed.has(p.id)?collapsed.delete(p.id):collapsed.add(p.id);render();},'workspace-group-toggle');toggle.setAttribute('aria-expanded',String(!collapsed.has(p.id)));toggle.append(el('span',collapsed.has(p.id)?'▸':'▾'),el('strong',p.name),el('small',String(members.length)));row.append(toggle);
    if(p.id){row.append(iconButton('folder','查看项目：'+p.name,()=>showProject(p)));const menu=iconButton('more','项目菜单：'+p.name,()=>projectUI.menu(p,chats,menu,projects));row.append(menu);}row.append(iconButton('plus','在 '+p.name+' 中新建对话',()=>create(p.id?p:null)));section.append(row);
    if(!collapsed.has(p.id)){for(const c of items.slice(0,limits.get(p.id)||8))section.append(chatRow(c,p.id?p:null));if(items.length>(limits.get(p.id)||8))section.append(button('显示更多（'+(items.length-(limits.get(p.id)||8))+'）',()=>{limits.set(p.id,(limits.get(p.id)||8)+20);render();},'workspace-more'));if(!items.length)section.append(el('p','暂无当前会话','note'));}
    list.append(section);total++;
   }
  }
  if(!total)list.append(el('p','这里还没有匹配的项目或会话。','workspace-empty'));
  container.append(el('p','同一套项目与会话 · 归档和删除可恢复，原文件保留','foot'));
  if(searchFocus){search.focus();search.setSelectionRange(query.length,query.length);}
 }
 const onChanged=()=>{if(!detail)void refresh().catch(e=>notice(e.message));};window.addEventListener('jarvis:workspace-changed',onChanged);
 const ready=refresh();return {ready,close(){if(projectUI.dirty())throw Error('项目文件仍有未保存修改，请先保存或还原。');disposed=true;window.removeEventListener('jarvis:workspace-changed',onChanged);}};
}
