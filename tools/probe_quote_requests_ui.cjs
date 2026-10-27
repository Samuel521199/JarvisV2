const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2),fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
const mode=fixture.changeReview?'quote_changes':fixture.sourceReview?'quote_sources':'quote_request',reviewAction='review_'+mode;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),report={checks:[],errors:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 async function command(value){return page.evaluate(async value=>{const s=await(await fetch('/api/session')).json();const r=await fetch('/api/goals',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':s.token},body:JSON.stringify(value)});return {status:r.status,body:await r.json()};},value);}
 async function detail(id){const r=await command({action:'detail',id});assert.equal(r.status,200);return r.body;}
 let delayOnce=true;
 try{
  await page.route('**/api/goals',async route=>{if(route.request().method()==='POST'&&route.request().postDataJSON().action===reviewAction&&delayOnce){delayOnce=false;const response=await route.fetch();await new Promise(r=>setTimeout(r,350));await route.fulfill({response});}else await route.continue();});
  await page.route('**/quote-request-probe',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><body><div id="error" hidden></div><main id="test" style="padding:24px;max-width:1100px;margin:auto"></main><dialog id="modal"><h2 id="modal-title"></h2><div id="modal-content"></div></dialog></body></html>'}));
  for(const item of fixture.cases){
   await page.goto(base+'/quote-request-probe');await page.evaluate(async f=>{const {goalsView}=await import('/goals.js');goalsView(document.getElementById('test'),{settings:f.settings,initialId:f.id});},{settings:fixture.settings,id:item.id});
   await page.getByRole('button',{name:'约定验收条件并执行',exact:true}).click();
   if(item.name==='correct'){
    const sent=page.waitForRequest(r=>r.url().endsWith('/api/goals')&&r.method()==='POST'&&r.postDataJSON().action===reviewAction);
    await page.getByLabel('检查方式',{exact:true}).selectOption(mode);await sent;
    await page.getByLabel('检查方式',{exact:true}).selectOption('text_equals');await new Promise(r=>setTimeout(r,500));
    assert.equal(await page.getByLabel('预期文本',{exact:true}).isVisible(),true);
    assert.equal(await page.getByText('逐项对照原文。这里只识别明确的报价表达，未覆盖片段不会自动忽略。',{exact:true}).count(),0);
    report.checks.push('Late review response cannot overwrite a newer selected acceptance mode');
   }
   await page.getByLabel('检查方式',{exact:true}).selectOption(mode);
   await page.getByText('逐项对照原文。这里只识别明确的报价表达，未覆盖片段不会自动忽略。',{exact:true}).waitFor();
   assert.equal((await detail(item.id)).task,null);
   if(item.name==='conflict'){
    await page.getByText(fixture.changeReview?'当前目标与逐条变更后仍有效的要求不一致':'原请求预算与输入预算不一致：请求 9000 / 输入 10000',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'保存条件并执行',exact:true}).isDisabled(),true);
    const d=await detail(item.id),review=await command({action:reviewAction,id:item.id,revision:d.plan.revision});
    const refused=await command({action:'approve',id:item.id,revision:d.plan.revision,acceptance:{...review.body.acceptance,coverage:'complete'}});
    assert.notEqual(refused.status,200);assert.equal((await detail(item.id)).task,null);
    await page.screenshot({path:path.join(out,'conflict.png'),fullPage:true});report.checks.push('Conflict blocks both UI and direct HTTP admission; no task created');continue;
   }
   if(item.name==='correct'){
    if(fixture.changeReview){await page.getByText('要求变更记录 · 当前有效 5 项',{exact:true}).click();await page.getByText('已替换：预算不超过100元',{exact:true}).waitFor();await page.getByText('已撤销：必须保修三年',{exact:true}).waitFor();await page.getByText('有效：预算不超过90元',{exact:true}).waitFor();}
    if(fixture.sourceReview){await page.getByText('合成报价.json · 与本次输入逐字一致',{exact:true}).waitFor();await page.getByText('用户原话 · 已逐句对照',{exact:true}).click();}
    await page.getByLabel('验收范围',{exact:true}).selectOption('complete');
    await page.screenshot({path:path.join(out,'review-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'review-mobile.png'),fullPage:true});
    assert.equal(await page.locator('#modal').evaluate(e=>e.scrollWidth<=e.clientWidth+1),true);await page.setViewportSize({width:1440,height:1000});
   }else{
    await page.getByText(fixture.sourceReview?'原话中的要求没有完整写入当前目标':'未覆盖：必须保修三年',{exact:true}).waitFor();
    if(fixture.sourceReview){await page.getByText('用户原话 · 已逐句对照',{exact:true}).click();assert.match(await page.locator('#modal details').first().innerText(),/必须保修三年/);}
    assert.equal(await page.getByLabel('验收范围',{exact:true}).isDisabled(),true);
    assert.equal(await page.getByLabel('验收范围',{exact:true}).inputValue(),'recipe');await page.screenshot({path:path.join(out,'uncovered-review.png'),fullPage:true});
   }
   await page.getByRole('button',{name:'保存条件并执行',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
   let d;for(let i=0;i<160;i++){d=await detail(item.id);if(d.task?.status==='SUCCEEDED'&&d.completion?.checks?.length)break;await new Promise(r=>setTimeout(r,100));}
   assert.equal(d.task?.status,'SUCCEEDED');assert.equal(d.completion.state,item.name==='correct'?'VERIFIED':'WAITING_EVIDENCE');
   assert.equal(d.work_closure.state==='COMPLETE',item.name==='correct');assert.equal(d.completion.requirement_coverage.semantic_goal_verified,false);
   const refreshed=page.waitForResponse(r=>r.url().endsWith('/api/goals')&&r.request().method()==='POST'&&r.request().postDataJSON().action==='detail'&&r.request().postDataJSON().id===item.id);
   await page.getByRole('button',{name:'刷新详情',exact:true}).click();const response=await refreshed;assert.equal(response.status(),200);
   await page.waitForFunction(sig=>document.querySelector('.goal-detail')?.dataset.signature===sig,JSON.stringify(await response.json()));
   await page.locator('.completion-summary').getByText(item.name==='correct'?'已核对明确列出的受支持要求':'等待验收证据',{exact:true}).waitFor();
   await page.locator('.completion-summary').scrollIntoViewIfNeeded();
   if(item.name==='uncovered')await page.getByText(fixture.changeReview?'变更后仍有未核验要求，不能自动结案':fixture.sourceReview?'来源中仍有未核对内容，不能自动结案':'原始请求仍有未覆盖要求，不能自动结案',{exact:true}).waitFor();
   await page.screenshot({path:path.join(out,item.name+'-result.png'),fullPage:true});report.checks.push(item.name+': original clauses reviewed; independent execution/closure matches declared scope');
  }
  report.passed=report.errors.length===0;
 }catch(e){report.errors.push(e.stack);report.passed=false;await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});process.exitCode=1;}
 finally{fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
