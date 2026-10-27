import {history} from './memory-portability.js';
import {el,button,field,input,post,run,modal,closeModal,notice,card,download} from './ui.js';
import {transferButtons} from './knowledge-transfer.js';
import {claimsButton} from './knowledge-claims.js';
import {extractSource,extractionJobs} from './knowledge-extraction.js';

const indexErrors={model_not_loaded:'请先启动本地嵌入模型',model_not_selected:'请将运行中的嵌入模型设为默认',model_busy:'本地模型繁忙，请稍后续建',model_space_changed:'模型已切换，请重新构建',knowledge_changed:'资料有变更，请续建',knowledge_cancelled:'已取消，已保存批次可续建',local_timeout:'本地编码超时，请重启模型后续建'};
const indexStates={idle:'未启动重建',queued:'等待重建',running:'正在重建',succeeded:'重建完成',failed:'重建失败，可重试',cancelled:'已取消重建'};
export function knowledgeView(parent,{settings,getScope,onChange}){
 const mount=el('details',undefined,'card'),toolbar=el('div',undefined,'row'),status=el('p',undefined,'note'),list=el('div'),filter=input('','搜索资料标题');
 mount.append(el('summary','本地资料库 · v1.2.0'),el('p','导入 TXT / Markdown 或粘贴原文。资料保留版本和片段位置，作为参考证据，不自动成为已核对事实。每份最多 80,000 字节。','note'),toolbar,filter,status,list);parent.append(mount);
 let generation=0,rows=[],timer=null;
 toolbar.append(button('导入 / 粘贴资料',()=>edit()),button('刷新资料',load),button('重建检索索引',async()=>{await post('/api/knowledge',{action:'rebuild'});await poll();}),button('构建 / 续建语义索引',async()=>{await post('/api/knowledge',{action:'rebuild_vectors'});await poll();}),button('取消重建',async()=>{await post('/api/knowledge',{action:'cancel_rebuild'});await poll();}));
 filter.type='search';filter.setAttribute('aria-label','搜索资料标题');filter.oninput=draw;
 transferButtons(toolbar,{getScope,onChange:changed});
 claimsButton(toolbar,{getScope,onChange:changed});
 toolbar.append(button('知识提取任务',()=>extractionJobs(getScope())));
 async function poll(){if(!mount.isConnected)return;clearTimeout(timer);const value=await post('/api/knowledge',{action:'index_status'});if(!mount.isConnected)return;status.textContent=(value.available?'持久全文索引可用':'当前使用扫描检索')+' · '+indexStates[value.state]+' · 已处理 '+value.processed+' 片段'+(value.error?' · '+(indexErrors[value.error]||value.error):'')+' · 语义向量 '+value.vectors.vectors+' 条'+(value.vectors.active?(value.vectors.recipe_current===false?'（切片配方已更新，请构建新索引）':value.vectors.stale?'（资料有变化，请续建）':'（已持久保存）'):'（尚未构建，需要先启动并设定本地嵌入模型）')+(value.vectors.staging.length?' · 可续建 '+value.vectors.staging.reduce((n,s)=>n+s.vectors,0)+' 条已保存向量':'')+(value.result?.reconcile_attempts?' · 增量核对 '+value.result.reconcile_attempts+' 次':'');if(['queued','running'].includes(value.state))timer=setTimeout(()=>run(poll),700);}
 async function load(){const g=++generation,scope=getScope();rows=[];list.replaceChildren();const value=await post('/api/knowledge',{action:'list',scope});if(g!==generation||!mount.isConnected||scope!==getScope())return;rows=value.sources;draw();await poll();}
 function draw(){list.replaceChildren();const visible=rows.filter(r=>r.title.toLocaleLowerCase().includes(filter.value.toLocaleLowerCase()));if(!visible.length)list.append(el('p','此范围尚无符合条件的资料。','empty'));for(const r of visible){const c=card(r.title,`${r.status==='paused'?'已暂停':'可用'} · r${r.revision} · ${r.chunks} 片段 · ${(r.bytes/1024).toFixed(1)} KiB`),actions=el('div',undefined,'row');c.append(el('p','模型接入方：'+(r.providers.map(p=>settings.connections.find(c=>c.id===p)?.label||p).join('、')||'仅本地保存'),'note'));actions.append(button('模型提取候选',()=>extractSource(r,settings)),button('修订记录',()=>history(r.scope,'source',r.id)),button('编纂知识候选',async()=>{const v=await post('/api/knowledge',{action:'compile',scope:r.scope,id:r.id,revision:r.revision});notice(`已提出 ${v.added} 个待审阅候选，请打开“知识候选 / 来源审阅”。`);}),button('查看原文 / 修改',async()=>{const v=await post('/api/knowledge',{action:'detail',scope:r.scope,id:r.id});if(getScope()===r.scope)edit(v);}),button(r.status==='paused'?'恢复引用':'暂停引用',async()=>{const v=await post('/api/knowledge',{action:'detail',scope:r.scope,id:r.id});await save({...v,paused:r.status!=='paused'});await changed();}),button('删除入库副本',()=>{const body=modal('删除入库资料');body.append(el('p','将清除本资料的入库原文、片段和全文索引，撤销后续引用。不会删除电脑上的原文件，也不会清除历史聊天、任务输出、导出或备份。'),button('删除入库副本',async()=>{await post('/api/knowledge',{action:'delete',scope:r.scope,id:r.id,revision:r.revision});closeModal();await changed();},'danger'));}));c.append(actions);list.append(c);}}
 async function save(v){return post('/api/knowledge',{action:'save',revision:v.revision||0,item:{id:v.id||'',scope:v.scope,title:v.title,text:v.text,providers:v.providers,paused:!!v.paused}});}
 async function changed(){await onChange();await load();}
 function edit(row=null){const scope=row?.scope||getScope(),body=modal(row?'资料原文与使用范围':'导入本地资料'),form=el('form'),title=input(row?.title||''),text=el('textarea'),file=el('input'),destinations=el('fieldset'),error=el('p',undefined,'form-error'),submit=el('button','保存资料','primary');
  title.required=true;title.maxLength=160;text.required=true;text.rows=12;text.value=row?.text||'';file.type='file';file.accept='.txt,.md,.markdown';submit.type='submit';
  file.onchange=()=>run(async()=>{const f=file.files?.[0];if(!f)return;if(f.size>80000||! /\.(txt|md|markdown)$/i.test(f.name))throw new Error('请选择不超过 80,000 字节的 TXT / Markdown 文件。');text.value=new TextDecoder('utf-8',{fatal:true}).decode(await f.arrayBuffer());title.value=f.name;});
  destinations.append(el('legend','允许这些模型接入方引用资料'));const checks=[],seen=new Set();for(const p of [...settings.connections,{id:'codex-cli',label:'外部 Codex 编码通道'}]){if(seen.has(p.id))continue;seen.add(p.id);const c=el('input');c.type='checkbox';c.value=p.id;c.checked=!!row?.providers.includes(p.id);checks.push(c);destinations.append(field(p.label,c));}
  form.append(field('本地 UTF-8 文本文件（可选）',file),field('资料标题',title),field('原文',text),destinations,el('p',row?`来源 ${row.id} · r${row.revision}。保存会替换入库版本；旧引用随即失效。`:'不选择模型接入方时只保存于本地。导入不会调用云端模型。','note'),error,submit);
  if(row)form.append(button('导出原文',()=>download('jarvis-source.txt',text.value)));
  form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{if(new TextEncoder().encode(text.value).length>80000)throw new Error('原文超过 80,000 字节。');const result=await save({id:row?.id,revision:row?.revision,scope,title:title.value,text:text.value,paused:row?.status==='paused',providers:[...new Set([...checks.filter(c=>c.checked).map(c=>c.value),...(row?.providers||[]).filter(p=>!seen.has(p))])]});closeModal();await changed();const state=await post('/api/knowledge',{action:'index_status'});if(!state.available){await post('/api/knowledge',{action:'rebuild'});await poll();}notice(result.existing?'相同资料已存在，保留原有使用范围。':'资料已保存，后续引用使用当前版本。');}catch(e){error.textContent=e.message;}finally{submit.disabled=false;}};body.append(form);
 }
 run(load);return {reload:load};
}

export async function showSource(scope,evidence){
 const row=evidence.snapshot_domain?await post('/api/memory-domains',{action:'source',scope,id:evidence.source_id,revision:evidence.revision}):await post('/api/knowledge',{action:'detail',scope,id:evidence.source_id});
 const body=modal(row.title+' · r'+row.revision);
 if(row.revision!==evidence.revision){body.append(el('p','资料版本已变化，请重新检索。','note'));return;}
 body.append(el('p',`来源 ${row.id} · 第 ${evidence.line_start}–${evidence.line_end} 行；仅说明原文记载，未经事实核验。`,'note'),el('pre',Array.from(row.text).slice(evidence.start,evidence.end).join('')));
}
