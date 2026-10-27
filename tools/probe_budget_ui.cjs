const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2),fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1100}}),report={checks:[],errors:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 async function command(value){return page.evaluate(async value=>{const s=await(await fetch('/api/session')).json();const r=await fetch('/api/goals',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':s.token},body:JSON.stringify(value)});return {status:r.status,body:await r.json()};},value);}
 async function detail(id){return(await command({action:'detail',id})).body;}
 async function done(id){let d;for(let i=0;i<150;i++){d=await detail(id);if(d.task?.status==='SUCCEEDED')break;await new Promise(r=>setTimeout(r,100));}assert.equal(d.task?.status,'SUCCEEDED');await page.getByRole('button',{name:'刷新详情',exact:true}).click();return d;}
 async function adjust(limit,note){await page.getByRole('button',{name:'调整整件工作执行额度',exact:true}).click();await page.getByLabel('执行总额',{exact:true}).fill(String(limit));await page.getByLabel('调整原因',{exact:true}).fill(note);await page.getByRole('button',{name:'保存执行额度',exact:true}).click();}
 try{
  await page.route('**/budget-probe',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><body><div id="error" hidden></div><main id="test" style="padding:24px;max-width:1100px;margin:auto"></main><dialog id="modal"><h2 id="modal-title"></h2><div id="modal-content"></div></dialog></body></html>'}));
  await page.goto(base+'/budget-probe');await page.evaluate(async f=>{const {goalsView}=await import('/goals.js');goalsView(document.getElementById('test'),{settings:f.settings,initialId:f.id});},fixture);
  await page.getByLabel('整件工作执行总额',{exact:true}).fill('4');await page.getByRole('button',{name:'确认此计划并执行',exact:true}).click();const original=await done(fixture.id);
  assert.equal(original.work.budget.limit_units,4);assert.equal(original.work.budget.spent_units,3);
  await page.getByRole('button',{name:'关联返工 / 追加要求',exact:true}).click();await page.getByLabel('完整的新要求',{exact:true}).fill('保留第一步，重新处理最后一步');await page.getByLabel('变更原因',{exact:true}).fill('第二步追加要求，前段仍适用');await page.getByLabel('最早需要重做的步骤',{exact:true}).selectOption('2');await page.getByRole('button',{name:'生成关联计划',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
  const child=(await detail(fixture.id)).work.current_goal;
  await page.getByRole('button',{name:'确认此计划并执行',exact:true}).click();await page.locator('#error').filter({hasText:'整件工作可用额度不足，未受理新执行。请调整计划或明确调整总额。'}).waitFor();
  assert.equal((await detail(child)).task,null);report.checks.push('Insufficient shared budget blocks admission without a new task');
  await adjust(5,'明确增加 1 个执行单位以完成本次返工');await page.locator('#modal').waitFor({state:'hidden'});
  assert.equal((await detail(child)).task,null);assert.equal((await detail(child)).work.budget.limit_units,5);report.checks.push('Explicit budget update alone does not execute or admit the draft');
  const approved=await command({action:'approve',id:child,revision:1});assert.equal(approved.status,200);
  await page.getByRole('button',{name:'刷新详情',exact:true}).click();await page.getByText('整件工作执行额度：3 已用 + 2 预留 / 5 总额 · 可用 0',{exact:true}).waitFor();
  await page.screenshot({path:path.join(out,'budget-reserved.png'),fullPage:true});report.checks.push('Existing approve-only path visibly holds two units until execution');
  await page.getByRole('button',{name:'开始 / 接续执行',exact:true}).click();const completed=await done(child);
  assert.deepEqual((await detail(fixture.id)).actions,original.actions);assert.equal(completed.work.budget.spent_units,5);assert.equal(completed.work.budget.reserved_units,0);assert.equal(completed.work.budget.available_units,0);
  await page.getByText('整件工作执行额度：5 已用 + 0 预留 / 5 总额 · 可用 0',{exact:true}).waitFor();
  await page.getByRole('button',{name:'刷新计划',exact:true}).click();await page.getByText('执行中',{exact:true}).waitFor({state:'hidden'});
  for(const theme of ['dark','light']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(out,'budget-'+theme+'.png'),fullPage:true});}
  await adjust(4,'试图低于已经使用的额度，应被拒绝');await page.getByText('总额不能低于已用和预留之和；需要减少时先停止尚未执行的任务。',{exact:true}).waitFor();
  assert.equal((await detail(child)).work.budget.limit_units,5);await page.keyboard.press('Escape');
  report.checks.push('Completed spend remains counted; lowering below it is rejected and original receipts are unchanged');
  report.snapshot=await detail(child);assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;report.body=await page.locator('body').innerText();await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2)+'\n');await browser.close();}
 console.log(JSON.stringify({passed:report.passed,checks:report.checks,errors:report.errors}));
})().catch(e=>{console.error(e);process.exitCode=1;});
