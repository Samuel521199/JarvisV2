import {el,button,input,select,field,post,run,modal,closeModal,notice} from './ui.js';
import {sourceBranch} from './memory-source-merge.js';
const kinds={branch:'项目分支',task:'独立任务范围',world:'模拟世界'};

async function mergeBranch(scope,onChange){
 const plan=await post('/api/memory-domains',{action:'merge_preview',scope}),body=modal('逐项合并分支记忆'),choices={},error=el('p',undefined,'form-error');
 body.append(el('p','对照分支起点、主项目当前值和分支值，逐项选择。采用分支值会成为你在主项目独立确认的事实，并暂停模型使用，等待重新设置接入方。已遗忘的主项目条目不能复活。资料原文请使用“原文 / 章节合并”。','note'));
 const labels={forgotten:'主项目已遗忘 · 禁止复活',unchanged:'没有需要合并的变动',conflict:'双方已改动 · 需要选择',delete:'分支已遗忘',replace:'可更新主项目',create:'主项目新增'};
 for(const row of plan.items){
  const card=el('section',undefined,'card');card.append(el('h3',row.key),el('p',labels[row.state],'note'),el('pre',`分支起点：${row.base??'无'}\n主项目：${row.parent_value??'无 / 已遗忘'}\n此分支：${row.branch_value??'已遗忘'}`));
  if(!['forgotten','unchanged'].includes(row.state)){const choice=select([['parent','保留主项目'],['branch',row.branch_value===null?'在主项目也遗忘':'采用分支值']]);choices[row.id]=choice;card.append(field('本项决定',choice));}
  body.append(card);
 }
 if(!plan.items.length)body.append(el('p','此分支尚未单独修改事实。','empty'));
 const apply=button('应用这些决定',async()=>{apply.disabled=true;try{const result=await post('/api/memory-domains',{action:'merge',scope,token:plan.token,choices:Object.fromEntries(Object.entries(choices).map(([id,e])=>[id,e.value]))});closeModal();await onChange();notice(`已合并 ${result.changed} 项，保留主项目 ${result.kept_parent} 项。`);}catch(e){error.textContent=e.message;}finally{apply.disabled=false;}});
 body.append(error,apply);
}

export async function domainControls(toolbar,{selectScope,projects,chatId,onChange,getProvider}){
 const baseOptions=[['personal','我的个人记忆'],...projects.filter(p=>!p.removed).map(p=>[p.id,'项目 · '+p.name])];
 let domains=[],binding=null,serial=0,bindButton=null;
 const hint=el('p',undefined,'note');toolbar.after(hint);
 const parent=()=>domains.find(d=>d.id===selectScope.value)?.parent||selectScope.value;
 async function refresh(keep=selectScope.value){
  const generation=++serial,p=domains.find(d=>d.id===keep)?.parent||keep;
  const r=await post('/api/memory-domains',{action:'list',parent:p});if(generation!==serial||!toolbar.isConnected)return;
  domains=r.domains;selectScope.replaceChildren();for(const [id,title] of [...baseOptions,...domains.filter(d=>!d.archived).map(d=>[d.id,kinds[d.kind]+' · '+d.name])]){const o=el('option',title);o.value=id;selectScope.append(o);}selectScope.value=keep;
  if(!selectScope.value)selectScope.value=p;
  if(chatId)binding=await post('/api/memory-domains',{action:'binding',chat_id:chatId});
  if(bindButton)bindButton.disabled=!!binding&&binding.parent!==p;
  const d=domains.find(d=>d.id===selectScope.value);
  hint.textContent=(d?`${kinds[d.kind]}：本页显示本范围编辑的内容。分支继承的快照可在“按问题检索”核对；父范围当前撤回与许可仍有效。`:'个人、项目与模拟世界分开使用。')+(binding?` 当前会话使用：${binding.label||baseOptions.find(([id])=>id===binding.scope)?.[1]||binding.scope}。选择查看范围不会自动切换会话。`:'');
 }
 toolbar.append(button('范围 / 分支',()=>{
  const p=parent(),body=modal('记忆范围与分支'),name=input(''),kind=select(Object.entries(kinds).filter(([k])=>k!=='branch'||p!=='personal')),snapshot=el('input'),form=el('form'),submit=el('button','创建范围','primary'),error=el('p',undefined,'form-error');name.required=true;name.maxLength=80;snapshot.type='checkbox';snapshot.checked=true;
  const snapField=field('以当前项目资料与记忆建立引用快照',snapshot);snapField.hidden=kind.value!=='branch';kind.onchange=()=>{snapField.hidden=kind.value!=='branch';};submit.type='submit';
  body.append(el('p','分支固定原修订，独立修改不会改变主项目。任务范围和模拟世界初始为空，不继承个人资料。这里不会创建 Git 分支，也不改变文件或执行权限。','note'));
  form.append(field('名称',name),field('类型',kind),snapField,error,submit);body.append(form);
  form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{const d=await post('/api/memory-domains',{action:'create',parent:p,kind:kind.value,name:name.value,snapshot:kind.value==='branch'&&snapshot.checked});domains.push(d);closeModal();await refresh(d.id);await onChange();notice('记忆范围已建立；可明确应用到当前会话。');}catch(e){error.textContent=e.message;}finally{submit.disabled=false;}};
  const list=el('div');body.append(list);for(const d of domains){const row=el('div',undefined,'row');row.append(el('span',`${kinds[d.kind]} · ${d.name}${d.archived?'（已归档）':''}`),button(d.archived?'恢复':'归档',async()=>{await post('/api/memory-domains',{action:'archive',id:d.id,revision:d.revision,archived:!d.archived});closeModal();await refresh(p);await onChange();}));if(d.kind==='branch'&&!d.archived)row.append(button('审阅事实合并',()=>mergeBranch(d.id,onChange)),button('原文 / 章节合并',()=>sourceBranch(d.id,async()=>{await refresh(d.id);await onChange();})));list.append(row);}
 }));
 toolbar.append(button('联合检索',()=>{
  const body=modal('明确选择联合使用的范围'),choices=el('div'),query=input(''),results=el('div'),error=el('p',undefined,'form-error'),checks=[];
  body.append(el('p','仅检索明确勾选的 2–4 个范围，各条保留出处；其他项目不参与。个人记忆需要单独勾选。联合范围不能保存或修改事实，写入时须选定一个具体范围。','note'));
  for(const [id,title] of [...baseOptions,...domains.filter(d=>!d.archived).map(d=>[d.id,kinds[d.kind]+' · '+d.name])]){
   const box=el('input');box.type='checkbox';box.checked=id===(binding?.parent||parent());checks.push([id,box]);choices.append(field(title,box));
  }
  const chosen=()=>{const ids=checks.filter(([,box])=>box.checked).map(([id])=>id).sort();if(ids.length<2||ids.length>4)throw Error('请明确选择 2–4 个范围');return 'joint:'+ids.join(',');};
  const preview=button('预览所选范围',async()=>{error.textContent='';try{
   const provider=getProvider();
   if(!provider)throw Error('请先在记忆面板选择模型接入方');
   const r=await post('/api/memory',{action:'recall',scope:chosen(),provider,enabled:true,query:query.value});results.replaceChildren();
   for(const row of r.facts)results.append(el('p',`${[...baseOptions,...domains.map(d=>[d.id,d.name])].find(([id])=>id===row.origin_scope)?.[1]||row.origin_scope} · ${row.key}\n${row.value}`));
   if(!r.facts.length)results.append(el('p','没有找到当前接入方获准使用的相关内容。'));
  }catch(e){error.textContent=e.message;}});
  body.append(choices,field('检索问题',query),error,preview,results);
  if(chatId)body.append(button('应用到当前会话',async()=>{error.textContent='';try{
   const latest=await post('/api/memory-domains',{action:'binding',chat_id:chatId});
   await post('/api/memory-domains',{action:'bind',chat_id:chatId,scope:chosen(),revision:latest.revision});closeModal();await refresh();notice('后续对话将使用明确选定的联合范围。');
  }catch(e){error.textContent=e.message;}}));
 }));
 if(chatId){bindButton=button('让当前会话使用所选范围',async()=>{
  const latest=await post('/api/memory-domains',{action:'binding',chat_id:chatId});
  await post('/api/memory-domains',{action:'bind',chat_id:chatId,scope:selectScope.value,revision:latest.revision});await refresh();notice('会话已切换记忆范围。后续回复不会带入其他范围的旧对话。');
 });toolbar.append(bindButton);}
 await refresh();return {refresh};
}
