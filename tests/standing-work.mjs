// Actual shared component event handlers, synthetic DOM/API. No Windows clicks.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const source=readFileSync(new URL('../apps/workbench/standing-work.js',import.meta.url),'utf8').replace(/^import .*;$/gm,'').replaceAll('export ','');
function setup(){
 class Node{
  constructor(tag,text='',cls=''){this.tag=tag;this.textContent=text??'';this.className=cls;this.children=[];this.value='';this.parent=null;}
  append(...nodes){for(const node of nodes){node.parent=this;this.children.push(node);}}
  replaceChildren(...nodes){for(const c of this.children)c.parent=null;this.children=[];this.append(...nodes);}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);this.parent=null;}
  get isConnected(){return this===root||!!this.parent?.isConnected;}
 }
 const root=new Node('root'),calls=[],rows=[],goal={id:'goal-'+'a'.repeat(32),request:{goal:'每天整理这段文字',input_text:'hello'},proposal:{steps:[{title:'大写',capability:'plugin.upper.v1'}],questions:[],input_text:'hello'}},notices=[];
 const el=(...x)=>new Node(...x),button=(text,fn,cls)=>{const n=el('button',text,cls);n.onclick=fn;return n;},field=(text,node)=>{const n=el('label');n.append(el('span',text),node);return n;},input=(value='')=>{const n=el('input');n.value=value;return n;},select=(options,value)=>{const n=el('select');n.value=value??options[0]?.[0];return n;};
 const get=async path=>path==='/api/goals'?[{id:goal.id,goal:goal.request.goal,status:'REVIEW'}]:{items:structuredClone(rows)};
 let failAfterCreate=false;
 const post=async(path,value)=>{
  calls.push({path,value:structuredClone(value)});
  if(path==='/api/goals')return {plan:structuredClone(goal)};
  assert.equal(path,'/api/standing-work');
  if(value.action==='create'){
   if(!rows.length)rows.push({...structuredClone(value),id:'standing-'+'b'.repeat(32),revision:1,status:'DRAFT',granted:false,runs_started:0,reserved_units:0,next_at:Date.now()/1000,notice_pending:false,runs:[],plans:[{...goal,acceptance:value.plans[0].acceptance}]});
   if(failAfterCreate){failAfterCreate=false;throw Error('response lost after durable commit');}
  }else{
   const r=rows[0];assert.equal(value.id,r.id);assert.equal(value.revision,r.revision);
   if(value.action==='approve'){r.status='ACTIVE';r.granted=true;}
   if(value.action==='pause')r.status='PAUSED';
   if(value.action==='feedback')r.status=value.kind==='accept'?'DONE':'PAUSED';
   r.revision++;
  }
  return {id:rows[0].id,revision:rows[0].revision,status:rows[0].status};
 };
 const modal=title=>{root.replaceChildren(el('h2',title));const body=el('main');root.append(body);return body;};
 const context={el,button,field,input,select,get,post,modal,notice:x=>notices.push(x),details:()=>{},closeModal:()=>root.replaceChildren(),crypto:webcrypto,Date,JSON,Number,String,Error,console};
 vm.runInNewContext(source+'\nglobalThis.api={standingForm,openStanding,scheduleHint};',context);
 const walk=(n=root)=>[n,...n.children.flatMap(walk)],find=text=>walk().find(n=>n.tag==='button'&&n.textContent===text),control=label=>walk().find(n=>n.tag==='label'&&n.children[0].textContent===label)?.children[1];
 return {api:context.api,root,rows,calls,goal,walk,find,control,failNextCreate:()=>failAfterCreate=true};
}
let tests=0;
async function test(name,fn){await fn();tests++;console.log('PASS '+name);}
await test('natural schedule suggestions stay inert and bounded',()=>{
 const x=setup();for(const [q,n] of [['每天帮我整理',86400],['每隔 15 分钟处理',900],['每周做一次',604800],['取消每天整理',null],['每0分钟执行',null],['解释每天整理是什么意思',null]])assert.equal(x.api.scheduleHint(q),n);
 assert.equal(x.calls.length,0);
});
await test('plan -> draft -> exact review -> approved shared view remains open',async()=>{
 const x=setup();await x.api.standingForm({goalId:x.goal.id});assert.equal(x.control('重复周期').value,'86400');
 x.control('最后一个工具的精确预期输出（作为本次声明的验收要求）').value='HELLO';
 const form=x.walk().find(n=>n.tag==='form');await form.onsubmit({preventDefault(){}});
 assert.equal(x.rows[0].status,'DRAFT');assert.equal(x.calls.filter(c=>c.value.action==='approve').length,0);
 await x.find('核对计划并启用').onclick();assert.ok(x.find('确认授权并启用'));assert.ok(x.walk().some(n=>n.tag==='pre'&&n.textContent.includes('HELLO')));
 await x.find('确认授权并启用').onclick();assert.equal(x.rows[0].status,'ACTIVE');assert.ok(x.find('暂停后续动作'));assert.equal(x.rows[0].policy.cloud_model_budget_usd,0);
 await x.find('暂停后续动作').onclick();assert.equal(x.rows[0].status,'PAUSED');
});
await test('lost create response reuses the same request identity',async()=>{
 const x=setup();await x.api.standingForm({goalId:x.goal.id});x.control('最后一个工具的精确预期输出（作为本次声明的验收要求）').value='HELLO';const form=x.walk().find(n=>n.tag==='form');
 x.failNextCreate();await form.onsubmit({preventDefault(){}});await form.onsubmit({preventDefault(){}});
 const sent=x.calls.filter(c=>c.value.action==='create');assert.equal(sent.length,2);assert.equal(sent[0].value.request_id,sent[1].value.request_id);assert.equal(x.rows.length,1);
});
await test('shared feedback returns to current view, no detached-panel update',async()=>{
 const x=setup();await x.api.standingForm({goalId:x.goal.id});x.control('最后一个工具的精确预期输出（作为本次声明的验收要求）').value='HELLO';await x.walk().find(n=>n.tag==='form').onsubmit({preventDefault(){}});
 Object.assign(x.rows[0],{status:'DONE',granted:true,runs:[{id:'run-1',ordinal:1,status:'VERIFIED',goals:[]}]});await x.api.openStanding();await x.find('反馈 / 纠正 / 撤回经验').onclick();x.control('反馈').value='withdraw';x.control('说明').value='撤回不适用的经验';await x.find('保存反馈').onclick();assert.equal(x.rows[0].status,'PAUSED');assert.ok(x.find('修改安排'));
});
console.log(JSON.stringify({passed:true,tests,scope:'shared component event handlers with synthetic DOM/API; not real desktop clicks'}));
