// Geometry/event unit tests. Synthetic DOM, no browser or Windows input.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../apps/workbench/native-presence.js',import.meta.url),'utf8');
function setup(handler=()=>Promise.resolve(),robotSurface=false){
 const frames=[],calls=[],events={},observers=[];
 function node(classes=[],box=[400,700,74,74]){return {hidden:false,classes:new Set(classes),box,listeners:{},classList:{contains:c=>classes.includes(c)},getBoundingClientRect(){let [left,top,width,height]=this.box;return {left,top,width,height,right:left+width,bottom:top+height};},getClientRects(){return this.hidden?[]:[this.getBoundingClientRect()];},addEventListener(type,fn){this.listeners[type]=fn;}};}
 const robot=node(['robot'],[8,8,74,74]),full=node(),error=node(),dot={dataset:{}};error.hidden=true;
 const items=Array.from({length:3},(_,i)=>node([], [510,100+i*50,47,46]));
 const card=node([], [20,40,400,660]);card.hidden=true;items.push(card,error);
 const ids={robot,'open-full':full,error,'presence-dot':dot};
 const root={classList:{add(){}},dataset:{}};
 const document={documentElement:root,body:{},querySelectorAll:selector=>selector==='.robot'?[robot]:items,getElementById:id=>ids[id],addEventListener(type,fn){events[type]=fn;}};
 const win={__TAURI_INTERNALS__:{invoke(cmd,args){calls.push({cmd,args});return handler(cmd,args);}},addEventListener(type,fn){events[type]=fn;}};
 const context={document,window:win,location:{pathname:robotSurface?'/companion/native-robot':'/companion/native'},innerWidth:560,innerHeight:800,Promise,Math,JSON,String,getComputedStyle:n=>({visibility:n.invisible?'hidden':'visible',display:'block'}),
  requestAnimationFrame:fn=>frames.push(fn),ResizeObserver:class{observe(){}disconnect(){}},MutationObserver:class{constructor(fn){observers.push(fn);}observe(){}disconnect(){}}};
 vm.runInNewContext(source,context);
 async function frame(){assert.ok(frames.length);frames.splice(0).forEach(fn=>fn());await Promise.resolve();await Promise.resolve();}
 return {items,card,robot,full,error,dot,root,events,observers,calls,frame};
}
let tests=0;
async function test(name,body){await body();tests++;console.log('PASS '+name);}
await test('only visible control islands, never full viewport',async()=>{
 const x=setup();await x.frame();const rects=x.calls[0].args.rects;
 assert.equal(rects.length,3);assert.equal(rects[0].rounded,false);assert.ok(rects.every(r=>r.width<560&&r.height<800));
});
await test('opened and closed card update the same native mask',async()=>{
 const x=setup();await x.frame();x.card.hidden=false;x.observers[0]();await x.frame();assert.equal(x.calls.at(-1).args.rects.length,4);
 x.card.hidden=true;x.observers[0]();await x.frame();assert.equal(x.calls.at(-1).args.rects.length,3);
});
await test('task islands are clipped to viewport and scroll parent',async()=>{
 const x=setup();const task=x.items[1];task.classes.add('task-dock');task.classList.contains=c=>task.classes.has(c);task.box=[500,700,70,150];task.parentElement={getBoundingClientRect:()=>({top:730,bottom:780})};
 await x.frame();const r=x.calls[0].args.rects[1];assert.equal(r.x,500);assert.equal(r.y,730);assert.equal(r.width,60);assert.equal(r.height,50);
});
await test('single flight keeps only newest geometry while IPC pending',async()=>{
 const resolves=[];const x=setup(()=>new Promise(resolve=>resolves.push(resolve)));await x.frame();
 x.items[0].box[0]=390;x.events.resize();await x.frame();x.items[0].box[0]=380;x.events.resize();await x.frame();assert.equal(x.calls.length,1);
 resolves.shift()();await Promise.resolve();await Promise.resolve();assert.equal(x.calls.length,2);assert.equal(x.calls[1].args.rects[0].x,380);
 resolves.shift()();await Promise.resolve();
});
await test('synchronous bridge errors are bounded and redact long identifiers',async()=>{
 const secret='a'.repeat(43);const x=setup(()=>{throw Error('denied '+secret);});await x.frame();
 assert.equal(x.root.dataset.nativeError,'region');assert.equal(x.error.hidden,false);assert.ok(!x.error.textContent.includes(secret));
});
await test('animation completion resamples transformed card coordinates',async()=>{
 const x=setup();x.card.hidden=false;await x.frame();x.card.box[1]=35;x.events.animationend();await x.frame();assert.equal(x.calls.at(-1).args.rects[3].y,35);
});
await test('dragging uses only own-window command and suppresses release click',async()=>{
 const x=setup(undefined,true);await x.frame();x.robot.listeners.pointerdown({button:0,screenX:10,screenY:10});x.events.pointermove({screenX:22,screenY:10});
 assert.equal(x.calls.at(-1).cmd,'presence_drag');let stopped=false;x.robot.listeners.click({stopImmediatePropagation(){stopped=true;},preventDefault(){}});assert.ok(stopped);
});
await test('workbench continuation uses native command, no second business client',async()=>{
 const x=setup();await x.frame();let stopped=false;x.full.listeners.click({stopImmediatePropagation(){stopped=true;}});assert.ok(stopped);assert.equal(x.calls.at(-1).cmd,'presence_workbench');
});
await test('robot surface has one small hit island, independent from dock',async()=>{
 const x=setup(undefined,true);await x.frame();assert.equal(x.calls[0].args.rects.length,1);assert.equal(x.calls[0].args.rects[0].width,74);assert.equal(x.calls[0].args.rects[0].rounded,true);
 const dock=setup();await dock.frame();assert.equal(dock.robot.listeners.pointerdown,undefined);x.robot.onclick();assert.equal(x.calls.at(-1).cmd,'presence_toggle');
});
await test('only status values bridge to robot, no extra business client',async()=>{
 const x=setup();await x.frame();x.dot.dataset.state='running';x.observers[1]();assert.equal(x.calls.at(-1).cmd,'presence_status');assert.equal(x.calls.at(-1).args.status,'running');
});
await test('capabilities split dock and robot commands by window and exact page',()=>{
 const cfg=JSON.parse(readFileSync(new URL('../apps/desktop/tauri.conf.json',import.meta.url),'utf8'));
 const [dock,robot]=cfg.app.security.capabilities;assert.deepEqual(dock.windows,['presence']);assert.deepEqual(robot.windows,['robot']);
 assert.deepEqual(dock.remote.urls,['http://127.0.0.1:*/companion/native']);assert.deepEqual(robot.remote.urls,['http://127.0.0.1:*/companion/native-robot']);
 assert.ok(!dock.permissions.includes('allow-presence-drag'));assert.ok(!robot.permissions.includes('allow-presence-workbench'));assert.ok([...dock.permissions,...robot.permissions].every(p=>p.startsWith('allow-presence-')));
});
console.log(JSON.stringify({passed:true,tests,scope:'synthetic DOM unit tests; no real click acceptance'}));
