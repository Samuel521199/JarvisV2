const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const {chromium}=require(process.env.JARVIS_PLAYWRIGHT||'playwright');
(async()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'jarvis-preview-'));
 const folder=path.join(temp,'fixture');
 const server=spawn(process.env.JARVIS_PYTHON||'python',['-X','utf8','-B','tests/workspace_browser_fixture.py',folder,'--library-preview'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
 const exited=new Promise(resolve=>server.once('close',resolve));
 let logs='';server.stderr.on('data',s=>logs=(logs+s).slice(-2400));
 let browser;
 try{
  const fixtureFile=path.join(folder,'fixture.json');
  for(let n=0;!fs.existsSync(fixtureFile);n++){if(n>150||server.exitCode!==null)throw Error('Fixture failed '+logs);await new Promise(r=>setTimeout(r,100));}
  const fixture=JSON.parse(fs.readFileSync(fixtureFile)),origin='http://127.0.0.1:'+fixture.port;
  browser=await chromium.launch({channel:'msedge',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
  const context=await browser.newContext({viewport:{width:1100,height:820},reducedMotion:'reduce',permissions:['microphone']}),errors=[];
  assert.equal((await context.request.post(origin+'/api/local-access',{data:{key:fixture.key},headers:{Origin:origin}})).status(),200);
  const asset=await (await context.request.get(origin+'/api/model-library/assets/paper-boat')).json();
  const expectedSha=asset.variants.find(v=>v.id==='lod2').file.sha256;
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(14000);
  for(const route of ['/','/conversation']){
   if(route==='/conversation')await page.setViewportSize({width:450,height:800});
   await page.goto(origin+route);await page.waitForFunction(()=>typeof document.getElementById('message').oninput==='function');
   await page.keyboard.press('Escape');
   assert.equal(await page.locator('#session-tasks').isVisible(),false);
   await page.getByRole('button',{name:'项目与会话',exact:true}).click();await page.locator('#session-operations summary').first().click();
   assert.equal(await page.locator('#session-tasks').isVisible(),true);assert.equal(await page.locator('#model-button').isVisible(),true);
   await page.locator('#close-workspace').click();
   await page.locator('#message').fill('请打开纸船的 LOD2');await page.locator('#send').click();
   try{await page.waitForFunction(()=>document.querySelector('#panel-content iframe')?.contentWindow.studio3dViewerState?.ready===true,null,{timeout:20000});}catch(e){throw Error(e.message+' '+await page.locator('body').innerText()+' '+await page.locator('#panel-content iframe').count()+' '+errors+' '+logs);}
   const state=await page.evaluate(()=>{const w=document.querySelector('#panel-content iframe').contentWindow;return [w.location.pathname,w.studio3dViewerState.triangles,w.studio3dViewerState.sha256]});
   assert.equal(state[0],'/model-library/view/paper-boat/lod2');assert.equal(state[1],1);assert.equal(state[2],expectedSha);
   await page.locator('#close-panel').click();
   await page.reload();await page.waitForFunction(()=>typeof document.getElementById('message').oninput==='function');
   await page.keyboard.press('Escape');await page.getByRole('button',{name:'纸船 · LOD2',exact:true}).waitFor();
   assert.equal(await page.locator('#panel-content iframe:visible').count(),0);
   await page.locator('#message').fill('预览纸船的 LOD3');await page.locator('#message').press('Enter');
   await page.getByText('纸船 没有可预览的 LOD3。',{exact:false}).first().waitFor();assert.equal(await page.locator('#panel-content iframe:visible').count(),0);
  }
  await page.locator('#voice').click();
  await page.getByRole('button',{name:'开始录音',exact:true}).click();
  await page.getByText('正在录音，最多60秒；停止后可回听并确认转写。',{exact:true}).waitFor();
  await page.waitForTimeout(800);
  await page.getByRole('button',{name:'停止录音',exact:true}).click();
  const candidate=page.getByRole('button',{name:'纸船 · LOD2 · paper-boat',exact:true});
  try{await candidate.waitFor();}catch(error){
   throw Error(error.message+' '+await page.locator('#panel-content').innerText()+' '+errors+' '+logs);
  }
  const confirm=page.getByRole('button',{name:'确认并发送到当前会话',exact:true});
  const turnCount=async()=> (await (await context.request.get(origin+'/__fixture__/state')).json()).turns;
  const before=await turnCount();
  await confirm.click();
  await page.getByText('请选择本机候选，或手动校正模型名称和 LOD。',{exact:true}).waitFor();
  assert.equal(await turnCount(),before);
  await candidate.click();
  assert.equal(await page.getByLabel('语音识别草稿').inputValue(),'打开 paper-boat 的 LOD2');
  assert.equal(await turnCount(),before);
  await confirm.click();
  await page.waitForFunction(sha=>document.querySelector('#panel-content iframe')?.contentWindow.studio3dViewerState?.sha256===sha,expectedSha);
  assert.equal(await turnCount(),before+1);
  assert.deepEqual(errors,[]);
  console.log('PASS desktop and compact: local typed/confirmed speech preview, SHA-verified GLB, no turn before voice confirmation');
 }finally{
  if(browser)await browser.close();
  server.kill();
  await exited;
  if(path.dirname(path.resolve(temp))===path.resolve(os.tmpdir())&&path.basename(temp).startsWith('jarvis-preview-')){
   fs.rmSync(temp,{recursive:true,force:true,maxRetries:3});
  }
 }
})().catch(e=>{console.error(e.message);process.exitCode=1});
