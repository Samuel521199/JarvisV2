const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2),fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),report={checks:[],errors:[]},children={};
 page.on('pageerror',e=>report.errors.push(e.message));
 async function command(value){return page.evaluate(async value=>{const s=await(await fetch('/api/session')).json();const r=await fetch('/api/goals',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':s.token},body:JSON.stringify(value)});return {status:r.status,body:await r.json()};},value);}
 async function detail(id){const r=await command({action:'detail',id});assert.equal(r.status,200);return r.body;}
 try{
  await page.route('**/recovery-probe',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><body><div id="error" hidden></div><main id="test" style="padding:24px;max-width:1100px;margin:auto"></main><dialog id="modal"><h2 id="modal-title"></h2><div id="modal-content"></div></dialog></body></html>'}));
  for(const item of fixture.cases){
   await page.goto(base+'/recovery-probe');await page.evaluate(async f=>{const {goalsView}=await import('/goals.js');goalsView(document.getElementById('test'),{settings:f.settings,initialId:f.id});},{settings:fixture.settings,id:item.id});
   const old=await detail(item.id),analyzed=page.waitForResponse(r=>r.url().endsWith('/api/goals')&&r.request().method()==='POST'&&r.request().postDataJSON().action==='analyze_recovery');
   await page.getByRole('button',{name:'分析来源失效与恢复',exact:true}).click();const analysis=await analyzed;
   if(item.name==='conflict'){
    assert.notEqual(analysis.status(),200);assert.equal(await page.getByRole('button',{name:'建立恢复草案',exact:true}).count(),0);
    const d=await detail(item.id);assert.equal(d.work.versions.length,2);assert.equal(d.task.status,'READY');children[item.name]=item.id;
    await page.screenshot({path:path.join(out,'conflict.png'),fullPage:true});report.checks.push('Changed original request blocks recovery analysis and creates no version');continue;
   }
   assert.equal(analysis.status(),200);await page.getByText('只发现可证明的反馈变化；原话、有效要求和已确认回执保持原依据。',{exact:true}).waitFor();
   assert.equal(await page.getByRole('button',{name:'建立恢复草案',exact:true}).isDisabled(),true);
   await page.getByLabel('保持全部当前要求',{exact:true}).check();assert.equal(await page.getByRole('button',{name:'建立恢复草案',exact:true}).isDisabled(),true);
   await page.getByLabel('恢复说明',{exact:true}).fill('已核对来源反馈，完整保留当前要求并重新验收。');
   if(item.name==='correct'){
    await page.screenshot({path:path.join(out,'analysis-desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(out,'analysis-mobile.png'),fullPage:true});assert.equal(await page.locator('#modal').evaluate(e=>e.scrollWidth<=e.clientWidth+1),true);await page.setViewportSize({width:1440,height:1000});
   }
   const created=page.waitForResponse(r=>r.url().endsWith('/api/goals')&&r.request().method()==='POST'&&r.request().postDataJSON().action==='recover_work');
   await page.getByRole('button',{name:'建立恢复草案',exact:true}).click();const response=await created;assert.equal(response.status(),200);const id=(await response.json()).id;children[item.name]=id;
   await page.locator('#modal').waitFor({state:'hidden'});const draft=await detail(id);assert.equal(draft.task,null);assert.equal(draft.plan.request.goal,old.plan.request.goal);
   assert.equal(draft.plan.proposal.input_text,old.plan.proposal.input_text);assert.equal(draft.work.root_goal,old.work.root_goal);
   assert.equal((await detail(item.id)).task.status,item.name==='correct'?'SUCCEEDED':'CANCELLED');
   assert.equal(await page.getByRole('button',{name:'确认此计划并执行',exact:true}).count(),0);
   await page.getByRole('button',{name:'约定验收条件并执行',exact:true}).click();await page.getByLabel('检查方式',{exact:true}).selectOption('quote_recovery');
   await page.getByText('来源恢复边界 · 1 次',{exact:true}).waitFor();
   if(item.name==='correct')await page.getByLabel('验收范围',{exact:true}).selectOption('complete');
   else{
    await page.getByText('未覆盖：必须保修三年',{exact:true}).waitFor();assert.equal(await page.getByLabel('验收范围',{exact:true}).isDisabled(),true);
    assert.equal(await page.getByLabel('验收范围',{exact:true}).inputValue(),'recipe');
   }
   await page.screenshot({path:path.join(out,item.name+'-review.png'),fullPage:true});
   await page.getByRole('button',{name:'保存条件并执行',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
   let d;for(let i=0;i<160;i++){d=await detail(id);if(d.task?.status==='SUCCEEDED'&&d.completion?.checks?.length)break;await new Promise(r=>setTimeout(r,100));}
   assert.equal(d.task?.status,'SUCCEEDED');assert.equal(d.completion.state,item.name==='correct'?'VERIFIED':'WAITING_EVIDENCE');assert.equal(d.work.spent_cost_units,item.name==='correct'?6:4);
   assert.equal(d.work_closure.state==='COMPLETE',item.name==='correct');
   const refreshed=page.waitForResponse(r=>r.url().endsWith('/api/goals')&&r.request().method()==='POST'&&r.request().postDataJSON().action==='detail'&&r.request().postDataJSON().id===id);
   await page.getByRole('button',{name:'刷新详情',exact:true}).click();const res=await refreshed;
   await page.waitForFunction(sig=>document.querySelector('.goal-detail')?.dataset.signature===sig,JSON.stringify(await res.json()));
   await page.locator('.completion-summary').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,item.name+'-result.png'),fullPage:true});
   report.checks.push(item.name+': explicit recovery draft, preserved requirements, fresh acceptance and unchanged cumulative spending');
  }
  report.passed=report.errors.length===0;
 }catch(e){report.errors.push(e.stack);report.passed=false;await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});process.exitCode=1;}
 finally{fs.writeFileSync(path.join(out,'children.json'),JSON.stringify(children,null,2));fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
