import {$,el,button,iconButton,link,input,select,field,get,post,run,notice,modal,closeModal,initModal,card,confirmAction,errorText,states} from './ui.js';
initModal();
const status=await get('/api/family/status');
if(!status.enabled||!status.actor)location.replace('/login');
else await start();
function group(title,node){const box=el('fieldset',undefined,'family-group');box.append(el('legend',title),node);return box;}
async function start(){
 const actor=status.actor;let tab='note',activeChat=null,timer=null,pollBusy=false;
 const command=value=>post('/api/family',value);
 const {members}=await command({action:'members'}),{connections}=await get('/api/family/catalog');
 const name=id=>members.find(x=>x.id===id)?.name||id;
 $('family-identity').textContent=actor.name+' · '+(actor.role==='owner'?'主人 / 可管理全部':'成员 / 自己与明确共享');
 if(actor.role==='owner')$('family-tools').append(iconButton('home','返回工作台',()=>location.assign('/')));
 $('family-tools').append(iconButton('lock','退出并锁定',async()=>{await post('/api/family/logout',{});location.replace('/login');}));
 const tabs=[['note','记忆与资料'],['chat','私密对话'],['account','账户']];if(actor.role==='owner')tabs.push(['members','成员管理']);
 for(const [id,label] of tabs)$('family-tabs').append(button(label,()=>{tab=id;activeChat=null;clearTimeout(timer);return render();}));
 function checks(items,selected=[]){const wrap=el('div',undefined,'family-checks'),boxes=[];for(const [id,label] of items){const box=input();box.type='checkbox';box.checked=selected.includes(id);box.dataset.id=id;const l=el('label');l.append(box,el('span',label));wrap.append(l);boxes.push(box);}return {node:wrap,value:()=>boxes.filter(x=>x.checked).map(x=>x.dataset.id)};}
 async function editor(ident){const row=ident?await command({action:'read',id:ident}):{id:'',revision:0,title:'',text:'',shared:[],providers:[],owner:actor.id};const writable=actor.role==='owner'||row.owner===actor.id;
  const body=modal(writable?'编辑私密资料':'共享资料'),form=el('div',undefined,'family-editor'),title=input(row.title),content=el('textarea');content.value=row.text;title.maxLength=160;content.maxLength=20000;
  const recipients=checks(members.filter(x=>x.active&&x.id!=='owner'&&x.id!==row.owner).map(x=>[x.id,x.name]),row.shared),providers=checks(connections.map(x=>[x.id,x.label]),row.providers);
  form.append(el('p','来源成员：'+name(row.owner)+'。主人始终可以查看；共享成员仅可读取。','note'),field('标题',title),field('正文',content),group('明确共享给',recipients.node),group('允许进入这些模型接入方（默认不允许）',providers.node));
  if(writable)form.append(button('保存',async()=>{await command({action:'save',note:{id:row.id,revision:row.revision,title:title.value,text:content.value,shared:recipients.value(),providers:providers.value()}});closeModal();await render();}));else for(const n of form.querySelectorAll('input,textarea'))n.disabled=true;
  body.append(form);
 }
 async function render(){
  clearTimeout(timer);const body=$('family-content');body.replaceChildren();for(const [i,b] of [...$('family-tabs').children].entries())b.classList.toggle('active',tabs[i][0]===tab);
  if(tab==='members'){body.append(el('p','账号停用或密码重置会撤销该成员的全部登录；资料保留，主人仍可管理。','note'));
   const id=input('','如 alice'),label=input('','显示名称'),password=input();password.type='password';password.autocomplete='new-password';
   body.append(field('成员 ID',id),field('成员名称',label),field('初始密码（至少 12 字符）',password),button('添加成员',async()=>{await command({action:'member_save',member:{id:id.value,name:label.value,active:true,password:password.value}});location.reload();}));
   for(const m of members.filter(x=>x.id!=='owner')){const c=card(m.name+' · '+m.id,m.active?'使用中':'已停用');c.append(button(m.active?'停用并撤销登录':'重新启用',async()=>{await command({action:'member_save',member:{id:m.id,name:m.name,active:!m.active,password:''}});location.reload();}),button('重置密码',()=>{const b=modal('重置 '+m.name+' 的密码'),p=input();p.type='password';p.autocomplete='new-password';b.append(field('新密码',p),button('保存并撤销旧登录',async()=>{await command({action:'member_save',member:{id:m.id,name:m.name,active:m.active,password:p.value}});p.value='';closeModal();notice('已重置该成员密码。');}));}));body.append(c);}return;
  }
  if(tab==='account'){const old=input(),next=input();old.type=next.type='password';old.autocomplete='current-password';next.autocomplete='new-password';body.append(field('当前密码',old),field('新密码（至少 12 字符）',next),button('更改密码并退出所有登录',async()=>{await command({action:'password',current:old.value,password:next.value});location.replace('/login');}));return;}
  if(tab==='chat'&&activeChat){await chatView(body);return;}
  const query=input('','搜索标题或资料正文'),list=el('div',undefined,'family-list');
  if(tab==='note')body.append(button('添加私密资料',()=>editor('')));else body.append(button('开始私密对话',async()=>{activeChat=(await command({action:'chat_create',title:'新的私密对话'})).id;await render();}));
  const draw=async()=>{const result=await command({action:'list',kind:tab,query:query.value});list.replaceChildren();if(!result.items.length)list.append(el('p','这里还没有可见内容。','note'));
   for(const row of result.items){const c=card(row.title,'来源：'+name(row.owner)+' · 修订 '+row.revision),meta=el('p',undefined,'family-meta');meta.append(el('span',row.shared.length?'共享给 '+row.shared.map(name).join('、'):'成员私密 · 主人可查看'),el('span',row.providers.length?'允许模型：'+row.providers.join('、'):'未授权提供给模型'));c.append(meta);
    c.append(button(tab==='chat'?'打开对话':'查看 / 编辑',async()=>{if(tab==='chat'){activeChat=row.id;await render();}else await editor(row.id);}));
    if(actor.role==='owner'||row.owner===actor.id)c.append(button('遗忘',()=>confirmAction('遗忘这条内容','将清空本机有效内容，并撤回依赖它的家庭聊天片段。已发送云端或另存的副本无法追回。','遗忘',async()=>{await command({action:'forget',id:row.id,revision:row.revision});await draw();}),'danger'));list.append(c);
   }};
  body.append(field('筛选',query),button('搜索',draw),list);await draw();
 }
 async function chatView(body){
  body.append(button('返回私密对话',()=>{activeChat=null;return render();}));const transcript=el('div'),form=el('div',undefined,'family-editor');body.append(transcript,form);
  const provider=select(connections.map(x=>[x.id,x.label])),model=select([]),content=el('textarea');content.maxLength=6000;content.placeholder='向 Jarvis 说些什么…';
  const options=(await command({action:'list',kind:'note',query:''})).items,notes=checks(options.map(x=>[x.id,x.title]));
  const models=()=>{model.replaceChildren();for(const x of connections.find(x=>x.id===provider.value)?.models||[])model.add(new Option(x,x));};provider.onchange=models;models();
  const send=button('发送',async()=>{send.disabled=true;try{await command({action:'chat_send',id:activeChat,text:content.value,notes:notes.value(),provider:provider.value,model:model.value,request_id:crypto.randomUUID()});content.value='';await poll();}finally{send.disabled=false;}});
  form.append(el('p','当前选择的接入方会收到本次消息、该接入方最近 8 轮成功对话和勾选资料。只对话，不执行任务；不同接入方的历史分别使用。','note'),field('模型接入方',provider),field('模型',model),group('本次附入的私密记忆（需要资料已允许该接入方）',notes.node),field('消息',content),send);
  const chatId=activeChat;
  async function poll(){if(pollBusy||activeChat!==chatId||!transcript.isConnected)return;pollBusy=true;clearTimeout(timer);try{const row=await command({action:'read',id:chatId});if(activeChat!==chatId)return;transcript.replaceChildren();for(const turn of row.turns){const c=el('section',undefined,'private-turn');c.append(el('small',name(turn.actor)+' · '+(turn.status==='WITHDRAWN'?'已撤回':states[turn.status]||turn.status)+' · '+turn.provider),el('p',turn.status==='WITHDRAWN'?'此段依赖的资料已改变，内容已撤回。':turn.text),el('p',turn.reply||(turn.error?errorText(turn.error):'正在生成…')));if(turn.status==='RUNNING')c.append(button('停止回答',async()=>{await command({action:'chat_cancel',id:chatId,request_id:turn.id});}));transcript.append(c);}send.disabled=row.turns.some(x=>x.status==='RUNNING');if(row.turns.some(x=>x.status==='RUNNING'))timer=setTimeout(()=>run(poll),900);}finally{pollBusy=false;}}
  await poll();
 }
 await render();
 setInterval(()=>run(async()=>{const fresh=await get('/api/family/status');if(!fresh.actor||fresh.actor.id!==actor.id){document.body.replaceChildren();location.replace('/login');}}),30000);
 document.addEventListener('visibilitychange',()=>{if(document.hidden){clearTimeout(timer);$('family-content').replaceChildren(el('p','私密内容已暂时隐藏，返回此页后重新读取。'));}else run(render);});
}
