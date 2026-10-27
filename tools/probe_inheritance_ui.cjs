const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2),fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),report={checks:[],errors:[]},children={};
 page.on('pageerror',e=>report.errors.push(e.message));
 async function command(value){return page.evaluate(async value=>{const s=await(await fetch('/api/session')).json();const r=await fetch('/api/goals',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':s.token},body:JSON.stringify(value)});return {status:r.status,body:await r.json()};},value);}
 async function detail(id){const r=await command({action:'detail',id});assert.equal(r.status,200);return r.body;}
 try{
  await page.route('**/inheritance-probe',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><body><div id="error" hidden></div><main id="test" style="padding:24px;max-width:1100px;margin:auto"></main><dialog id="modal"><h2 id="modal-title"></h2><div id="modal-content"></div></dialog></body></html>'}));
  for(const item of fixture.cases){
   await page.goto(base+'/inheritance-probe');await page.evaluate(async f=>{const {goalsView}=await import('/goals.js');goalsView(document.getElementById('test'),{settings:f.settings,initialId:f.id});},{settings:fixture.settings,id:item.id});
   const old=await detail(item.id),goal=old.plan.request.goal;
   await page.getByRole('button',{name:'关联返工 / 追加要求',exact:true}).click();
   await page.getByLabel('完整的新要求',{exact:true}).fill(item.name==='uncovered'?goal:item.name==='conflict'?goal.replace('，保留来源引用','').replace('100元','90元'):goal.replace('100元','90元'));
   await page.getByLabel('变更原因',{exact:true}).fill(item.name==='uncovered'?'保持全部要求':'将要求「预算不超过100元」替换为「预算不超过90元」');
   await page.getByLabel('变更类型',{exact:true}).selectOption(item.name==='uncovered'?'correction':'new_requirement');
   const created=page.waitForResponse(r=>r.url().endsWith('/api/goals')&&r.request().method()==='POST'&&r.request().postDataJSON().action==='rework');
   await page.getByRole('button',{name:'生成关联计划',exact:true}).click();const creation=await created;assert.equal(creation.status(),200);const id=(await creation.json()).id;children[item.name]=id;
   await page.locator('#modal').waitFor({state:'hidden'});await page.getByRole('button',{name:'调整计划',exact:true}).click();
   if(item.name!=='uncovered'){
    const input=JSON.parse(old.plan.proposal.input_text);input.max_price_minor=9000;
    await page.getByLabel('实际输入（请核对模型提取是否准确）',{exact:true}).fill(JSON.stringify(input));
   }
   await page.getByRole('button',{name:'保存修改后的计划',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
   await page.getByRole('button',{name:'约定验收条件并执行',exact:true}).click();await page.getByLabel('检查方式',{exact:true}).selectOption('quote_rework');
   await page.getByText('返工继承链 · 1 次接续',{exact:true}).click();
   await page.getByText('要求变更记录 · 当前有效 '+(item.name==='uncovered'?6:5)+' 项',{exact:true}).click();
   assert.equal((await detail(id)).task,null);
   if(item.name==='conflict'){
    await page.getByText('当前目标与逐条变更后仍有效的要求不一致',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'保存条件并执行',exact:true}).isDisabled(),true);
    const d=await detail(id),r=await command({action:'review_quote_rework',id,revision:d.plan.revision});
    assert.notEqual((await command({action:'approve',id,revision:d.plan.revision,acceptance:{...r.body.acceptance,coverage:'complete'}})).status,200);
    assert.equal((await detail(id)).task,null);await page.screenshot({path:path.join(out,'conflict.png'),fullPage:true});report.checks.push('Dropped inherited condition blocks UI and HTTP before task creation');continue;
   }
   if(item.name==='correct'){
    await page.getByText('已替换：预算不超过100元',{exact:true}).waitFor();await page.getByText('有效：保留来源引用',{exact:true}).waitFor();
    await page.getByLabel('验收范围',{exact:true}).selectOption('complete');
    await page.screenshot({path:path.join(out,'review-desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(out,'review-mobile.png'),fullPage:true});assert.equal(await page.locator('#modal').evaluate(e=>e.scrollWidth<=e.clientWidth+1),true);await page.setViewportSize({width:1440,height:1000});
   }else{
    await page.getByText('未覆盖：必须保修三年',{exact:true}).waitFor();assert.equal(await page.getByLabel('验收范围',{exact:true}).isDisabled(),true);
    assert.equal(await page.getByLabel('验收范围',{exact:true}).inputValue(),'recipe');await page.screenshot({path:path.join(out,'uncovered-review.png'),fullPage:true});
   }
   await page.getByRole('button',{name:'保存条件并执行',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
   let d;for(let i=0;i<160;i++){d=await detail(id);if(d.task?.status==='SUCCEEDED'&&d.completion?.checks?.length)break;await new Promise(r=>setTimeout(r,100));}
   assert.equal(d.task?.status,'SUCCEEDED');assert.equal(d.completion.state,item.name==='correct'?'VERIFIED':'WAITING_EVIDENCE');assert.equal(d.work.spent_cost_units,4);
   assert.equal(d.work_closure.state==='COMPLETE',item.name==='correct');
   const refreshed=page.waitForResponse(r=>r.url().endsWith('/api/goals')&&r.request().method()==='POST'&&r.request().postDataJSON().action==='detail'&&r.request().postDataJSON().id===id);
   await page.getByRole('button',{name:'刷新详情',exact:true}).click();const response=await refreshed;
   await page.waitForFunction(sig=>document.querySelector('.goal-detail')?.dataset.signature===sig,JSON.stringify(await response.json()));
   await page.locator('.completion-summary').getByText(item.name==='correct'?'已核对明确列出的受支持要求':'等待验收证据',{exact:true}).waitFor();
   await page.locator('.completion-summary').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,item.name+'-result.png'),fullPage:true});
   report.checks.push(item.name+': UI creates linked version, edits input, reviews inherited clauses, executes and independently evaluates');
  }
  report.passed=report.errors.length===0;
 }catch(e){report.errors.push(e.stack);report.passed=false;await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});process.exitCode=1;}
 finally{fs.writeFileSync(path.join(out,'children.json'),JSON.stringify(children,null,2));fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
