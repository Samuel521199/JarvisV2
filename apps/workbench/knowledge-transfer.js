import {el,button,field,post,get,run,modal,closeModal,notice,download,errorText} from './ui.js';

// Preserve the file's JSON bytes until the strict server decoder checks duplicate
// keys. JSON.parse + JSON.stringify would silently discard those duplicates.
async function transfer(action,scope,raw,token){
 const session=await get('/api/session');
 const fields=JSON.stringify({action,scope,...(action==='restore'?{token}:{})});
 const body=fields.slice(0,-1)+`,"bundle":${raw}}`;
 const response=await fetch('/api/knowledge-transfer',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':session.token},body});
 const value=await response.json();if(!response.ok)throw Error(({knowledge_bundle_invalid:'资料包格式、版本或校验摘要不正确，未写入。',knowledge_restore_conflict:'资料恢复存在冲突，请重新预览。',knowledge_transfer_size:'资料包超过当前传输上限。',invalid_json:'资料包不是有效 UTF-8 JSON，或包含重复字段、无效数值。'})[value.error]||errorText(value.error));return value;
}

export function transferButtons(toolbar,{getScope,onChange}){
 toolbar.append(button('导出此范围资料包',()=>{
  const scope=getScope(),body=modal('导出本地资料包');
  body.append(el('p','导出当前范围的资料原文、修订和删除墓碑。JSON 文件是明文，请自行妥善保管；不包含密钥、聊天记录、已核对记忆或检索索引。','note'),button('下载资料包',async()=>{const bundle=await post('/api/knowledge',{action:'export',scope});download('jarvis-knowledge-v1.json',JSON.stringify(bundle));closeModal();}));
 }),button('从资料包恢复',()=>{
  const scope=getScope(),body=modal('预览资料恢复'),file=el('input'),result=el('div');file.type='file';file.accept='.json';
  body.append(el('p',`恢复到当前范围：${scope}。新建或替换的资料将暂停引用且关闭全部模型接入方许可。当前库有删除墓碑时，旧原文不会恢复。资料包包含的删除记录也会生效。`,'note'),field('JSON 资料包（最多 40 MB）',file),result);
  let selection=0;
  file.onchange=()=>run(async()=>{
   const serial=++selection;
   const selected=file.files?.[0];result.replaceChildren();if(!selected)return;
   if(selected.size>39999000)throw Error('资料包超过 40 MB。');
   const raw=new TextDecoder('utf-8',{fatal:true}).decode(await selected.arrayBuffer());
   const plan=await transfer('restore_preview',scope,raw,null);if(!result.isConnected||selection!==serial)return;
   const c=plan.counts;result.append(el('p',`新增 ${c.create} · 替换 ${c.replace} · 删除 ${c.delete} · 新墓碑 ${c.tombstone} · 无变化 ${c.unchanged} · 已删除跳过 ${c.skip_deleted} · 冲突 ${c.conflict}`));
   const items=el('details'),labels={create:'新增',replace:'替换',delete:'删除',tombstone:'登记墓碑',unchanged:'保留',skip_deleted:'跳过已删除',conflict:'冲突'};items.append(el('summary','查看逐项处理清单'));for(const a of plan.actions)items.append(el('p',`${labels[a.action]} · ${a.title||a.id} · r${a.revision}${a.reason?' · '+({different_scope:'ID 属于其他范围',newer_or_divergent_local:'本地较新或内容分叉'}[a.reason]||a.reason):''}`,'note'));result.append(items);
   if(plan.source_scope!==scope)result.append(el('p',`原范围 ${plan.source_scope} → 当前范围 ${scope}。仅本次明确映射；不会建立共享关系。`,'note'));
   if(!plan.can_apply){result.append(el('p',plan.capacity_ok?'存在较新本地内容、同修订分叉或跨范围 ID 冲突。整包未写入；请核对原文件，不能强制覆盖。':'恢复后会超过 200 份有效资料上限。整包未写入。','form-error'));return;}
   const apply=button('按此预览恢复',async()=>{apply.disabled=true;try{const r=await transfer('restore',scope,raw,plan.token);closeModal();await onChange();notice(`资料包处理完成，变更 ${r.applied} 项。恢复资料需重新选择接入方并恢复引用。`);}finally{apply.disabled=false;}});result.append(apply);
  });
 }),button('清理失效记忆与资料',()=>cleanup(getScope(),onChange)));
}

function cleanup(scope,onChange){
 const body=modal('失效记忆 / 资料 · 派生清理'),report=el('div'),history=el('div');
 body.append(el('p','先预览，再清理依赖旧修订、已暂停或已遗忘记忆与资料的聊天回复、目标背景、已结束任务的派生计划与模型结果。整条受影响回复会被占位说明替代；原始提问保留。依赖编号仍保留，旧任务不会因清空背景而重新获准。受管目录中未修改的回复副本和任务产物也会清理，并禁止重新同步；进行中或回执不明的任务暂缓。','note'),el('p','不清理：原始提问、自主研发代码与包、来源不明的内容、用户改过的文件、导出、备份、外部模型副本或 SQLite 可恢复页。此操作不能撤回，资料包也不备份这些回复。','note'),report,history);
 const first={goals:'',turns:''};
 async function preview(cursor){
  const plan=await post('/api/knowledge',{action:'cleanup_preview',scope,cursor});if(!report.isConnected)return;
  report.replaceChildren(el('p',`本批：${plan.counts.turns} 条回复 · ${plan.counts.goals} 个目标背景 · ${plan.counts.tasks} 个已结束任务 · ${plan.counts.model_results} 条模型结果 · ${plan.counts.busy_goals} 个目标暂缓 · ${plan.counts.busy_turns} 条进行中暂缓 · ${plan.counts.unknown_provenance} 条来源未知未处理。`));
  const targets=el('details');targets.append(el('summary','查看受影响的会话与目标'));for(const t of plan.targets.turns)targets.append(el('p',`${t.title} · ${t.id}`,'note'));for(const id of plan.targets.goals)targets.append(el('p','目标背景 · '+id,'note'));report.append(targets);
  const controls=el('div',undefined,'row');report.append(controls);
  if(plan.counts.turns+plan.counts.goals){const apply=button('清理本批正文',async()=>{apply.disabled=true;try{const r=await post('/api/knowledge',{action:'cleanup',scope,cursor,token:plan.token});await onChange();await receipts();await preview(cursor);notice(r.receipt.state==='completed'?'本批受管正文已清理，其他副本不在范围内。':'部分步骤未完成，请重新预览后重试。');}finally{apply.disabled=false;}},'danger');controls.append(apply);}
  controls.append(button('重新从头检查',()=>preview(first)));
  if(plan.has_more)controls.append(button('检查下一批',()=>preview(plan.next_cursor)));
  else report.append(el('p','已到本轮扫描末尾；进行中或来源未知的记录、排除范围不算清理完成。','note'));
 }
 async function receipts(){const r=await post('/api/knowledge',{action:'cleanup_status',scope});if(!history.isConnected)return;history.replaceChildren(el('h3','最近清理回执'));for(const f of r.files||[])history.append(el('p',`派生文件 · ${f.id} · ${{pending:'待重试',modified_preserved:'用户修改过，已保留',cleared:'已清理并禁止重新同步',absent:'不存在，已禁止重新同步'}[f.state]}${f.error?' · '+f.error:''}`,'note'));for(const v of r.receipts.slice(0,10))history.append(el('p',`${new Date(v.created*1000).toLocaleString()} · ${{completed:'本批完成',partial:'部分完成，可重新预览',pending:'中断或待完成，请重新预览'}[v.state]} · 背景 ${v.goals} / 回复 ${v.turns}${v.error?' · '+v.error:''}`,'note'));}
 body.append(button('重试未完成的派生文件清理',async()=>{const v=await post('/api/knowledge',{action:'retry_cleanup_files',scope});await receipts();notice(`已清理 ${v.cleared} · 文件不存在 ${v.absent} · 待处理 ${v.pending} · 用户修改保留 ${v.modified_preserved}`);}));
 run(async()=>{await preview(first);await receipts();});
}
