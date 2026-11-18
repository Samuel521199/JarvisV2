const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.JARVIS_PLAYWRIGHT||'playwright');

(async()=>{
 const [folder,cdp,probe]=process.argv.slice(2);
 const fixture=JSON.parse(fs.readFileSync(path.join(folder,'fixture.json')));
 const origin='http://127.0.0.1:'+fixture.port;
 const report={passed:false,checks:[],production_mutations:0,model_calls:0};
 let browser;
 const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 const stamp=(page,value)=>page.waitForFunction(build=>document.querySelector('meta[name="jarvis-application"]')?.content===build.repeat(64),value);
 try{
  for(let i=0;i<80;i++){
   try{browser=await chromium.connectOverCDP('http://127.0.0.1:'+cdp);break;}catch{await wait(250);}
  }
  assert.ok(browser);
  const context=browser.contexts()[0];context.setDefaultTimeout(35000);
  const pageFor=async route=>{
   for(let i=0;i<80;i++){
    const page=context.pages().find(page=>new URL(page.url()).pathname===route);
    if(page)return page;
    await wait(150);
   }
   throw Error('Missing WebView '+route);
  };
  const dock=await pageFor('/companion/native'),robot=await pageFor('/companion/native-robot');
  dock.on('pageerror', error=>console.error('Dock scripting:',error.message));
  await dock.waitForFunction(()=>document.documentElement.classList.contains('native-presence')&&typeof document.getElementById('robot')?.onclick==='function');
  const initialRobotBox=await robot.locator('#robot').boundingBox();
  await dock.evaluate(id=>localStorage.setItem('jarvis.companion.chat.v1',id),fixture.ids[0]);
  await dock.reload();await dock.waitForFunction(()=>document.documentElement.classList.contains('native-presence')&&typeof document.getElementById('robot')?.onclick==='function');
  await robot.evaluate(()=>window.__TAURI_INTERNALS__.invoke('presence_toggle'));
  await dock.locator('#card[data-mode=chat]').waitFor();
  const frame=dock.frameLocator('#conversation-host iframe');
  await frame.locator('html[data-presentation-ready]').waitFor();
  const compactDraft='精灵升级期间保留的未发送内容';
  await frame.locator('#message').fill(compactDraft);
  await dock.evaluate(id=>window.__TAURI_INTERNALS__.invoke('presence_workbench',{action:'open',chatId:id}),fixture.ids[1]);
  const full=await pageFor('/workbench/native');
  await full.locator('html[data-presentation-ready]').waitFor();
  await full.keyboard.press('Escape');
  const fullDraft='隐藏工作台中已经保存的草稿';
  await full.locator('#message').fill(fullDraft);
  await full.getByRole('button',{name:'收回桌面精灵',exact:true}).click();
  const windows=async()=> (await(await fetch('http://127.0.0.1:'+probe+'/state')).json()).workbench;
  let view=await windows();for(let i=0;i<40&&view[0]?.visible;i++){await wait(100);view=await windows();}assert.equal(view.length,1);assert.equal(view[0].visible,false);
  const originalHandle=view[0].handle;
  const auth=await (await context.request.get(origin+'/api/session')).json();
  const advance=async(build,epoch,phase)=>{
   const response=await context.request.post(origin+'/__fixture__/presentation',{
    headers:{Origin:origin,'X-Jarvis-Token':auth.token},data:{build,epoch,phase},
   });
   assert.equal(response.status(),200);
  };
  await advance('b',2,'observing');
  await wait(5500);
  await stamp(dock,'a');await stamp(robot,'a');await stamp(full,'a');
  await advance('a',3,'quarantined');
  await stamp(dock,'a');
  report.checks.push('A candidate under observation and a failed candidate rolled back do not reload any open view');

  const unsent='恢复连接后只保存、不发送的最新草稿';
  let rejected=0,failWrites=true;
  await dock.route('**/api/chat/workspace',async route=>{
   const req=route.request();
   if(failWrites&&req.method()==='POST'&&req.postDataJSON().action==='save'){
    rejected++;
    return route.fulfill({status:409,json:{error:'application_maintenance'}});
   }
   return route.continue();
  });
  await frame.locator('#message').fill(unsent);
  await advance('c',4,'complete');
  await dock.locator('#error').filter({hasText:'新版已就绪'}).waitFor();
  assert.ok(rejected>0);
  assert.equal(await frame.locator('#message').inputValue(),unsent);
  await stamp(dock,'a');
  failWrites=false;
  await stamp(dock,'c');await stamp(robot,'c');await stamp(full,'c');
  await frame.locator('html[data-presentation-ready]').waitFor();
  assert.equal(await frame.locator('#message').inputValue(),unsent);
  await full.waitForFunction(value=>document.getElementById('message')?.value===value,fullDraft);
  assert.deepEqual(await windows(),[{handle:originalHandle,visible:false}]);
  assert.deepEqual(await robot.locator('#robot').boundingBox(),initialRobotBox);
  assert.equal((await (await context.request.get(origin+'/__fixture__/state')).json()).turns,12);
  const persisted=await (await context.request.post(origin+'/api/chat/workspace',{
   headers:{Origin:origin,'X-Jarvis-Token':auth.token},data:{id:fixture.ids[0],action:'detail'},
  })).json();
  assert.equal(persisted.config.text,unsent);
  report.checks.push('Rejected saves keep the draft and old windows; confirmed retry reloads all three views, preserving the panel, draft, hidden HWND and position');

  await dock.getByRole('button',{name:'项目与会话',exact:true}).click();
  await dock.getByLabel('搜索项目或会话',{exact:true}).fill('草稿对话');
  await advance('d',5,'complete');
  await stamp(dock,'d');
  assert.equal(await dock.getByLabel('搜索项目或会话',{exact:true}).inputValue(),'草稿对话');
  report.checks.push('Project list and filter restore after a later automatic update without restarting the original shell');
  report.passed=true;
 }finally{
  fs.writeFileSync(path.join(folder,'native-upgrade.json'),JSON.stringify(report,null,2)+'\n');
  if(browser)await browser.close();
 }
 console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exitCode=1;});
