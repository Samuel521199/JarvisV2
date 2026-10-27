import {el,button,field,post,get,run,modal,closeModal,notice,download} from './ui.js';

export async function history(scope,kind,id){
 const body=modal('修订记录'),r=await post('/api/memory',{action:'history',scope,kind,id});
 if(!body.isConnected)return;
 body.append(el('p','仅供核对历史，不会把旧修订重新送入对话。这里记录系统保存时间；未知的旧时间不会推算。遗忘原件会清除此处正文。','note'));
 if(!r.versions.length)body.append(el('p','当前记录建立于修订追踪启用之前；还没有后续修订。','note'));
 for(const v of r.versions){const d=el('details');d.append(el('summary',`r${v.revision} · ${v.recorded?new Date(v.recorded*1000).toLocaleString():'旧记录保存时间未知'}`),el('pre',v.body.text??v.body.value));body.append(d);}
}

export async function origin(scope,id){
 const body=modal('导入来源'),r=await post('/api/memory-transfer',{action:'origin',scope,id});
 if(!body.isConnected)return;
 body.append(el('p','这是导入包携带的来源记录，可帮助人工核对；摘要校验只能发现损坏，不能证明文件作者或外部任务实际执行成功。','note'),el('pre',JSON.stringify(r.origin,null,2)));
}

async function restore(action,scope,raw,token){
 const session=await get('/api/session'),fields=JSON.stringify({action,scope,...(token?{token}:{})});
 const response=await fetch('/api/memory-transfer',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':session.token},body:fields.slice(0,-1)+',"bundle":'+raw+'}'});
 const result=await response.json();if(!response.ok)throw Error(({conflict:'资料已变化，请重新预览。',memory_restore_conflict:'存在分叉或范围冲突，整包未写入。',memory_bundle_invalid:'记忆包格式或校验失败，未写入。',invalid_json:'JSON 包含无效值或重复字段。'})[result.error]||'无法恢复：'+result.error);return result;
}

export function portability(toolbar,{getScope,onChange}){
 toolbar.append(button('迁移 / 恢复记忆',()=>{
  const scope=getScope(),body=modal('记忆迁移 · v1.0.0'),file=el('input'),result=el('div');file.type='file';file.accept='.json';
  body.append(el('p','将当前范围的记忆、资料、候选、来源审阅、修订历史和可获取的来源凭据保存为公开 JSON。新机器恢复后默认暂停、关闭模型外发；本地删除记录优先。文件为明文，包含个人内容。','note'),el('p','不迁移密钥、模型权重、授权、正在运行的任务、整份聊天或外部文件。原聊天不等于长期记忆；此包保存的是记忆对象及其引用的来源证据。','note'),button('下载单范围记忆包',async()=>{const bundle=await post('/api/memory-transfer',{action:'export',scope});download('jarvis-memory-bundle-v1.json',JSON.stringify(bundle));}),button('下载父范围与全部分支包',async()=>{const bundle=await post('/api/memory-transfer',{action:'export_collection',scope});download('jarvis-memory-collection-v2.json',JSON.stringify(bundle));}),el('p','完整保留分支快照与原文依赖时，请先选择父项目（或个人根），再下载父范围与全部分支包。单范围包只含本范围自己的对象，不含父范围原件。已有原文分支稿时须下载整组包。恢复的域保持归档，需明确恢复后使用。','note'),field('选择要恢复的记忆包（最多 40 MB）',file),result);
  let generation=0;
  file.onchange=()=>run(async()=>{
   const serial=++generation,selected=file.files?.[0];result.replaceChildren();if(!selected)return;
   if(selected.size>39999000)throw Error('记忆包超过 40 MB。');
   const raw=new TextDecoder('utf-8',{fatal:true}).decode(await selected.arrayBuffer()),p=await restore('preview',scope,raw);
   if(!result.isConnected||serial!==generation)return;
   const plans=p.plans?.map(x=>x.plan)||[p],allFacts=plans.flatMap(x=>x.facts),sourceCounts=plans.reduce((a,x)=>{for(const [k,v] of Object.entries(x.sources.counts))a[k]=(a[k]||0)+v;return a;},{});
   const counts=allFacts.reduce((a,r)=>(a[r.action]=(a[r.action]||0)+1,a),{}),labels={create:'新增',replace:'替换',delete:'删除',tombstone:'登记删除',unchanged:'保留',skip_deleted:'已遗忘跳过',conflict:'冲突'};
   result.append(el('p',`记忆：${Object.entries(counts).map(([k,v])=>(labels[k]||k)+' '+v).join(' · ')||'0 条'}；资料：新增 ${sourceCounts.create} / 替换 ${sourceCounts.replace} / 删除 ${sourceCounts.delete} / 冲突 ${sourceCounts.conflict}`));
   if((p.source_root||p.sources?.source_scope)!==scope)result.append(el('p',`原范围 ${p.source_root||p.sources?.source_scope} → 当前范围 ${scope}。仅明确迁入，未建立持续分享。`,'note'));
   const details=el('details');details.append(el('summary','逐项预览'));for(const a of allFacts)details.append(el('p',`${labels[a.action]} · ${a.key} · ${a.id}`,'note'));for(const a of plans.flatMap(x=>x.sources.actions))details.append(el('p',`${labels[a.action]} · ${a.title||a.id}`,'note'));result.append(details);
   if(!p.can_apply){result.append(el('p','发现冲突或超出容量；全部内容保持原样。请先核对原包与本地版本。','form-error'));return;}
   result.append(button('按预览恢复记忆包',async()=>{await restore('restore',scope,raw,p.token);closeModal();await onChange();notice('记忆包已处理。新恢复内容保持暂停，请核对后设置使用范围。');}));
  });
 }));
}
