/* Uses an owned fixture shell and samples its real HWND; never moves the user's pointer. */
const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.env.JARVIS_PLAYWRIGHT||'playwright');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
(async()=>{
 const [folder,cdp,port,mode]=process.argv.slice(2);
 const report={passed:false,mode,scope:'Owned Windows WebView2 shell; live window coordinates, synthetic data',checks:[]};
 let browser;
 const read=async()=>await(await fetch(`http://127.0.0.1:${port}/state`)).json();
 try{
  for(let i=0;i<80;i++){try{browser=await chromium.connectOverCDP(`http://127.0.0.1:${cdp}`);break;}catch{await wait(200);}}
  assert.ok(browser,'WebView2 endpoint did not start');const context=browser.contexts()[0];
  let dock,robot;
  for(let i=0;i<80;i++){
   dock=context.pages().find(p=>p.url().includes('/companion/native')&&!p.url().includes('native-robot'));
   robot=context.pages().find(p=>p.url().includes('/companion/native-robot'));
   if(dock&&robot)break;await wait(200);
  }
  assert.ok(dock&&robot,'Both native windows must be present');
  await robot.locator('#robot[data-face-motion]').waitFor({timeout:15000});
  const size=()=>robot.locator('#robot').evaluate(e=>e.getBoundingClientRect().width);
  let initial,first;
  for(let i=0;i<60;i++){initial=await read();first=initial.robot.find(v=>v.visible);if(first)break;await wait(100);}
  assert.ok(first,`Robot native window did not become visible: ${JSON.stringify(initial)}`);assert.equal(await size(),74);
  async function sample(ms){
   const rows=[];const begin=Date.now();
   do {
    const state=await read();const bot=state.robot.find(v=>v.handle===first.handle);
    assert.ok(bot?.visible,'same robot window stays visible');
    rows.push({at:Date.now()-begin,rect:bot.rect,work:bot.work,dock:state.dock[0]?.rect,focus:state.foreground});
    await wait(55);
   }while(Date.now()-begin<ms);
   return rows;
  }
  if(mode==='still'){
   const points=await sample(2200);
   assert.ok(points.every(p=>equal(p.rect,first.rect)));
   await dock.evaluate(()=>window.__TAURI_INTERNALS__.invoke('presence_status',{status:'running'}));
   await robot.locator('#robot[data-expression=focused]').waitFor();
   report.checks.push('Default mode keeps the native window stationary and retains the face renderer');
  }else{
   const phases=robot.evaluate(()=>new Promise(resolve=>{
    const root=document.documentElement,poses={};
    const observer=new MutationObserver(()=>{
     const pose=root.dataset.hopPose;if(pose)poses[pose]=getComputedStyle(document.querySelector('.robot svg')).animationName;
     if(poses.launch&&poses.land){observer.disconnect();resolve(poses);}
    });observer.observe(root,{attributes:true,attributeFilter:['data-hop-pose']});
    setTimeout(()=>{observer.disconnect();resolve(poses);},15000);
   }));
   const trail=await sample(10000);
   assert.ok(new Set(trail.map(p=>p.rect[0])).size>8,'actual native horizontal movement was not seen');
   assert.ok(new Set(trail.map(p=>p.rect[1])).size>5,'actual vertical jump was not seen');
   assert.ok(trail.every(({rect:r,work:w})=>r[0]>=w[0]&&r[1]>=w[1]&&r[2]<=w[2]&&r[3]<=w[3]),'robot must stay in the monitor work area');
   assert.ok(trail.every(p=>equal(p.dock,trail[0].dock)),'dock must not move with the robot');
   assert.ok(trail.every((p,i)=>!i||p.focus!==first.handle||trail[i-1].focus===first.handle),
    'the robot must not take focus from another window during motion');
   assert.equal(await size(),74);assert.deepEqual(await phases,{launch:'jarvis-hop-launch',land:'jarvis-hop-land'});
   report.path={samples:trail.length,otherForegroundSamples:trail.filter(p=>p.focus&&p.focus!==first.handle).length,xTravel:Math.max(...trail.map(p=>p.rect[0]))-Math.min(...trail.map(p=>p.rect[0])),
    yTravel:Math.max(...trail.map(p=>p.rect[1]))-Math.min(...trail.map(p=>p.rect[1]))};
   report.checks.push('Actual two-dimensional jumps inside the Windows work area; dock remains stationary and no focus steal',
    'Takeoff and landing animate the inner artwork while keeping its 74px click target');
   await robot.evaluate(()=>document.querySelector('#robot').click());
   await dock.locator('#card').waitFor({timeout:12000});await wait(250);
   const panel=await sample(1700);assert.ok(panel.every(p=>equal(p.rect,panel[0].rect)));
   await dock.locator('#close-card').click();await dock.locator('#card').waitFor({state:'hidden'});
   const resumed=await sample(4500);assert.ok(resumed.some(p=>!equal(p.rect,panel[0].rect)),'jump did not resume after closing conversation');
   report.checks.push('Actual robot-to-dock chat pauses movement and closing chat resumes it');
   await robot.emulateMedia({reducedMotion:'reduce'});
   await robot.locator('#robot[data-face-motion]').waitFor({state:'hidden'});await wait(250);
   const reduced=await sample(1800);assert.ok(reduced.every(p=>equal(p.rect,reduced[0].rect)));
   assert.equal(await robot.locator('.robot svg').evaluate(e=>getComputedStyle(e).animationName),'none');
   report.checks.push('System reduced-motion policy stops both native travel and hop artwork');
   await robot.emulateMedia({reducedMotion:'no-preference'});
   await robot.locator('#robot[data-face-motion]').waitFor();
   await dock.evaluate(async()=>{const {savePreferences}=await import('/ui.js');await savePreferences({motion_off:true});});
   await robot.locator('#robot[data-face-motion]').waitFor({state:'hidden'});await wait(250);
   const preference=await sample(1600);assert.ok(preference.every(p=>equal(p.rect,preference[0].rect)));
   await dock.evaluate(async()=>{const {savePreferences}=await import('/ui.js');await savePreferences({motion_off:false});});
   await robot.locator('#robot[data-face-motion]').waitFor();
   report.checks.push('Existing live Jarvis appearance preference also turns off native jumps');
  }
  report.passed=true;
 }catch(error){report.error=error.stack;process.exitCode=1;}
 finally{
  fs.writeFileSync(`${folder}/motion-${mode}.json`,JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));await browser?.close().catch(()=>{});
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
