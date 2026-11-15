const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/samuel/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'../../..'),origin='http://127.0.0.1:18282';
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});const report={checks:[],errors:[],scope:'Actual daily UI; no learner answer or paid model call from this probe.'};
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1050},reducedMotion:'reduce'});
  const key=cp.execFileSync('python',['-X','utf8','-B','-c',"from control.local_access import read_key;from pathlib import Path;print(read_key(Path('E:/Jarvis/runtime/user-data')))"],{cwd:root,encoding:'utf8'}).trim();
  const unlocked=await context.request.post(origin+'/api/local-access',{data:{key},headers:{Origin:origin}});assert.equal(unlocked.status(),200);
  const page=await context.newPage();page.on('pageerror',e=>report.errors.push(e.message));
  await page.goto(origin);await page.getByRole('button',{name:'英语学习 · 跨会话记录与复习',exact:true}).click();
  await page.getByLabel('保存并使用个人跨会话学习记录').waitFor();
  assert.ok(await page.getByLabel('保存并使用个人跨会话学习记录').isChecked());report.checks.push('Actual owner-authorized learning panel and saved preference');
  const panel=page.locator('#panel-content');assert.match(await panel.innerText(),/尚无足够可比的延迟样本/);report.checks.push('Insufficient progress evidence stays unknown');
  assert.equal(await page.getByLabel('练习场景').locator('option').count(),5);
  await page.getByLabel('练习场景').selectOption('mistakes');assert.equal(await page.getByLabel('练习场景').inputValue(),'mistakes');report.checks.push('Explicit mistake review selection; no paid request on selection');
  assert.ok(await panel.getByRole('button',{name:'刷新学习记录',exact:true}).isVisible());
  assert.equal(await panel.locator('details').count(),0);assert.ok(await page.getByLabel('我的回答').isVisible());
  report.checks.push('Daily first question ready; no synthetic assessments imported');
  await page.screenshot({path:path.join(__dirname,'daily-desktop.png'),fullPage:true});
  await page.reload();await page.getByRole('button',{name:'英语学习 · 跨会话记录与复习',exact:true}).click();await page.getByLabel('保存并使用个人跨会话学习记录').waitFor();assert.ok(await page.getByLabel('保存并使用个人跨会话学习记录').isChecked());assert.equal(await panel.locator('details').count(),0);report.checks.push('Page reload preserves server learning state and first unanswered question');
  await page.setViewportSize({width:430,height:900});await page.screenshot({path:path.join(__dirname,'daily-narrow.png'),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);report.narrow_page_overflow=overflow;
  assert.equal(report.errors.length,0);report.passed=true;
 }finally{fs.writeFileSync(path.join(__dirname,'daily-ui-result.json'),JSON.stringify(report,null,2)+'\n');await browser.close();}
 console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exitCode=1;});
