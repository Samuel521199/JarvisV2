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
for(const [status,next,label] of [['PASSED','compare_real_tasks','合成输出检查通过'],['FAILED','resolve_validation_failure','未通过新输入检查'],['INTERRUPTED','review_validation_run','验证已中断'],[null,'independent_validation','尚无完成回执']]){
 const parent=new Element('main');
 completionView(parent,{state:'VERIFIED',checks:[],learning_candidate:{state:'CANDIDATE',next_step:next,
  history:{observations:1,distinct_inputs:1},validation:{policy:{enabled:true,max_trials_24h:4,revision:2},
  trials_in_24h:1,trial:{result:status?{status}:null}}}});
 assert.ok(text(parent).includes(label));assert.ok(text(parent).includes('不调用模型或写入业务文件'));
 assert.deepEqual(buttons(parent),['暂停本地自动验证','查看经验依据与待验证项']);
}
const broken=new Element('main');completionView(broken,{state:'VERIFIED',checks:[],learning_candidate:{state:'CANDIDATE',next_step:'independent_validation',history:{observations:1,distinct_inputs:1},validation:{policy:{enabled:false,max_trials_24h:4,revision:1},policy_error:'invalid_policy',trials_in_24h:0,trial:null}}});
assert.ok(text(broken).includes('自动验证已停止'));assert.deepEqual(buttons(broken),['查看经验依据与待验证项']);
for(const repair of [null,{id:'dev-fixture',status:'WAITING'}]){
 const parent=new Element('main');completionView(parent,{state:'VERIFIED',task_id:'task-fixture',checks:[],learning_candidate:{state:'CANDIDATE',next_step:'resolve_validation_failure',history:{observations:1,distinct_inputs:1},repair,validation:{policy:{enabled:true,max_trials_24h:4,revision:2},trials_in_24h:1,trial:{source_task:'task-fixture',result:{status:'FAILED'}}}}});
 assert.ok(buttons(parent).includes(repair?'查看修复研发':'根据失败用例准备修复'));
 assert.ok(!buttons(parent).some(s=>s.includes('发布')));
 if(repair)assert.ok(text(parent).includes('原工具尚未替换'));
}
for(const status of ['CLOSED','WAITING','REGRESSED','CANCELLED']){
 const parent=new Element('main');completionView(parent,{state:'NEEDS_CORRECTION',task_id:'original',checks:[],learning_candidate:{state:'COUNTEREVIDENCE',history:{observations:1,distinct_inputs:1},repair:{id:'repair',status:'SUCCEEDED',return:{status,child_task:'returned',before_score:0,actual:{condition_score:100}}}}});
 assert.ok(text(parent).includes('0 → 100（不代表综合智能评分）'));
 assert.ok(buttons(parent).includes('查看返工的实际验收'));
 assert.equal(buttons(parent).includes('撤销本次自动修复授权'),!['REGRESSED','CANCELLED'].includes(status));
}
console.log('16 completion candidate/validation/repair-return render checks passed');
