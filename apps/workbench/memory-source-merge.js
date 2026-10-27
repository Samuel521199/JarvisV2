import {el,button,field,select,post,modal,closeModal,notice} from './ui.js';

const labels={unchanged:'无需合并',forgotten:'主项目已遗忘 · 禁止复活',missing_base:'缺少分支起点 · 不可合并',create:'分支新增资料',replace:'主项目未修改 · 可采用分支',delete:'分支已删除 · 等待你的决定',combined:'不同位置修改 · 可组合',conflict:'重叠修改 · 需要选择'};

export async function sourceBranch(scope,onChange){
 const [plan,inherited]=await Promise.all([post('/api/memory-domains',{action:'source_merge_preview',scope}),post('/api/memory-domains',{action:'source_inherited',scope})]);
 const body=modal('原文 / 章节合并'),error=el('p',undefined,'form-error'),choices={};
 body.append(el('p','按原文行与章节比对分支起点、主项目和分支稿。不同位置的修改可组合；重叠修改由你决定。采用的资料仍是参考原文，合并后暂停引用，模型接入方需要重新选择。','note'));
 const originals=el('details',undefined,'card');originals.append(el('summary',`继承资料 · ${inherited.sources.length} 份`));
 originals.append(el('p','为要修改的继承原文建立分支稿，再到此分支的本地资料库编辑。分支稿继续受主项目当前许可约束；主项目遗忘原文时也会撤回分支稿。','note'));
 for(const source of inherited.sources){const row=el('div',undefined,'row');row.append(el('span',`${source.title} · 起点 r${source.base_revision}${source.branch_id?' · 已建立分支稿':''}`));if(!source.branch_id)row.append(button('建立分支稿',async()=>{error.textContent='';try{await post('/api/memory-domains',{action:'source_fork',scope,id:source.id,revision:source.base_revision});closeModal();await onChange();notice('分支稿已建立并暂停引用，请在本地资料库打开修改。');}catch(e){error.textContent=e.message;}}));originals.append(row);}
 body.append(originals);
 for(const item of plan.items){
  const card=el('section',undefined,'card'),comparison=el('details'),content=el('div',undefined,'source-merge-comparison');
  card.append(el('h3',item.title),el('p',`${labels[item.state]} · 分支 r${item.revision} / 主项目 r${item.parent_revision}`,'note'));
  comparison.append(el('summary','展开原文对照'),content);let loaded=false;
  comparison.ontoggle=async()=>{if(!comparison.open||loaded)return;loaded=true;content.textContent='正在读取…';try{const detail=await post('/api/memory-domains',{action:'source_merge_detail',scope,id:item.id});if(detail.revision!==item.revision)throw Error('分支已变化，请重新打开合并预览。');content.replaceChildren();for(const [key,label] of [['base','分支起点'],['parent','主项目当前'],['branch','分支稿'],['combined','可组合结果']]){if(key==='combined'&&!detail[key])continue;const column=el('section');column.append(el('h4',label),el('pre',detail[key]?detail[key].title+'\n\n'+detail[key].text:'无 / 已遗忘'));content.append(column);}}catch(e){content.textContent=e.message;loaded=false;}};
  card.append(comparison);
  if(!['forgotten','missing_base','unchanged'].includes(item.state)){const options=[['parent','保留主项目'],['branch',item.state==='delete'?'在主项目也删除':'采用分支稿']];if(item.combined_available)options.push(['combined','采用组合结果']);const choice=select(options);choices[item.id]=choice;card.append(field('本项决定',choice));}
  body.append(card);
 }
 if(!plan.items.length)body.append(el('p','此分支还没有新增或修改的资料。可先展开继承资料，建立分支稿。','empty'));
 const apply=button('应用资料合并决定',async()=>{apply.disabled=true;error.textContent='';try{const result=await post('/api/memory-domains',{action:'source_merge',scope,token:plan.token,choices:Object.fromEntries(Object.entries(choices).map(([id,e])=>[id,e.value]))});closeModal();await onChange();notice(`资料合并完成：更改 ${result.changed} 份，保留主项目 ${result.kept_parent} 份。`);}catch(e){error.textContent=e.message;}finally{apply.disabled=false;}});
 apply.disabled=!Object.keys(choices).length;body.append(error,apply);
}
