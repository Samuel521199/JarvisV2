import {el,button,post,modal} from './ui.js';

export async function memoryHealth(scope){
 const value=await post('/api/memory',{action:'health',scope}),body=modal('记忆与资料健康');
 body.append(el('p','检查当前范围的记录关系与全库索引覆盖；不会修改记忆，也不把结构正常当成知识正确。','note'));
 const labels={facts:'有效事实',forgotten:'遗忘墓碑',pending_candidates:'待核对记忆',sources:'资料原件',pending_claims:'待审阅知识',history_versions:'历史修订',unknown_history_time:'保存时间未知的历史'};
 const grid=el('table',undefined,'memory-health-metrics'),rows=el('tbody');grid.setAttribute('aria-label','当前范围记录统计');for(const [key,n] of Object.entries(value.counts)){const row=el('tr'),label=el('th',labels[key]||key);label.scope='row';row.append(label,el('td',String(n)));rows.append(row);}grid.append(rows);body.append(grid);
 body.append(el('p',`全文索引：${!value.fts.available?'未构建或不可用':value.fts.consistent?'覆盖一致':'覆盖缺失，需要重建'} · 语义索引：${!value.vectors.active?'未构建':!value.vectors.recipe_current?'配方已升级，需要重建':value.vectors.stale?'资料有变化，需要续建':'当前版本可用'}（${value.vectors.count} 条）`,'note'));
 const messages={invalid_claim_dependency:'知识候选的来源或事实关系失效，需要复核',orphan_history:'检测到不再有有效原件的历史记录，需要核对清理',fts_coverage:'全文索引缺失或有孤立行',fts_unavailable:'全文索引不可读取'};
 if(!value.issues.length)body.append(el('p','本次覆盖的结构检查未发现异常。未检查语义真伪、未知外部副本、全部磁盘损坏或家庭隐私。','note'));
 for(const issue of value.issues)body.append(el('p',`${messages[issue.code]||issue.code}：${issue.count} 项`,'form-error'));
 const progress=el('p',undefined,'note');progress.setAttribute('aria-live','polite');
 body.append(button('重新检查',()=>memoryHealth(scope)),button('重建全文索引',async()=>{await post('/api/knowledge',{action:'rebuild'});progress.textContent='后台重建已提交，完成后点“重新检查”；可在本地资料库查看状态或取消。';}),button('构建 / 续建语义索引',async()=>{await post('/api/knowledge',{action:'rebuild_vectors'});progress.textContent='后台续建已提交，需已启动并设定本地嵌入模型；可在资料库查看结果。';}),progress,el('small',`检查耗时 ${value.elapsed_ms} ms · ${value.version}`,'note'));
}
