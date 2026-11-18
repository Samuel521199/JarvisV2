const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/samuel/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const folder=path.resolve(process.argv[2]),fixture=JSON.parse(fs.readFileSync(path.join(folder,'fixture.json'))),origin='http://127.0.0.1:'+fixture.port;
 const browser=await chromium.launch({channel:'msedge',headless:true});const report={scope:'Synthetic owner data, actual HTTP receipts and real browser render; native IPC is a geometry stub, not an OS hit-test proof',checks:[],errors:[],passed:false};
 try{
  const context=await browser.newContext({viewport:{width:560,height:800},deviceScaleFactor:1});
  await context.addInitScript(()=>{window.nativeRects=[];window.__TAURI_INTERNALS__={invoke:(cmd,args)=>{if(cmd==='presence_regions')window.nativeRects=args.rects;return Promise.resolve();}};});
  assert.equal((await context.request.post(origin+'/api/local-access',{data:{key:fixture.key},headers:{Origin:origin}})).status(),200);
  const page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  await page.goto(origin+'/companion/native');await page.getByRole('button',{name:'所有工作与未读结果',exact:true}).click();await page.locator('.work-card').first().waitFor();
  assert.equal(await page.getByRole('tab',{name:/待你处理/}).getAttribute('aria-selected'),'true');
  assert.equal(await page.locator('.work-metric[data-state=running] strong').innerText(),'1');
  assert.equal(await page.locator('.work-metric[data-state=queued] strong').innerText(),'1');
  report.checks.push('Attention first; running and queued remain independently visible');
  await page.screenshot({path:path.join(folder,'native-attention.png')});
  await page.getByRole('tab',{name:/未读成果/}).click();await page.getByRole('heading',{name:'PaK38 · 游戏资产',exact:true}).waitFor();
  const before=Number(await page.locator('#unread-total').innerText());
  assert.equal(await page.locator('.work-project').count(),3);assert.equal(await page.locator('#task-docks .task-dock').count(),3);
  assert.equal(await page.locator('.work-card').count(),3);assert.equal(await page.getByText('含 2 项进度与反馈',{exact:true}).count(),1);
  const overflow=await page.evaluate(()=>[...document.querySelectorAll('.work-board,.work-card,.work-tabs')].filter(n=>n.scrollWidth>n.clientWidth+2).map(n=>n.className));assert.deepEqual(overflow,[]);
  const box=await page.locator('#card').boundingBox();assert.ok(box.height<=610&&box.width<=470&&box.y>=0);
  await page.screenshot({path:path.join(folder,'native-unread.png')});
  report.checks.push('Project/task grouping, three dock groups, bounded 470x610 card and no horizontal overflow');
  const model=page.locator('.work-project').filter({has:page.getByRole('heading',{name:'PaK38 · 游戏资产',exact:true})});
  await page.route('**/api/work-status',async route=>{if(route.request().method()==='POST')return route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'attention_stale'})});return route.continue();});
  const failedRead=page.waitForResponse(r=>r.url().endsWith('/api/work-status')&&r.request().method()==='POST'&&r.status()===400);
  await model.getByRole('button',{name:/将.*标记已读/}).click();
  await failedRead;
  assert.equal(Number(await page.locator('#unread-total').innerText()),before);
  await page.unroute('**/api/work-status');report.checks.push('Rejected/stale read never clears a badge optimistically');
  await model.getByRole('button',{name:/将.*标记已读/}).click();
  await page.waitForFunction(n=>Number(document.getElementById('unread-total').textContent)===n-1,before);
  await page.getByRole('heading',{name:'PaK38 · 游戏资产',exact:true}).waitFor({state:'detached'});
  await page.locator('#task-docks .task-dock').filter({hasText:'PaK38 · 游戏资产'}).waitFor({state:'detached'});
  assert.equal(await page.locator('.work-metric[data-state=running] strong').innerText(),'1');
  await page.getByRole('tab',{name:/已读历史/}).click();await page.getByRole('heading',{name:'PaK38 · 游戏资产',exact:true}).waitFor();
  report.checks.push('The last confirmed read removes the project dock while keeping history and running work');

  const englishDock=page.locator('#task-docks .task-dock').filter({hasText:'英语学习 · 日常交流'});
  const nextBefore=Number(await page.locator('#unread-total').innerText());
  await englishDock.getByRole('button').click();
  await page.getByRole('heading',{name:'英语学习 · 日常交流',exact:true}).waitFor();
  assert.equal(await page.getByRole('tab',{name:/未读成果/}).getAttribute('aria-selected'),'true');
  assert.equal(Number(await page.locator('#unread-total').innerText()),nextBefore);
  await page.getByRole('button',{name:'查看成果',exact:true}).click();
  await page.locator('#modal[open] .answer').waitFor();
  await englishDock.waitFor({state:'detached'});
  await page.waitForFunction(n=>Number(document.getElementById('unread-total').textContent)===n-1,nextBefore);
  await page.screenshot({path:path.join(folder,'native-result.png')});
  await page.getByRole('button',{name:'关闭对话框',exact:true}).click();
  await page.getByRole('button',{name:'收起卡片',exact:true}).click();
  report.checks.push('Desktop shortcut opens unread results and disappears when the actual reply is visible');

  const last=page.locator('#task-docks .task-dock button');
  assert.equal(await last.count(),1);
  const lastBox=await last.boundingBox();
  const sample=await (await context.request.get(origin+'/api/work-status')).json();
  const unread=sample.items.filter(item=>item.attention?.unread);
  assert.equal(unread.length,1);
  await last.focus();
  let releaseSnapshot,captureSnapshot;
  const release=new Promise(resolve=>{releaseSnapshot=resolve;});
  const captured=new Promise(resolve=>{captureSnapshot=resolve;});
  await page.route('**/api/work-status',async route=>{
    const response=await route.fetch();
    captureSnapshot();
    await release;
    await route.fulfill({response});
  },{times:1});
  await page.evaluate(()=>window.dispatchEvent(new Event('jarvis:work-viewed')));
  try {
    await captured;
    const source=await context.newPage();
    // A second client reads through the original versioned API and broadcast.
    await source.goto(origin+'/companion');
    await source.evaluate(async item=>{
      const {workApi}=await import('/work-client.js');
      await workApi.viewed(item);
    },unread[0]);
    await source.close();
  } finally {
    releaseSnapshot();
  }
  await last.waitFor({state:'detached'});
  assert.equal(await page.locator('#work-button').evaluate(node=>document.activeElement===node),true);
  await page.waitForFunction(box=>window.nativeRects.every(rect=>rect.y+rect.height<=box.y),lastBox);
  assert.equal(await page.locator('#unread-total').isHidden(),true);
  await page.reload();
  await page.waitForFunction(()=>document.getElementById('work-summary').textContent.includes('0 项工作有未读'));
  assert.equal(await last.count(),0);
  report.checks.push('Cross-window receipt removes even a focused last dock and its hit region, with no reappearance after reload');

  await page.getByRole('button',{name:'所有工作与未读结果',exact:true}).click();
  await page.getByRole('tab',{name:/进行中/}).click();
  assert.equal(await page.locator('.work-card').count(),1);
  await page.getByRole('tab',{name:/待你处理/}).click();
  assert.equal(await page.locator('.work-card').count(),1);
  report.checks.push('Read receipts neither cancel work nor answer an outstanding question');
  await page.setViewportSize({width:390,height:720});await page.getByRole('tab',{name:/未读成果/}).click();await page.screenshot({path:path.join(folder,'compact.png')});
  assert.equal(await page.evaluate(()=>document.querySelector('.work-board').scrollWidth>document.querySelector('.work-board').clientWidth+2),false);
  await page.getByRole('tab',{name:/未读成果/}).focus();await page.keyboard.press('ArrowRight');assert.equal(await page.getByRole('tab',{name:/已读历史/}).getAttribute('aria-selected'),'true');
  await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('.work-board').evaluate(n=>getComputedStyle(n).animationName),'none');
  report.checks.push('Compact layout, keyboard tabs and reduced-motion preference');
  await page.setViewportSize({width:1100,height:820});await page.goto(origin+'/settings#work');
  // The exact same component can also be mounted in a workbench-sized surface.
  await page.evaluate(async()=>{const {workStatusView}=await import('/work-status.js');const host=document.createElement('div');host.id='fixture-board';host.style.cssText='position:fixed;inset:20px 180px;z-index:100;background:var(--bg);padding:24px;overflow:auto';document.body.append(host);workStatusView(host);});
  await page.locator('#fixture-board .work-card').first().waitFor();await page.screenshot({path:path.join(folder,'workbench.png')});
  report.checks.push('Workbench and companion mount the same work component');
  assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.error=e.stack;}
 finally{await browser.close();fs.writeFileSync(path.join(folder,'browser-result.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));process.exitCode=report.passed?0:1;}
})();
