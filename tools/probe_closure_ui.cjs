const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2),fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1100}}),report={checks:[],errors:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 async function command(value){return page.evaluate(async v=>{const s=await(await fetch('/api/session')).json();const r=await fetch('/api/goals',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':s.token},body:JSON.stringify(v)});return {status:r.status,body:await r.json()};},value);}
 async function detail(id){const r=await command({action:'detail',id});assert.equal(r.status,200);return r.body;}
 async function done(id){let d;for(let i=0;i<150;i++){d=await detail(id);if(d.task?.status==='SUCCEEDED')break;await new Promise(r=>setTimeout(r,100));}assert.equal(d.task?.status,'SUCCEEDED');await page.getByRole('button',{name:'刷新详情',exact:true}).click();return d;}
 try{
  await page.route('**/closure-probe',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><body><div id="error" hidden></div><main id="test" style="padding:24px;max-width:1100px;margin:auto"></main><dialog id="modal"><h2 id="modal-title"></h2><div id="modal-content"></div></dialog></body></html>'}));
  await page.goto(base+'/closure-probe');await page.evaluate(async f=>{const {goalsView}=await import('/goals.js');goalsView(document.getElementById('test'),{settings:f.settings,initialId:f.id});},fixture);
  await page.getByRole('button',{name:'确认此计划并执行',exact:true}).click();const original=await done(fixture.id);
  await page.getByRole('button',{name:'修改计划并自动分析返工范围',exact:true}).click();
  await page.getByLabel('本次修改说明',{exact:true}).fill('第二步要求更明确，第一步保持原样');await page.getByLabel('第 2 步预期',{exact:true}).fill('字母全部大写，中文原样保留');
  await page.getByRole('button',{name:'分析修改影响',exact:true}).click();await page.getByText('从第 2 步重做 · 保留 1 步 · 预计 2 执行单位（含保存）',{exact:true}).waitFor();
  assert.equal((await detail(fixture.id)).work.versions.length,1);report.checks.push('Read-only analysis keeps one valid prefix step and creates no version');
  await page.getByLabel('修改后的原始输入',{exact:true}).fill('changed input');
  assert.equal(await page.getByRole('button',{name:'按分析结果生成关联计划',exact:true}).count(),0);
  await page.getByRole('button',{name:'分析修改影响',exact:true}).click();await page.getByText('从第 1 步重做 · 保留 0 步 · 预计 3 执行单位（含保存）',{exact:true}).waitFor();report.checks.push('Edited input invalidates UI review and requires all steps');
  await page.getByLabel('修改后的原始输入',{exact:true}).fill('hello 中文');await page.getByRole('button',{name:'分析修改影响',exact:true}).click();await page.getByText('从第 2 步重做 · 保留 1 步 · 预计 2 执行单位（含保存）',{exact:true}).waitFor();
  await page.locator('.impact-summary').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'impact-review.png'),fullPage:true});
  await page.getByRole('button',{name:'按分析结果生成关联计划',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
  const child=(await detail(fixture.id)).work.current_goal;assert.notEqual(child,fixture.id);assert.equal((await detail(child)).task,null);
  await page.getByText('当前版本待核对与受理',{exact:true}).waitFor();assert.equal((await detail(fixture.id)).work_closure.state,'NEEDS_REVIEW');
  report.checks.push('Automatic analysis creates only the linked suffix draft; historical entry sees it as pending');
  const rules={coverage:'complete',criteria:[{id:'literal',step_id:'step-1',check:'text_equals',expected:'HELLO 中文'}],requirements:[{id:'output',text:'字面输出等于 HELLO 中文',kind:'literal',criterion_ids:['literal']}]};
  const admitted=await command({action:'approve_and_run',id:child,revision:1,acceptance:rules});assert.equal(admitted.status,200);
  const completed=await done(child);assert.equal(completed.work_closure.state,'COMPLETE');assert.equal(completed.work_closure.condition_score,100);assert.equal(completed.work_closure.quality_score,null);
  await page.getByText('当前版本已按约定结案',{exact:true}).waitFor();assert.deepEqual((await detail(fixture.id)).actions,original.actions);
  assert.equal(completed.work.spent_cost_units,5);report.checks.push('Frozen literal acceptance closes the current version; original receipts and cumulative cost persist');
  await page.getByRole('button',{name:'修改计划并自动分析返工范围',exact:true}).click();
  await page.getByLabel('修改后的完整目标',{exact:true}).fill('新目标需要重新核对最早的输入和前段');
  await page.getByLabel('本次修改说明',{exact:true}).fill('不能把当前后段当作完整原始流程');await page.getByRole('button',{name:'分析修改影响',exact:true}).click();
  await page.getByText('当前计划复用了更早的前段；目标或输入变化时，请重新核对完整计划，不能只重做当前后段。',{exact:true}).waitFor();
  assert.equal((await detail(child)).work.versions.length,2);await page.keyboard.press('Escape');
  report.checks.push('Goal changes after ancestral prefix reuse require a complete reviewed plan; no misleading partial draft is created');
  await page.getByRole('button',{name:'刷新计划',exact:true}).click();await page.getByText('执行中',{exact:true}).waitFor({state:'hidden'});
  for(const theme of ['dark','light']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(out,'closure-'+theme+'.png'),fullPage:true});}
  await page.getByRole('button',{name:'指出需要修改',exact:true}).click();await page.getByLabel('结果反馈说明',{exact:true}).fill('迟到纠正：需要进一步确认业务含义');await page.getByRole('button',{name:'保存反馈',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
  await page.getByText('当前版本尚未结案',{exact:true}).waitFor();assert.equal((await detail(fixture.id)).work_closure.state,'NEEDS_EVIDENCE');assert.equal((await detail(child)).task.status,'SUCCEEDED');
  report.checks.push('Late correction reopens work across entrypoints without rewriting successful execution');
  const chat=await page.evaluate(async id=>(await fetch('/api/chats/'+id)).json(),fixture.chat_id);
  assert.equal(chat.turns[0].linked_goal.id,fixture.id);assert.equal(chat.turns[0].linked_goal.work_closure.current_goal,child);
  assert.equal(chat.turns[0].linked_goal.work_closure.state,'NEEDS_EVIDENCE');assert.equal(chat.turns[0].linked_goal.output,'HELLO 中文');
  await page.evaluate(async turn=>{const {actionCard}=await import('/assistant-actions.js');const p=document.createElement('section');p.id='chat-preview';document.getElementById('test').append(p);actionCard(p,turn,{openGoal:()=>{},refresh:()=>{},openMemory:()=>{}});},chat.turns[0]);
  await page.locator('#chat-preview').getByText('当前版本尚未结案',{exact:true}).waitFor();await page.locator('#chat-preview').getByRole('button',{name:'打开当前工作版本',exact:true}).waitFor();
  await page.locator('#chat-preview').screenshot({path:path.join(out,'conversation-closure.png')});
  report.checks.push('Real chat projection and the original conversation card expose the same current closure while retaining old output');
  report.snapshot=await detail(child);assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;report.body=await page.locator('body').innerText();await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2)+'\n');await browser.close();}
 console.log(JSON.stringify({passed:report.passed,checks:report.checks,errors:report.errors}));
})().catch(e=>{console.error(e);process.exitCode=1;});
