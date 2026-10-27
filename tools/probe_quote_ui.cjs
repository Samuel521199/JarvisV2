const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2),fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),report={checks:[],errors:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 async function detail(id){return page.evaluate(async id=>{const s=await(await fetch('/api/session')).json();const r=await fetch('/api/goals',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':s.token},body:JSON.stringify({action:'detail',id})});if(!r.ok)throw Error('detail '+r.status);return r.json();},id);}
 try{
  await page.route('**/quote-probe',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh-CN" data-theme="dark"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/style.css"><body><div id="error" hidden></div><main id="test" style="padding:24px;max-width:1100px;margin:auto"></main><dialog id="modal"><h2 id="modal-title"></h2><div id="modal-content"></div></dialog></body></html>'}));
  for(const item of fixture.cases){
   await page.goto(base+'/quote-probe');await page.evaluate(async f=>{const {goalsView}=await import('/goals.js');goalsView(document.getElementById('test'),{settings:f.settings,initialId:f.id});},{settings:fixture.settings,id:item.id});
   await page.getByRole('button',{name:'约定验收条件并执行',exact:true}).click();
   await page.getByLabel('检查方式',{exact:true}).selectOption('quote_selection');
   await page.getByText(/本次冻结：CNY/).waitFor();assert.equal(await page.getByLabel('预期文本',{exact:true}).isVisible(),false);
   assert.equal(await page.getByLabel('验收范围',{exact:true}).inputValue(),'recipe');
   await page.getByLabel('验收范围',{exact:true}).selectOption('complete');
   if(item.name==='correct'){
    await page.screenshot({path:path.join(out,'frozen-input-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'frozen-input-mobile.png'),fullPage:true});
    assert.equal(await page.locator('#modal').evaluate(e=>e.scrollWidth<=e.clientWidth+1),true);
    await page.setViewportSize({width:1440,height:1000});
   }
   await page.getByRole('button',{name:'保存条件并执行',exact:true}).click();await page.locator('#modal').waitFor({state:'hidden'});
   let d;for(let i=0;i<160;i++){d=await detail(item.id);if(d.task?.status==='SUCCEEDED'&&d.completion?.checks?.length)break;await new Promise(r=>setTimeout(r,100));}
   assert.equal(d.task?.status,'SUCCEEDED');assert.equal(d.completion.state,item.name==='wrong'?'NEEDS_CORRECTION':'VERIFIED');
   assert.equal(d.completion.requirement_coverage.semantic_goal_verified,false);
   assert.equal(d.completion.acceptance.rules.criteria[0].expected.length,64);
   assert.equal(d.work_closure.state==='COMPLETE',item.name!=='wrong');
   await page.getByRole('button',{name:'刷新详情',exact:true}).click();
   await page.getByText(item.name==='wrong'?'所选报价不属于合格最低价方案':item.name==='empty'?'已核对：本次没有同时满足预算和交期的报价':'预算、交期、合格集合、最低价与来源引用已核对',{exact:true}).waitFor();
   await page.locator('.completion-summary').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,item.name+'-result.png'),fullPage:true});
   report.checks.push(item.name+': real UI froze original input digest; tool ran and independent completion matched expected domain verdict');
  }
  report.passed=report.errors.length===0;
 }catch(e){report.errors.push(e.stack);report.passed=false;await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});process.exitCode=1;}
 finally{fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
