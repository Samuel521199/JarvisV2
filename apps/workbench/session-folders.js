import {el,button,post,notice} from './ui.js';
const stable=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v);

// Each queue keeps its own conversation/revision, including after switching tabs.
export class SessionFolders{
 constructor(){this.items=new Map();}
 adopt(chat){const w=chat?.workspace;if(w?.status!=='ready')return null;let item=this.items.get(chat.id);if(!item){item={revision:w.revision,path:w.path,config:w.config,saved:stable(w.config),pending:null,running:false,timer:null,error:false};this.items.set(chat.id,item);}return item.config;}
 dirty(id){const item=this.items.get(id);return !item||item.error||!!item.pending||item.running;}
 remember(id,config){const item=this.items.get(id);if(!item||item.error)return;if(stable(config)===stable(item.config))return;item.config=structuredClone(config);item.pending=item.config;clearTimeout(item.timer);item.timer=setTimeout(()=>this.flush(id),650);}
 async flush(id){const item=this.items.get(id);if(!item||item.running||item.error||!item.pending)return;const config=item.pending;item.pending=null;if(stable(config)===item.saved)return;item.running=true;try{const result=await post('/api/chat/workspace',{id,action:'save',config,revision:item.revision});item.revision=result.revision;item.saved=stable(config);}catch(e){item.error=true;notice('会话目录保存失败：'+e.message+'。当前草稿仍留在页面，请勿关闭。');}finally{item.running=false;if(item.pending&&!item.error)this.flush(id);}}
 async view(body,id){if(!id){body.append(el('p','点击“新对话”或发送第一条消息后，将创建专属文件夹。','note'));return;}const result=await post('/api/chat/workspace',{id,action:'detail'});body.append(el('p',result.path,'note'),el('p','配置与草稿自动保存；回答和已确认的任务交付按会话归档。密钥、权限和恢复账本由 Jarvis 统一管理。','note'));
 if(result.delivery_error)body.append(el('p','部分交付尚未写入专属目录：'+result.delivery_error+'。原记录仍保留，可补齐重试。','note'));
 const row=el('div',undefined,'row');row.append(button('打开会话文件夹',()=>post('/api/chat/workspace',{id,action:'reveal'})),button('复制路径',()=>navigator.clipboard.writeText(result.path)),button('补齐交付文件',async()=>{await post('/api/chat/workspace',{id,action:'sync'});body.replaceChildren();await this.view(body,id);notice('已补齐可恢复的回答与交付文件。');}));body.append(row,el('h3','会话文件'));
 for(const file of result.files)body.append(el('p',file.path+' · '+file.bytes+' B','note'));if(!result.files.length)body.append(el('p','生成的回答和任务成果将在这里出现。','empty'));if(result.truncated)body.append(el('p','仅列出前 200 个文件；可打开目录查看全部。','note'));
 }
}
