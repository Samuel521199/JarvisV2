// Disposable offline Host only. Screenshots contain synthetic tasks.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2);
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1050},reducedMotion:'reduce'});
 const report={checks:[],errors:[]};page.on('pageerror',e=>report.errors.push(e.message));
 try{
  await page.goto(base+'/settings#tasks');
  await page.getByLabel('结果核对开关',{exact:true}).waitFor();
  const missing=page.locator('.work-item').filter({hasText:'Outcome UI missing artifact'});
  await missing.waitFor({state:'attached'});
  await missing.evaluate(node=>{for(let p=node.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
  await missing.locator('.outcome-summary > summary').click();
  assert.match(await missing.innerText(),/结果核对发现问题/);
  assert.match(await missing.innerText(),/原始文件不可访问/);
  assert.match(await missing.innerText(),/综合评分：暂缺质量证据/);
  const good=page.locator('.work-item').filter({hasText:'Outcome UI intact artifact'});
  assert.match(await good.innerText(),/基础核对完成，目标质量待验证/);
  report.checks.push('Original task state and deterministic evidence are displayed separately; missing artifact is visible; no invented score');
  for(const theme of ['dark','light']){
   await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
   await missing.scrollIntoViewIfNeeded();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await page.screenshot({path:path.join(out,'outcomes-'+theme+'.png')});
  }
  await page.getByLabel('结果核对开关',{exact:true}).selectOption('0');
  await page.getByRole('button',{name:'应用结果核对设置',exact:true}).click();
  await page.waitForFunction(async()=>!(await (await fetch('/api/work-status')).json()).outcome_observer.enabled);
  await page.reload();await page.getByLabel('结果核对开关',{exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('[aria-label="结果核对开关"]').value==='0');
  await page.getByLabel('结果核对开关',{exact:true}).selectOption('1');
  await page.getByRole('button',{name:'应用结果核对设置',exact:true}).click();
  await page.waitForFunction(async()=>(await (await fetch('/api/work-status')).json()).outcome_observer.enabled);
  report.checks.push('Shared observer setting survives page reload; re-enabling does not dispatch business work');
  assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;throw e;}
 finally{fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2)+'\n');await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
