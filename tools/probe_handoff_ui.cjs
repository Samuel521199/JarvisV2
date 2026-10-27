const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2),fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1100}}),report={checks:[],errors:[],requests:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/api/goals'))report.requests.push({url:new URL(r.url()).pathname,body:r.postDataJSON()});});
 async function mount(id){
  await page.goto(base+'/handoff-probe');
  await page.evaluate(async data=>{const {goalsView}=await import('/goals.js');goalsView(document.getElementById('test'),{settings:data.settings,initialId:data.id});},{id,settings:fixture.settings});
  await page.getByRole('button',{name:'确认此计划并执行',exact:true}).waitFor();
 }
 async function done(id){let d;for(let i=0;i<150;i++){d=await page.evaluate(async id=>{const session=await(await fetch('/api/session')).json();const r=await fetch('/api/goals',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':session.token},body:JSON.stringify({action:'detail',id})});return r.json();},id);if(d.task?.status==='SUCCEEDED')break;await new Promise(r=>setTimeout(r,100));}assert.equal(d.task?.status,'SUCCEEDED',JSON.stringify(d));}
 try{
  await page.route('**/handoff-probe',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><body><div id="error" hidden></div><main id="test" style="padding:24px;max-width:1100px;margin:auto"></main><dialog id="modal"><h2 id="modal-title"></h2><div id="modal-content"></div></dialog></body></html>'}));
  await mount(fixture.ids[0]);await page.getByRole('button',{name:'确认此计划并执行',exact:true}).click();await done(fixture.ids[0]);
  assert.equal(report.requests.filter(r=>r.body.action==='approve_and_run').length,1);
  assert.equal(report.requests.filter(r=>r.url==='/api/goals/run').length,0);
  report.checks.push('One approval HTTP request persists execution; no second start request is needed');
  await mount(fixture.ids[1]);await page.getByRole('button',{name:'约定验收条件并执行',exact:true}).click();
  await page.getByLabel('检查方式',{exact:true}).selectOption('text_contains');await page.getByLabel('预期文本',{exact:true}).fill('最低报价：B');
  await page.getByLabel('验收范围',{exact:true}).selectOption('complete');await page.getByLabel('必需要求',{exact:true}).fill('预算最多100\n交付不超过5天');
  await page.getByRole('button',{name:'保存条件并执行',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});await done(fixture.ids[1]);
  await page.getByRole('button',{name:'刷新详情',exact:true}).click();
  await page.getByText('目标覆盖尚未证实；检查通过或记录认可不等于全部业务要求正确。',{exact:true}).waitFor();
  assert.match(await page.locator('.completion-summary').innerText(),/待核对 · 交付不超过5天/);
  await page.locator('.completion-summary').getByText(/约定检查通过率：100%/).waitFor();
  assert.match(await page.locator('.completion-summary').innerText(),/约定检查通过率：100%/);
  assert.equal(report.requests.filter(r=>r.body.action==='approve_and_run').length,2);
  assert.equal(report.requests.filter(r=>r.url==='/api/goals/run').length,0);
  report.checks.push('Weak passing check remains separate from two unverified business requirements');
  for(const theme of ['dark','light']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.locator('.completion-summary').scrollIntoViewIfNeeded();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(out,'handoff-'+theme+'.png'),fullPage:true});}
  assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;report.body=await page.locator('body').innerText();await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2)+'\n');await browser.close();}
 console.log(JSON.stringify({passed:report.passed,checks:report.checks,errors:report.errors}));
})().catch(e=>{console.error(e);process.exitCode=1;});
