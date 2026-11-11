// Actual shared event handlers; synthetic DOM/API, no desktop clicks.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const source=readFileSync(new URL('../apps/workbench/mail-standing.js',import.meta.url),'utf8').replace(/^import .*;$/gm,'').replaceAll('export ','');
function setup(){
 class Node{constructor(tag,text=''){this.tag=tag;this.textContent=text;this.children=[];this.parent=null;this.value='';}append(...ns){for(const n of ns){n.parent=this;this.children.push(n);}}replaceChildren(...ns){this.children=[];this.append(...ns);}get isConnected(){return this===root||!!this.parent?.isConnected;}}
 const root=new Node('root'),rows=[],calls=[];let fail=false;
 const el=(...x)=>new Node(...x),button=(name,fn)=>{const n=el('button',name);n.onclick=fn;return n;},input=(v='')=>{const n=el('input');n.value=v;return n;},field=(name,n)=>{const p=el('label',name);p.append(n);return p;};
 const context=vm.createContext({console,Date,crypto:webcrypto,el,button,input,field,select:()=>{},notice:()=>{},closeModal:()=>root.replaceChildren(),modal:title=>{const n=el('dialog',title);root.replaceChildren(n);return n;},get:async()=>({items:structuredClone(rows)}),post:async(path,value)=>{
  calls.push({path,value:structuredClone(value)});assert.equal(path,'/api/mail-standing');
  if(value.action==='create'){if(!rows.length)rows.push({id:'mail-watch-'+'a'.repeat(32),title:value.title,policy:value.policy,config_revision:1,status:'DRAFT',entries:{},checks_started:0,new_items:0,phase:'REVIEW'});if(fail){fail=false;throw Error('Lost response');}}
  else{assert.equal(value.revision,rows[0].config_revision);rows[0].status=value.action==='approve'?'ACTIVE':'PAUSED';rows[0].config_revision++;}
  return {id:rows[0].id};
 },mailApi:{state:async()=>({capabilities:{modify:true}}),command:async v=>{calls.push({path:'/api/mail',value:v});}},openMailTask:async(id)=>calls.push({path:'/api/mail-work',id})});
 vm.runInContext(source+'\nglobalThis.subject={mailStandingForm,openMailStanding,reconnectMail};',context);
 function nodes(n=root){return [n,...n.children.flatMap(nodes)];}function find(name){const n=nodes().find(n=>n.tag==='button'&&n.textContent===name);assert(n,'Missing '+name);return n;}
 return {root,rows,calls,api:context.subject,nodes,find,lose:()=>fail=true};
}
let x=setup();await x.api.mailStandingForm();assert.equal(x.calls.length,0);let f=x.nodes().find(n=>n.tag==='form');await f.onsubmit({preventDefault(){}});assert.equal(x.calls[0].value.action,'create');assert.equal(x.rows[0].status,'DRAFT');console.log('PASS editable default scope stays inert until explicit review');
await x.find('核对并启用').onclick();assert.equal(x.calls.length,1);await x.find('确认范围并启用').onclick();assert.equal(x.rows[0].status,'ACTIVE');assert(x.find('暂停'));console.log('PASS one shared policy review and approval, no detached panel update');
x=setup();await x.api.mailStandingForm();f=x.nodes().find(n=>n.tag==='form');x.lose();await f.onsubmit({preventDefault(){}});await f.onsubmit({preventDefault(){}});assert.equal(x.calls[0].value.request_id,x.calls[1].value.request_id);assert.equal(x.rows.length,1);console.log('PASS lost create response preserves one request identity');
await x.api.reconnectMail();assert.equal(x.calls.at(-1).value.level,'manage');console.log('PASS reconnect reuses existing authority level');
x.rows[0].entries={fixture:{todo_id:'task1',state:'DUE',followups:1}};await x.api.openMailStanding();await x.find('邮件待办 1 · DUE · 已跟进 1 次').onclick();assert.deepEqual(x.calls.at(-1),{path:'/api/mail-work',id:'task1'});console.log('PASS follow-up opens original shared mail task handler');
console.log(JSON.stringify({passed:true,tests:5,scope:'synthetic DOM/API, not actual native clicks'}));
