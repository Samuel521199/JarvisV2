import assert from 'node:assert/strict';
globalThis.BroadcastChannel=class {postMessage(){} close(){}};
globalThis.fetch=async()=>({json:async()=>({environment:'test'})});
const {completionView}=await import('../apps/workbench/ui.js');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.textContent='';}
 append(...nodes){this.children.push(...nodes);}
 setAttribute(){}
}
globalThis.document={createElement:tag=>new Element(tag)};
const text=node=>[node.textContent,...node.children.map(text)].join('\n');
const buttons=node=>[...(node.tag==='button'?[node.textContent]:[]),...node.children.flatMap(buttons)];
for(const [state,label,next] of [
 ['CANDIDATE','已整理为待验证经验','independent_validation'],
 ['COUNTEREVIDENCE','已记录需要纠正的反证','resolve_counterevidence'],
 ['WITHDRAWN','经验来源已失效','restore_current_sources'],
 ['INCOMPLETE','经验仍缺少完整验收依据','complete_acceptance']]){
 const parent=new Element('main');
 completionView(parent,{state:'VERIFIED',checks:[],learning_candidate:{state,next_step:next,history:{observations:3,distinct_inputs:2,window_truncated:true}}});
 assert.ok(text(parent).includes(label));assert.ok(text(parent).includes('不会自动成为事实或执行许可'));
 assert.ok(text(parent).includes('计数并不完整'));
 assert.deepEqual(buttons(parent),['查看经验依据与待验证项']);
}
const legacy=new Element('main');completionView(legacy,{state:'SATISFIED',checks:[]});
assert.ok(!text(legacy).includes('经验'));assert.equal(buttons(legacy).length,0);
console.log('5 completion candidate render checks passed; no promote/execute action added');
