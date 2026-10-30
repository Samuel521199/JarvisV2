import {el,card,button,field,select,link,input,get} from './ui.js';

export function workflowDetails(body, workflow){
 if(!workflow)return;
 body.append(el('h3','完整流程 · 一个组合技能'));
 for(const stage of workflow.stages){const row=el('p');row.append(el('strong',stage.name+' · '+(stage.status==='ready'?'已接入':'外部套件，尚未接入')),el('span',' — '+stage.detail));body.append(row);}
 body.append(el('p',workflow.edit_scope,'note'),el('p',workflow.runtime,'note'),el('h3','出处与适配'));
 for(const source of workflow.sources)body.append(link(source.name+' · '+source.license,source.url),el('br'));
}

export function workflowCard(){
 const pane=card('从参考到可编辑模型','Blender 负责制作与渲染；Jarvis 负责选取方法、模型规划、执行与结果记录。');
 const details=el('details');details.append(el('summary','查看每一步做什么、实际可用范围和出处'));pane.append(details);
 get('/api/studio3d').then(r=>{if(r.blender_workflow)workflowDetails(details,r.blender_workflow);else details.append(el('p','当前服务尚未加载分阶段工作流；已有工作室功能仍可使用。','note'));}).catch(()=>details.append(el('p','工作流状态暂时无法读取。','note')));
 return pane;
}

export function editPanel(receipt,submit){
 const pane=el('details');pane.append(el('summary','按部件修改 · 本机 Blender · 零模型调用'));
 const scene=receipt.configuration,objects=scene.objects,target=select(objects.map(o=>[o.id,o.id+' · '+o.kind]));
 const position=input(),rotation=input(),scale=input(),geometry=el('textarea'),modifiers=el('textarea'),color=el('input'),roughness=el('input'),affected=el('p',undefined,'note'),status=el('p',undefined,'note');
 color.type='color';color.style.height='44px';color.style.padding='6px';roughness.type='number';roughness.min='0.03';roughness.max='1';roughness.step='0.01';geometry.rows=3;modifiers.rows=2;status.role='status';
 let object,material;
 function fill(){object=objects.find(o=>o.id===target.value);material=scene.materials.find(m=>m.id===object.material);position.value=object.position.join(', ');rotation.value=object.rotation.join(', ');scale.value=object.scale.join(', ');geometry.value=JSON.stringify(object.params,null,2);modifiers.value=JSON.stringify(object.modifiers,null,2);color.value=material.color;roughness.value=material.roughness;affected.textContent='共享材质 '+material.id+'；改材质会影响：'+objects.filter(o=>o.material===material.id||o.cap_material===material.id).map(o=>o.id).join('、');}
 target.onchange=fill;fill();
 const fields=el('div',undefined,'grid');fields.append(field('目标部件',target),field('位置 X,Y,Z（米）',position),field('旋转 X,Y,Z（度）',rotation),field('比例 X,Y,Z',scale),field('材质颜色',color),field('粗糙度',roughness));
 const advanced=el('details');advanced.append(el('summary','几何参数与修改器'),field('当前部件几何参数 JSON',geometry),field('当前部件修改器 JSON',modifiers));
 const go=button('生成修改版并渲染',async()=>{status.textContent='';const set={},mat={};
  for(const [key,control] of [['position',position],['rotation',rotation],['scale',scale]]){const values=control.value.split(/[,，\s]+/).filter(Boolean).map(Number);if(values.length!==3||values.some(v=>!Number.isFinite(v)))throw Error('变换需要三个有效数字');if(JSON.stringify(values)!==JSON.stringify(object[key]))set[key]=values;}
  for(const [key,control] of [['params',geometry],['modifiers',modifiers]]){const value=JSON.parse(control.value);if(JSON.stringify(value)!==JSON.stringify(object[key]))set[key]=value;}
  if(color.value.toLowerCase()!==material.color.toLowerCase())mat.color=color.value;
  if(roughness.value.trim()===''||!Number.isFinite(Number(roughness.value)))throw Error('粗糙度需要有效数字');
  if(Number(roughness.value)!==material.roughness)mat.roughness=Number(roughness.value);
  const changes={};if(Object.keys(set).length)changes.objects=[{id:object.id,set}];if(Object.keys(mat).length)changes.materials=[{id:material.id,set:mat}];if(!Object.keys(changes).length)throw Error('请先修改至少一个参数');
  go.disabled=true;try{status.textContent='正在制作新版本，原模型保留。';await submit({edit:receipt.id,source_sha256:receipt.files['scene.json'].sha256,changes});status.textContent='任务已结束，请查看新版本的实际结果与渲染。';}finally{go.disabled=false;}
 },'primary');
 pane.append(el('p','适用于本工作室生成的未烘焙数据模型。保留原版，按源文件摘要检查输入；这不是任意 BLEND/FBX 雕刻编辑器。','note'),fields,affected,advanced,go,status);
 return pane;
}
