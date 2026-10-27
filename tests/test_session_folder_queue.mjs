import assert from 'node:assert/strict';
import {SessionFolders} from '../apps/workbench/session-folders.js';

// Exercise actual save queuing before archive/delete, with controlled HTTP completion.
const notices={};globalThis.document={getElementById:()=>notices};
let requests=[],releases=[],fail=false;
globalThis.fetch=async(url,options)=>{
 if(url==='/api/session')return {ok:true,json:async()=>({token:'fixture'})};
 const value=JSON.parse(options.body);requests.push(value);
 await new Promise(resolve=>releases.push(resolve));
 return {ok:!fail,status:fail?409:200,json:async()=>fail?{error:'conflict'}:{revision:value.revision+1}};
};
const next=()=>new Promise(resolve=>setImmediate(resolve));
function queue(){const q=new SessionFolders();q.adopt({id:'fixture',workspace:{status:'ready',revision:1,path:'fixture',config:{text:''}}});return q;}

const q=queue();q.remember('fixture',{text:'first draft'});const writing=q.flush('fixture');await next();
q.remember('fixture',{text:'latest draft'});let settled=false;const hiding=q.settle(['fixture']).then(()=>{settled=true;});
await next();assert.equal(settled,false);assert.equal(requests.length,1);
releases.shift()();await next();assert.equal(requests.length,2);assert.equal(requests[1].revision,2);assert.equal(requests[1].config.text,'latest draft');assert.equal(settled,false);
releases.shift()();await Promise.all([writing,hiding]);assert.equal(q.dirty('fixture'),false);assert.equal(settled,true);

const before=requests.length;q.remember('fixture',{text:'latest draft'});await q.settle(['fixture','unknown']);assert.equal(requests.length,before);

const failed=queue();failed.remember('fixture',{text:'must not be lost'});fail=true;const blocked=assert.rejects(failed.settle(['fixture']),/未执行/);await next();releases.shift()();await blocked;
assert.equal(failed.items.get('fixture').config.text,'must not be lost');assert.equal(failed.dirty('fixture'),true);
await assert.rejects(failed.settle(['fixture']),/未执行/);assert.ok(notices.textContent.includes('保存失败'));
console.log('PASS: in-flight wait, queued latest draft, revision ordering, unchanged no-op, failed save blocks hiding and retains draft.');
