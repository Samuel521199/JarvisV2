// Shared workbench controls, synthetic DOM; not a Windows visual acceptance.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../apps/workbench/delivery-review.js',import.meta.url),'utf8').replace(/^import .*;$/gm,'').replaceAll('export ','');
function setup(){
 class Node{
  constructor(tag,text='',cls=''){this.tag=tag;this.textContent=text??'';this.className=cls;this.children=[];this.value='';this.checked=false;this.dataset={};this.events={};}
  append(...nodes){this.children.push(...nodes);}
  before(node){root.append(node);}
  setAttribute(key,value){this[key]=value;}
  addEventListener(key,fn){this.events[key]=fn;}
 }
 const root=new Node('root'),downloads=[],changes=[];
 const el=(...args)=>new Node(...args),button=(text,fn)=>{const node=el('button',text);node.onclick=fn;return node;};
 const context={el,button,download:(...args)=>downloads.push(args),document:{createElement:tag=>el(tag),createTextNode:text=>el('text',text)},JSON,Error};
 vm.createContext(context);vm.runInContext(source+'\nglobalThis.api={basisEditor,deliveryReviewView};',context);
 const editor=context.api.basisEditor(el('textarea'),()=>changes.push(true));
 const nodes=()=>{const result=[];function visit(node){result.push(node);for(const child of node.children??[])visit(child);}visit(root);return result;};
 const get=id=>nodes().find(node=>node.id===id);
 return {root,downloads,changes,editor,nodes,get,api:context.api};
}
{
 const t=setup(),request={text:'整理记录',assistant_mode:true};
 assert.equal(t.editor.apply(request),request);
 t.get('delivery-document-render').checked=true;
 assert.throws(()=>t.editor.apply(request),/事实或已确认计划/);
 const facts=t.get('delivery-basis-facts');facts.value='尚未迁移Codex。';facts.events.input();
 const applied=t.editor.apply(request);
 assert.equal(applied.delivery_format,'source_excerpt_markdown_v1');assert.equal(applied.delivery_basis.facts[0],facts.value);
 assert.equal(request.text,'整理记录');assert.equal(request.delivery_format,undefined);
 t.editor.commit();assert.equal(t.get('delivery-document-render').checked,false);
 t.get('delivery-document-render').checked=true;t.editor.restore({},null);assert.equal(t.get('delivery-document-render').checked,false);
 t.editor.update({archived:true});assert.equal(t.get('delivery-document-render').disabled,true);
}
{
 const t=setup(),basis={revision:1,entries:[{kind:'facts',quote:'原文。'}]};
 const turn={delivery_basis:basis,reply:JSON.stringify({document:'## 事实\n- [F1] 原文。'}),delivery_review:{state:'EXCERPT_MATCH',rendering:{state:'RENDERED'}}};
 t.api.deliveryReviewView(t.root,turn);
 const exportButton=t.nodes().find(node=>node.tag==='button'&&node.textContent==='导出摘录文档');assert.ok(exportButton);exportButton.onclick();
 assert.deepEqual(t.downloads,[['jarvis-source-document.md','## 事实\n- [F1] 原文。']]);
 for(const review of [{state:'REVIEW',rendering:{state:'DECLINED'}},{state:'EXCERPT_MATCH',stale:true,rendering:{state:'RENDERED'}}]){
  const other=setup();other.api.deliveryReviewView(other.root,{...turn,delivery_review:review});
  assert.equal(other.nodes().some(node=>node.tag==='button'&&node.textContent==='导出摘录文档'),false);
 }
}
console.log('PASS explicit document selection, empty-basis guard, reset, original request preservation, export and stale/declined restrictions');
