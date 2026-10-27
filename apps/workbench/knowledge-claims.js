import {el,button,field,input,post,modal,closeModal,notice,run} from './ui.js';

export function claimsButton(toolbar,{getScope,onChange}){
 toolbar.append(button('知识候选 / 来源审阅',()=>review(getScope(),onChange)));
}

async function review(scope,onChange){
 const body=modal('知识编纂与审阅'),list=el('div');
 body.append(el('p','编纂器按原文片段提出候选，不调用云端、不自动宣称真实。请核对来源，修改为准确、独立的知识后再收入记忆；来源修订、暂停或删除会自动撤回其派生知识。','note'),list);
 async function load(){
  const value=await post('/api/knowledge',{action:'claims',scope});if(!list.isConnected)return;
  list.replaceChildren();const labels={pending:'待审阅',accepted:'已收入记忆',withdrawn:'来源失效 / 已遗忘',dismissed:'已拒绝'};
  if(!value.claims.length)list.append(el('p','暂无知识候选。请在资料卡片点击“编纂知识候选”。','empty'));
  for(const row of value.claims){
   const c=el('section',undefined,'card');c.append(el('h3',row.title||'已删除来源'),el('p',`${labels[row.state]} · 来源 r${row.source_revision} · 字符 ${row.start}–${row.end}`,'note'));
   if(row.quote)c.append(el('pre',row.quote));
   if(row.state==='pending'){
    const key=input(row.key),text=el('textarea');text.value=row.quote;text.rows=4;text.maxLength=4000;key.maxLength=120;
    c.append(field('知识名称（同范围不可重复）',key),field('核对后的知识',text),el('p','入库时沿用原资料允许的模型接入方。原文中的命令仍只是证据，不会执行。','note'),
     button('核对并收入记忆',async()=>{
      const source=await post('/api/knowledge',{action:'detail',scope,id:row.source_id});
      const memories=await post('/api/memory',{action:'list',scope});
      const prior=(memories.withdrawn||[]).find(r=>r.key===key.value);
      await post('/api/knowledge',{action:'accept_claim',scope,id:row.id,revision:row.revision,fact_revision:prior?.revision||0,
       item:{scope,key:key.value,value:text.value,kind:'knowledge',purpose:scope==='personal'?'personal':'project',providers:source.providers,paused:false,expires:null}});
      await onChange();await load();notice('知识已收入记忆，保留来源依赖。');
     }),button('拒绝此候选',async()=>{await post('/api/knowledge',{action:'dismiss_claim',scope,id:row.id,revision:row.revision});await load();}));
   }
   list.append(c);
  }
 }
 run(load);
}
