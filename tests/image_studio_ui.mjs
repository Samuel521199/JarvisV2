// DOM-contract smoke test, not a browser rendering or accessibility audit.
import assert from 'node:assert/strict';
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.dataset={};this.style={};this.files=[];this._value=undefined;this.textContent='';this.classList={add:()=>{}};this.isConnected=true;}
 append(...nodes){for(const n of nodes){if(n&&typeof n==='object')n.parent=this;this.children.push(n);}}
 prepend(...nodes){this.children.unshift(...nodes);for(const n of nodes)n.parent=this;}
 replaceChildren(...nodes){this.children=[];this._value=undefined;this.append(...nodes);}
 add(n){this.append(n);}
 get options(){return this.children;}
 get value(){return this._value??(this.tag==='select'?this.children[0]?.value||'':'');}
 set value(v){this._value=String(v);}
 setAttribute(k,v){this.attrs[k]=v;}
 removeAttribute(k){delete this.attrs[k];}
 addEventListener(k,f){this['on'+k]=f;}
 closest(tag){return this.tag===tag?this:this.parent?.closest(tag);}
 querySelectorAll(selector){const tags=selector.split(',');return this.children.flatMap(n=>typeof n==='object'?[...(tags.includes(n.tag)?[n]:[]),...n.querySelectorAll(selector)]:[]);}
 showModal(){this.open=true;}
 focus(){}
}
const dialog=new Element('dialog'),body=new Element('div'),title=new Element('h2'),error=new Element('p');dialog.append(body);
const ids={'modal':dialog,'modal-content':body,'modal-title':title,error};
globalThis.document={createElement:t=>new Element(t),createTextNode:t=>t,getElementById:id=>ids[id],querySelector:()=>null,head:new Element('head')};
globalThis.Option=class extends Element{constructor(label,value){super('option');this.textContent=label;this.value=value;}};
globalThis.BroadcastChannel=class{postMessage(){}close(){}};
const dims={'1:1':[1024,1024],'16:9':[1376,768]};
const models=[['gemini-nano-banana-2.1',['1K','2K','4K']],['gemini-3.1-flash-lite-image',['1K']]].map(([id,sizes])=>({id,name:id,enabled:true,sizes,dimensions:Object.fromEntries(sizes.map(s=>[s,dims])),rates:{vertex:{input:1,text_output:2,image_output:30,source:'https://cloud.google.com'},gemini:{source:'https://ai.google.dev'}}}));
let config={revision:0,provider:'vertex',model:models[0].id,size:'2K',aspect_ratio:'16:9',preset:'product',enabled_models:models.map(m=>m.id),max_estimate_usd:1},requests=[];
globalThis.fetch=async(path,options={})=>{
 const v=options.body?JSON.parse(options.body):null;if(v)requests.push({path,value:v});let result;
 if(path==='/api/session')result={token:'fixture'};
 else if(path==='/api/image-studio')result={settings:config,models,recipes:[{id:'product',name:'产品',icon:'🔩'}],routes:[{id:'vertex',label:'Google',adapter:'vertex',credential_available:true}],ratios:Object.keys(dims),version:'test'};
 else if(path==='/api/image-studio/jobs')result=[];
 else if(path==='/api/image-studio/billing')result={groups:[]};
 else if(path==='/api/image-studio/preview')result={allowed:true,quote:{image_output_estimate:.05,planning_allowance:.1}};
 else if(path==='/api/image-studio/settings')result=config={...v,revision:v.revision+1};
 else throw Error('Unexpected route '+path);
 return {ok:true,status:200,json:async()=>result};
};
const {imageStudio}=await import('../apps/workbench/settings-images.js');await imageStudio({});
const all=tag=>body.querySelectorAll(tag),label=name=>all('label').find(n=>n.children[0].textContent===name)?.children[1];
assert.equal(label('分辨率档位').value,'2K');assert.equal(label('画幅').value,'16:9');
const model=label('图片模型');model.value=models[1].id;model.onchange();assert.deepEqual(label('分辨率档位').options.map(n=>n.value),['1K']);
model.value=models[0].id;model.onchange();assert.ok(label('分辨率档位').options.some(n=>n.value==='4K'));
label('主体与设计要求').value='blue pump';label('主体与设计要求').oninput();await new Promise(r=>setTimeout(r,350));assert.ok(requests.some(r=>r.path.endsWith('/preview')));assert.ok(!requests.some(r=>r.path.endsWith('/jobs')));
await all('button').find(n=>n.textContent==='保存当前选择与模型政策').onclick();assert.equal(config.revision,1);assert.equal(config.model,models[0].id);assert.equal(error.textContent,'');
console.log('PASS: mounted three panels, restored defaults, constrained model sizes, preview makes no generation call, saved backend defaults. DOM contract only.');
