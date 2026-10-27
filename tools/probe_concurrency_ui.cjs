// Real browser against the disposable offline fixture; never a paid model.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/samuel/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=process.argv[2]||'http://127.0.0.1:18379',out=path.resolve('docs/evidence/concurrency-1.0.0');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'}),report={checks:[],errors:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 try{
  await page.goto(base);await page.getByRole('button',{name:'工作状态与资源',exact:true}).waitFor();
  const tool=page.getByRole('button',{name:'工作状态与资源',exact:true});
  assert.equal(await tool.getAttribute('title'),'工作状态与资源');await tool.click();
  await page.locator('.work-count').first().waitFor();assert.equal(await page.locator('.work-count').count(),3);
  assert.match(await page.locator('.work-status-list').innerText(),/尚未启动/);
  report.checks.push('Workbench boots; icon, accessible name, three truthful summary groups and unstarted records');
  await page.getByRole('button',{name:'调整优先级',exact:true}).first().click();
  await page.getByLabel('执行优先级',{exact:true}).selectOption('3');await page.getByLabel('重要性',{exact:true}).selectOption('2');
  await page.getByRole('button',{name:'保存优先级',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.work-status-list')?.textContent.includes('紧急'));
  report.checks.push('Priority editor persists revisioned priority and updates the projection');
  await page.screenshot({path:path.join(out,'work-status.png')});
  await page.goto(base+'/settings#tasks');await page.getByLabel('通用任务并发上限',{exact:true}).waitFor();
  await page.getByLabel('通用任务并发上限',{exact:true}).selectOption('1');
  await page.getByRole('button',{name:'保存资源预算',exact:true}).click();
  await page.waitForFunction(async()=>{const r=await fetch('/api/work-status');return (await r.json()).policy.max_workers===1;});
  report.checks.push('Settings save updates actual scheduler policy');
  for(const theme of ['dark','light']){
   await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await page.screenshot({path:path.join(out,'settings-'+theme+'.png')});
  }
  report.checks.push('Dark/light theme variables render without page overflow');
  await page.goto(base);await page.locator('details').filter({has:page.locator('#message-mode')}).locator('summary').first().click();await page.locator('#message-mode').selectOption('chat');
  await page.locator('#message').fill('UI slow first reply');await page.locator('#send').click();
  await page.locator('#cancel-response').waitFor({state:'visible'});
  await page.waitForFunction(()=>!document.getElementById('send').disabled);assert.equal(await page.locator('#send').isEnabled(),true);
  await page.locator('#message').fill('followup remains usable');await page.locator('#send').click();
  await page.waitForFunction(()=>document.querySelector('#messages')?.textContent.includes('followup remains usable'));
  const chat=new URL(page.url()).hash.slice(6);
  const before=await (await page.request.get(base+'/api/chats/'+chat)).json();
  assert.equal(before.turns.length,2);assert.ok(before.turns.some(t=>t.status==='READY'));
  await page.locator('#cancel-response').click();
  await page.waitForFunction(async id=>{const r=await fetch('/api/chats/'+id);const t=(await r.json()).turns;return t.length===2&&t[0].status==='CANCELLED'&&t[1].status==='SUCCEEDED';},chat);
  report.checks.push('Running reply keeps input/send usable; followup persists; stopping first reply lets followup finish');
  assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;throw e;}
 finally{fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2)+'\n');await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
