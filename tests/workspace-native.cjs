const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.env.JARVIS_PLAYWRIGHT||'playwright');
(async()=>{
 const [folder,cdp,probe]=process.argv.slice(2),f=JSON.parse(fs.readFileSync(folder+'/fixture.json')),report={passed:false,scope:'Actual compiled Tauri IPC and read-only Win32 visibility; synthetic data only',checks:[]};
 let browser;
 try{
  for(let i=0;i<80;i++){try{browser=await chromium.connectOverCDP('http://127.0.0.1:'+cdp);break;}catch{await new Promise(r=>setTimeout(r,250));}}
  assert.ok(browser,'Owned WebView2 debug endpoint was not ready');const context=browser.contexts()[0];context.setDefaultTimeout(15000);
  let dock;for(let i=0;i<60;i++){dock=context.pages().find(p=>p.url().includes('/companion/native')&&!p.url().includes('native-robot'));if(dock)break;await new Promise(r=>setTimeout(r,250));}assert.ok(dock);await dock.locator('#project-button').waitFor();
  await dock.evaluate(id=>window.__TAURI_INTERNALS__.invoke('presence_workbench',{action:'open',chatId:id}),f.ids[1]);
  let full;for(let i=0;i<60;i++){full=context.pages().find(p=>p.url().includes('/workbench/native'));if(full)break;await new Promise(r=>setTimeout(r,250));}assert.ok(full);
  await full.waitForFunction(()=>typeof document.getElementById('message')?.oninput==='function');await full.keyboard.press('Escape');await full.waitForFunction(()=>!document.documentElement.hasAttribute('data-brand-cinema'));
  assert.equal(await full.locator('#chat-title').innerText(),'草稿对话');assert.ok(!full.url().includes('access='));
  const states=[];const state=async()=>{const v=await(await fetch('http://127.0.0.1:'+probe+'/state')).json();states.push(v);return v;};
  let shown=await state();assert.equal(shown.workbench.length,1);assert.equal(shown.workbench[0].visible,true);const handle=shown.workbench[0].handle;
  await full.locator('#message').fill('原生工作台收回保留草稿');await full.getByRole('button',{name:'收回桌面精灵',exact:true}).click();let hidden;for(let i=0;i<40;i++){hidden=await state();if(hidden.workbench[0]?.visible===false)break;await new Promise(r=>setTimeout(r,100));}assert.equal(hidden.workbench[0].visible,false);assert.equal(context.pages().filter(p=>p.url().includes('/workbench/native')).length,1);
  await dock.evaluate(id=>window.__TAURI_INTERNALS__.invoke('presence_workbench',{action:'open',chatId:id}),f.ids[1]);await full.waitForFunction(()=>document.getElementById('message')?.value==='原生工作台收回保留草稿');shown=await state();assert.equal(shown.workbench[0].visible,true);assert.equal(shown.workbench[0].handle,handle);
  await assert.rejects(full.evaluate(()=>window.__TAURI_INTERNALS__.invoke('presence_workbench',{action:'hide'})));
  await assert.rejects(full.evaluate(()=>window.__TAURI_INTERNALS__.invoke('presence_regions',{rects:[]})));
  await dock.evaluate(id=>window.__TAURI_INTERNALS__.invoke('presence_workbench',{action:'open',chatId:id}),f.ids[0]);await full.waitForFunction(()=>document.getElementById('chat-title')?.textContent==='整理后的原对话');assert.equal((await state()).workbench.length,1);
  report.checks=['Native workbench uses selected existing conversation and removes access key from address','Fold hides actual HWND, retaining WebView and draft','Reopen reuses the same HWND and draft','Full workbench has no direct native IPC permissions; fold delegates to the original dock','Repeated open selects a different conversation without spawning another window'];
  const robotPage=context.pages().find(page=>page.url().includes('/companion/native-robot'));
  assert.ok(robotPage);
  const setMotion=motionOff=>full.evaluate(async motionOff=>{
   const {savePreferences}=await import('/ui.js');
   await savePreferences({motion_off:motionOff});
  },motionOff);
  await setMotion(false);
  await robotPage.waitForSelector('#robot[data-face-motion]');
  const robot=robotPage.locator('#robot');
  const initialBox=await robot.boundingBox();
  assert.equal(initialBox.width,74);
  for(const [status,expression] of [['running','focused'],['unread','attention'],['unknown','uncertain']]){
   await dock.evaluate(status=>{document.getElementById('presence-dot').dataset.state=status;},status);
   await robotPage.waitForSelector('#robot[data-expression="'+expression+'"]');
   assert.deepEqual(await robot.boundingBox(),initialBox);
  }
  await robotPage.reload();
  await robotPage.waitForSelector('#robot[data-face-motion]');
  // The timed dock refresh can supersede the last synthetic state before reload completes.
  const poses={running:'focused',unread:'attention',unknown:'uncertain',idle:'resting'};let converged=false;
  for(let i=0;i<70;i++){
   const current=await dock.locator('#presence-dot').getAttribute('data-state');
   if(await robot.getAttribute('data-expression')===poses[current]){converged=true;break;}
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert.ok(converged,'reloaded robot did not converge to the live dock status');
  assert.deepEqual(await robot.boundingBox(),initialBox);
  report.checks.push('Actual dock-to-robot IPC changes face poses and restores the current status after robot reload, with an invariant 74 px click region');
  await setMotion(true);
  await robotPage.waitForSelector('#robot:not([data-face-motion])[data-expression]');
  assert.deepEqual(await robot.evaluate(node=>node.getAnimations({subtree:true}).map(animation=>({type:animation.constructor.name, target:animation.effect.target.getAttribute('class'), property:animation.transitionProperty, state:animation.playState}))),[]);
  await setMotion(false);
  await robotPage.waitForSelector('#robot[data-face-motion]');
  report.checks.push('Existing Workbench motion preference is applied live to the separate native robot');
  report.visibility=states;report.passed=true;
 }finally{fs.writeFileSync(folder+'/native.json',JSON.stringify(report,null,2)+'\n');if(browser)await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
