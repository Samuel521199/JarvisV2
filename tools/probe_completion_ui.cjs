const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2);
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1080},reducedMotion:'reduce'}),report={checks:[],errors:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 async function waitState(predicate){const end=Date.now()+15000;while(Date.now()<end){const data=await (await page.request.get(base+'/api/work-status')).json();if(predicate(data))return data;await new Promise(resolve=>setTimeout(resolve,100));}throw Error('Expected workflow state did not arrive');}
 async function openGroups(){await page.locator('.work-status-list .work-group').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));}
 try{
  await page.goto(base+'/settings#tasks');await page.locator('.completion-summary').first().waitFor({state:'attached'});await openGroups();
  const source=page.locator('.work-item').filter({hasText:'Outcome UI intact artifact'});
  assert.match(await source.innerText(),/约定检查通过率：100%/);
  await source.getByRole('button',{name:'用这个方法处理新文本',exact:true}).click();
  await page.getByLabel('本次待处理文本',{exact:true}).fill('one two three');
  await page.getByRole('button',{name:'处理新文本并保存报告',exact:true}).click();
  await waitState(r=>r.items.some(i=>i.title==='分析本次文本并保存统计报告'&&i.completion?.state==='SATISFIED'));
  const data=await (await page.request.get(base+'/api/work-status')).json(),child=data.items.find(i=>i.title==='分析本次文本并保存统计报告');
  if(!child?.completion)throw Error('Missing completion: '+JSON.stringify(data.items.map(i=>({id:i.id,title:i.title,status:i.raw_status,completion:i.completion,outcome:i.outcome?.state}))));
  assert.equal(child.completion.state,'SATISFIED');report.checks.push('UI method reuse creates a fresh task; the real scheduler executes and verifies its result');
  await page.getByRole('button',{name:'刷新工作状态',exact:true}).click();await openGroups();
  await source.getByRole('button',{name:'指出需要修改',exact:true}).click();
  await page.getByLabel('结果反馈说明',{exact:true}).fill('实际使用发现条件不合适，暂停复用');
  await page.getByRole('button',{name:'保存反馈',exact:true}).click();
  await waitState(r=>r.items.some(i=>i.title==='Outcome UI intact artifact'&&i.completion?.state==='NEEDS_CORRECTION'));
  const after=await (await page.request.get(base+'/api/work-status')).json();
  assert.equal(after.items.find(i=>i.id===child.id).completion.state,'INVALIDATED');
  assert.equal(after.items.find(i=>i.title==='Outcome UI intact artifact').completion.method_available,false);
  report.checks.push('Late correction reopens the source and invalidates the actual adoption while execution facts remain succeeded');
  await page.getByRole('button',{name:'刷新工作状态',exact:true}).click();await openGroups();
  await source.getByRole('button',{name:'复核方法的新证据',exact:true}).waitFor({state:'visible'});
  for(const theme of ['dark','light']){await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);await source.evaluate(node=>node.scrollIntoView({block:'center',behavior:'instant'}));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(out,'completion-'+theme+'.png')});}
  await source.getByRole('button',{name:'撤回这次纠正',exact:true}).click();await page.getByLabel('结果反馈说明',{exact:true}).fill('已核对是输入范围不同，保留例外记录');await page.getByRole('button',{name:'保存反馈',exact:true}).click();
  await waitState(r=>r.items.some(i=>i.title==='Outcome UI intact artifact'&&i.completion?.feedback?.kind==='withdraw'));
  const latest=await (await page.request.get(base+'/api/work-status')).json();assert.equal(latest.items.find(i=>i.title==='Outcome UI intact artifact').completion.method_available,false);
  report.checks.push('Withdrawing feedback retains history and does not silently reactivate quarantined methods');
  assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;throw e;}
 finally{fs.writeFileSync(path.join(out,'completion-browser.json'),JSON.stringify(report,null,2)+'\n');await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
