import {el,button,link,select,field,get,post,run,modal,card,details} from './ui.js';
const presets=[['robot','自定义关节机构'],['engine','四冲程发动机'],['jet','喷气引擎'],['electric-water','电机 → 水泵 → 水波'],['waves','水波干涉'],['hybrid','发动机驱动水泵']];
const finished=new Set(['DELIVERED','CANCELLED','UNKNOWN','FAILED','INVALID']);
export function anatomyStudio(settings){
 const body=modal('Anatomy · 机械与场实验台');body.append(el('p','从示例开始，或用自然语言组合已支持的组件。场景最多 8 个组件、8 条连接；组件与场效果统一归 Anatomy 管理。','note'));
 const examples=el('div',undefined,'row'),output=el('div',undefined,'stack');
 for(const [id,name] of presets)examples.append(button('制作'+name,async()=>{const r=await post('/api/anatomy/render',{mechanism:'studio',preset:id});output.prepend(resultCard(r,name));}));body.append(examples);
 const free=card('自由描述生成','用模型把需求转成声明式场景，校验后自动交付 HTML。支持基础零件关节树，以及发动机、喷气引擎、电机电路、齿轮、水泵和水波的组合；缺少的结构和求解能力会列明。');
 const prompt=el('textarea');prompt.rows=4;prompt.maxLength=2000;prompt.placeholder='例如：做一个四缸发动机，通过 20:40 的齿轮驱动水泵，再让水槽产生干涉波；显示进排气、火焰和电火花。';prompt.setAttribute('aria-label','自由机械需求');
 const connections=(settings.connections||[]).filter(c=>c.enabled&&c.models.some(m=>m.enabled));const preferred=connections.find(c=>c.adapter==='vertex'||c.id==='vertex')||connections[0];
 const provider=select(connections.map(c=>[c.id,c.label]),preferred?.id),model=select([]),fill=()=>{model.replaceChildren();const c=connections.find(x=>x.id===provider.value);for(const m of c?.models.filter(x=>x.enabled)||[])model.add(new Option(m.label,m.id));if(c)model.value=c.model;};fill();provider.onchange=fill;
 const status=el('p','示例和手工 JSON 不调用模型。自由描述使用所选线路，最多一次调用；费用与未知结果保留在调用明细。','note');status.role='status';const actions=el('div',undefined,'row');let active=null;
 async function follow(id){active=id;for(;;){if(!body.isConnected||!document.getElementById('modal').open)return;const s=await get('/api/anatomy/compositions/'+id);status.textContent='场景 '+id.slice(0,8)+' · '+s.status+(s.error?' · '+s.error:'');
   if(s.status==='CANDIDATE'){status.textContent='配置校验通过，正在制作交互产物…';const done=await post('/api/anatomy/finish',{id});output.prepend(resultCard(done.artifact,done.scene.title));status.textContent='已交付 · '+done.calls.length+' 次模型调用'+(done.scene.unfulfilled.length?' · 有未覆盖要求，请查看产物说明':'');active=null;await history();return;}
   if(s.status==='DELIVERED'){output.prepend(resultCard(s.artifact,'已保存场景'));active=null;return;}
   if(finished.has(s.status)){active=null;status.textContent+='；没有自动重试。';output.prepend(button('查看本次回执',()=>details('场景与调用回执',s)));return;}
   await new Promise(resolve=>setTimeout(resolve,1100));
  }}
 actions.append(button('生成并制作',async()=>{if(active)throw Error('当前场景仍在生成，请先等待或取消。');const id=crypto.randomUUID().replaceAll('-','');const started=await post('/api/anatomy/compose',{id,prompt:prompt.value,provider:provider.value,model:model.value});status.textContent='已接收，正在调用所选模型…';await follow(started.id);},'primary'),button('取消当前生成',async()=>{if(active){await post('/api/anatomy/cancel',{id:active});status.textContent='已请求取消；已发出的远端调用仍可能计费。';}}));
 free.append(field('描述机械、动力传递和想观察的效果',prompt),field('模型线路',provider),field('模型',model),actions,status);body.append(free,output);
 const manual=el('details'),editor=el('textarea');editor.rows=9;editor.spellcheck=false;editor.setAttribute('aria-label','手工场景 JSON');manual.append(el('summary','手工场景 JSON · 不调用模型'),el('p','可从示例 HTML 保存场景 JSON，在这里编辑后重新制作。宿主和浏览器会分别校验配置。','note'),editor,button('校验并制作 JSON 场景',async()=>{let scene;try{scene=JSON.parse(editor.value);}catch{throw Error('JSON 语法无效。');}const r=await post('/api/anatomy/render',{mechanism:'studio',scene});output.prepend(resultCard(r,scene.title));}));body.append(manual);
 const records=card('最近自由生成','重开本窗口后可查看或继续取回结果；不会自动重新调用模型。');body.append(records);
 async function history(){const rows=await get('/api/anatomy/compositions');records.replaceChildren(el('h3','最近自由生成'));for(const r of rows.slice(0,10)){const line=el('div',undefined,'row');line.append(el('span',new Date(r.created*1000).toLocaleString()+' · '+(r.delivered?'已交付':r.cancel?'已取消':r.error||'查看状态'),'note'),button('取回 '+r.id.slice(0,8),()=>follow(r.id)),link('查看模型会话','/#chat='+r.chat_id));records.append(line);}if(!rows.length)records.append(el('p','暂无自由生成记录。','note'));}
 run(history);
}
function resultCard(r,name){const c=card(name||'机械场景','已保存 · Anatomy '+r.adapter_version+' · '+r.bytes+' bytes');if(r.normalizations?.length)c.append(el('p','标识符格式已规范化 '+r.normalizations.length+' 项，详情见回执。','note'));c.append(link('打开交互实验台 ↗',r.url),button('配置与来源回执',()=>details('Anatomy 回执',r)));return c;}
