import {el,button,card,field,post,get,modal,closeModal,notice,details,errorText,states} from './ui.js';

export function connectorControls(container,registration,connection,catalog,reload){
 const usable=registration.config.transport==='streamable-http'&&!registration.config.credential_ref;
 const status=!usable?'登记已保留 · 此传输或凭据适配尚未接入':!connection?.current?'待发现工具':connection.enabled?'已启用选定工具':'已发现 · 未启用';
 container.append(el('span',status,'badge'));
 const actions=el('div',undefined,'row');
 const discover=button(connection?.current?'重新发现（成功后需重新启用）':'连接并发现工具',async()=>{
  await post('/api/connectors/discover',{id:registration.id,revision:registration.revision});
  notice('正在后台发现工具；不会调用业务工具。聊天仍可使用。');discover.disabled=true;
  const poll=async()=>{if(!container.isConnected)return;try{const lane=await get('/api/development-runner');if(lane.status==='running'&&lane.kind==='connector'){setTimeout(poll,700);return;}if(lane.status==='failed')notice(errorText(lane.error));else notice('工具发现已完成；请选择允许使用的工具。');await reload();}catch(e){notice(e.message);discover.disabled=false;}};setTimeout(poll,700);
 });discover.disabled=!usable;actions.append(discover);
 if(connection?.current){actions.append(button('选择允许使用的工具',()=>configure(connection,reload)));
  if(connection.enabled)actions.append(button('停用此连接',async()=>{await post('/api/connectors',{action:'configure',id:connection.id,revision:connection.revision,selected:connection.selected,enabled:false});await reload();}));
 }
 container.append(actions);
 for(const tool of catalog.filter(t=>t.extension_id===registration.id)){const line=card(tool.tool_name,tool.description);line.append(button('核对参数并调用',()=>invoke(tool,reload)),button('查看输入格式',()=>details('MCP 输入格式 · 只允许列明的字段',tool.input_schema)));container.append(line);}
}

function configure(connection,reload){
 const b=modal('允许 Jarvis 使用哪些工具'),checks=[];
 b.append(el('p',connection.config.url,'note'),el('p','工具说明来自外部服务。选择后可进入个人行动计划；实际调用仍需核对参数。只读或幂等声明不作为权限保证。'));
 for(const tool of connection.tools){const c=el('input');c.type='checkbox';c.checked=connection.selected.includes(tool.name);c.disabled=!tool.supported;checks.push([tool,c]);const line=card(tool.name,tool.description);line.append(field(tool.supported?'允许进入个人能力目录':'输入结构暂不支持',c),button('查看描述与结构',()=>details(tool.name,tool)));b.append(line);}
 const error=el('p',undefined,'form-error');b.append(error,button('启用选定工具',async()=>{try{await post('/api/connectors',{action:'configure',id:connection.id,revision:connection.revision,selected:checks.filter(([t,c])=>t.supported&&c.checked).map(([t])=>t.name),enabled:true});closeModal();await reload();}catch(e){error.textContent=e.message;}},'primary'));
}

function invoke(tool,reload){
 const b=modal('核对本次外部调用'),input=el('textarea'),error=el('p',undefined,'form-error');input.rows=8;input.value='{}';input.maxLength=12000;let request=crypto.randomUUID();input.oninput=()=>request=crypto.randomUUID();
 b.append(el('h3',tool.name),el('p',tool.endpoint,'note'),el('p','本次只调用一次选定工具。工具可能产生外部效果；请确认下列参数，返回的内容保存在本机任务记录，不自动成为记忆。'),field('JSON 参数',input),el('pre',JSON.stringify(tool.input_schema,null,2)),error);
 const send=button('确认参数并调用一次',async()=>{send.disabled=true;try{const r=await post('/api/connectors',{action:'submit',request_id:request,capability:tool.capability,implementation:tool.active,revision:tool.revision,arguments:JSON.parse(input.value)});closeModal();try{await post('/api/connectors/run',{id:r.id});}catch(e){notice(e.message+' 任务已经保存，可稍后接续。');}await taskDetail(r.id,reload);await reload();}catch(e){error.textContent=e.message;}finally{send.disabled=false;}},'primary');b.append(send);
}

export async function taskDetail(id,reload){
 const d=await post('/api/connectors',{action:'detail',id}),b=modal('连接器任务 · '+(d.task.status==='READY'?'待执行':d.task.status==='RUNNING'?'执行中':states[d.task.status]||d.task.status)),watch=el('span');watch.hidden=true;b.append(watch);
 if(d.task.error)b.append(el('p',errorText(d.task.error),'form-error'));
 for(const a of d.actions){const c=card(a.result?.tool|| (a.capability==='artifact.write.v1'?'保存本机交付':'连接器调用'),a.status==='CONFIRMED'?'回执已确认':states[a.status]||a.status);if(a.error)c.append(el('p',errorText(a.error),'note'));c.append(el('pre',a.result?.text??JSON.stringify(a.result??a.arguments,null,2)));b.append(c);}
 if(!d.actions.length)b.append(el('p','任务已保存，尚未调用外部工具。'));
 b.append(button('刷新任务',()=>taskDetail(id,reload)),button('完整回执',()=>details('任务回执',d)));
 if(['READY','WAITING'].includes(d.task.status)){
  if(d.actions.some(a=>a.status==='UNKNOWN'))b.append(el('p','外部效果未知。没有持久回执时不能自动重试；请先在外部系统核对。','note'),button('只核对本机回执',async()=>{await post('/api/connectors',{action:'reconcile',id});await taskDetail(id,reload);}));
  else b.append(button('开始 / 接续此任务',async()=>{await post('/api/connectors/run',{id});await taskDetail(id,reload);await reload();},'primary'));
 }
 if(['READY','RUNNING'].includes(d.task.status))setTimeout(()=>{if(watch.isConnected&&b.closest('dialog')?.open)taskDetail(id,reload).catch(e=>notice(e.message));},800);
 if(!['SUCCEEDED','FAILED','CANCELLED'].includes(d.task.status))b.append(button('取消此任务',async()=>{await post('/api/connectors',{action:'cancel',id});await taskDetail(id,reload);await reload();}));
}
