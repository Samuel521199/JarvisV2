const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2),fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1100}}),report={checks:[],errors:[],requests:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/api/goals'))report.requests.push({url:new URL(r.url()).pathname,body:r.postDataJSON()});});
 async function detail(id){return page.evaluate(async id=>{const session=await(await fetch('/api/session')).json();return(await fetch('/api/goals',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':session.token},body:JSON.stringify({action:'detail',id})})).json();},id);}
 async function done(id){let state;for(let i=0;i<150;i++){state=(await detail(id)).task;if(state?.status==='SUCCEEDED')break;await new Promise(r=>setTimeout(r,100));}assert.equal(state?.status,'SUCCEEDED',JSON.stringify(state));await page.getByRole('button',{name:'刷新详情',exact:true}).click();}
 try{
  await page.route('**/rework-probe',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><body><div id="error" hidden></div><main id="test" style="padding:24px;max-width:1100px;margin:auto"></main><dialog id="modal"><h2 id="modal-title"></h2><div id="modal-content"></div></dialog></body></html>'}));
  await page.goto(base+'/rework-probe');await page.evaluate(async f=>{const {goalsView}=await import('/goals.js');goalsView(document.getElementById('test'),{settings:f.settings,initialId:f.id});},fixture);
  await page.getByRole('button',{name:'确认此计划并执行',exact:true}).click();await done(fixture.id);
  const original=await detail(fixture.id);
  await page.getByRole('button',{name:'关联返工 / 追加要求',exact:true}).click();
  await page.getByLabel('完整的新要求',{exact:true}).fill('第一步保留，重新核对第二步并保存结果');
  await page.getByLabel('变更原因',{exact:true}).fill('第二步需要重新核对，前段结果保留');
  await page.getByLabel('变更类型',{exact:true}).selectOption('correction');await page.getByLabel('最早需要重做的步骤',{exact:true}).selectOption('2');
  await page.getByRole('button',{name:'生成关联计划',exact:true}).click();
  await page.getByRole('button',{name:'确认此计划并执行',exact:true}).waitFor();
  const parent=await detail(fixture.id),child=parent.work.current_goal,draft=await detail(child);
  assert.notEqual(child,fixture.id);assert.equal(draft.task,null);assert.equal(draft.plan.proposal.input_text,'HELLO 中文');assert.equal(draft.plan.proposal.steps.length,1);
  assert.equal(parent.completion.state,'NEEDS_CORRECTION');report.checks.push('Linked correction pins prefix and records negative feedback; draft creates no task');
  await page.getByRole('button',{name:'打开第 1 版',exact:true}).click();
  await page.getByRole('button',{name:'指出需要修改',exact:true}).click();await page.getByLabel('结果反馈说明',{exact:true}).fill('迟到反馈：末步需要重新核对，前段文字转换保持适用');await page.getByRole('button',{name:'保存反馈',exact:true}).click();
  await page.locator('#modal').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'打开当前版本',exact:true}).click();
  await page.getByRole('button',{name:'重新核对已变化的复用依据',exact:true}).click();await page.getByLabel('说明为何前段结果仍然适用',{exact:true}).fill('已重新检查原前段回执，此次反馈只涉及末步');await page.getByRole('button',{name:'记录核对并更新依据',exact:true}).click();
  await page.locator('#modal').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'约定验收条件并执行',exact:true}).waitFor();
  assert.equal((await detail(child)).plan.revision,2);assert.equal((await detail(fixture.id)).completion.feedback_history.length,2);
  report.checks.push('Late feedback is preserved; explicit draft source review updates the revision without an execution task');
  await page.getByRole('button',{name:'约定验收条件并执行',exact:true}).click();
  await page.getByLabel('检查方式',{exact:true}).selectOption('text_equals');await page.getByLabel('预期文本',{exact:true}).fill('HELLO 中文');
  await page.getByRole('button',{name:'保存条件并执行',exact:true}).click();await done(child);
  const completed=await detail(child),old=await detail(fixture.id);
  report.snapshot={completed,old};
  assert.equal(completed.task.status,'SUCCEEDED');
  assert.equal(completed.task.spent,2);assert.equal(old.task.spent,3);assert.deepEqual(old.actions,original.actions);
  assert.equal(completed.work.spent_cost_units,5);assert.equal(completed.completion.condition_score,100);
  assert.equal(report.requests.filter(r=>r.url==='/api/goals/run').length,0);
  report.checks.push('One suffix action plus delivery; original actions unchanged; acceptance is separately reviewed');
  await page.getByRole('button',{name:'刷新计划',exact:true}).click();
  await page.getByText('执行中',{exact:true}).waitFor({state:'hidden'});
  for(const theme of ['dark','light']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await page.getByText('这件工作的负责人 · Jarvis 默认 Bot',{exact:true}).scrollIntoViewIfNeeded();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(out,'rework-'+theme+'.png'),fullPage:true});}
  await page.getByRole('button',{name:'打开第 1 版',exact:true}).click();await page.getByRole('button',{name:'打开当前版本',exact:true}).waitFor();
  await page.getByRole('button',{name:'停止整件工作接续',exact:true}).click();
  await page.getByText('整件工作已停止接续',{exact:true}).waitFor();assert.equal((await detail(fixture.id)).task.status,'SUCCEEDED');
  report.checks.push('Original version links to current work; whole-work stop preserves completed facts');
  assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;throw e;}
 finally{fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2)+'\n');await browser.close();}
 console.log(JSON.stringify({passed:report.passed,checks:report.checks,errors:report.errors}));
})().catch(e=>{console.error(e);process.exitCode=1;});
