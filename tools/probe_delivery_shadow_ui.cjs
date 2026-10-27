const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [base,out]=process.argv.slice(2),fixture=JSON.parse(fs.readFileSync(path.join(out,'fixture.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1400,height:1000}}),report={checks:[],errors:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 try{
  await page.goto(base+'/#chat='+fixture.chat);
  await page.waitForFunction(()=>!document.querySelector('#send')?.disabled&&document.querySelector('.chat-row.active'));
  await page.locator('#message').waitFor();await page.locator('.delivery-basis-editor summary').click();
  await page.locator('#delivery-basis-facts').fill('数据导出失败，原因未知。');await page.locator('#delivery-basis-plans').fill('明天10点检查日志，不重跑导出。');
  await page.locator('#message').fill('首轮：请整理记录，仅回复，不执行。');
  const sent=page.waitForResponse(r=>r.url().endsWith('/api/chat/send')&&r.request().method()==='POST');await page.locator('#send').click();assert.equal((await sent).status(),202);
  await page.locator('.delivery-review[data-review-state="REVIEW"]').waitFor();
  let data=await page.evaluate(async id=>(await fetch('/api/chats/'+id)).json(),fixture.chat);
  assert.equal(data.delivery_basis.revision,1);assert.equal(data.turns[0].status,'SUCCEEDED');assert.equal(data.turns[0].reply,'数据导出失败，原因未知。');assert.equal(data.turns[0].delivery_review.would_block,false);
  report.checks.push('UI supplies explicit source lines; original HTTP/store/model path saves review without changing or failing reply');
  await page.reload();await page.locator('.delivery-review[data-review-state="REVIEW"]').waitFor();
  await page.locator('.delivery-basis-editor summary').click();assert.equal(await page.locator('#delivery-basis-plans').inputValue(),'明天10点检查日志，不重跑导出。');
  await page.locator('#delivery-basis-facts').fill('导出尚未开始。');await page.locator('#delivery-basis-plans').fill('周五9点检查日志，不重跑导出。');await page.locator('#message').fill('第二轮：明确更正资料并改期。仅回复，不执行。');
  await page.locator('#send').click();await page.locator('.delivery-review[data-review-state="PROSE_UNVERIFIED"]').waitFor();await page.locator('.delivery-review[data-review-state="STALE"]').waitFor();
  data=await page.evaluate(async id=>(await fetch('/api/chats/'+id)).json(),fixture.chat);assert.equal(data.delivery_basis.revision,2);assert.equal(data.turns[0].delivery_basis.revision,1);assert.equal(data.turns[0].delivery_review.stale,true);
  report.checks.push('Reload preserves basis; explicit replacement increments revision; old review marked stale and old snapshot retained');
  const stale=await page.evaluate(async id=>{const s=await(await fetch('/api/session')).json();const r=await fetch('/api/chat/send',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':s.token},body:JSON.stringify({chat_id:id,request_id:'stale-shadow-ui',text:'无资料更新',provider:'openai',model:'fixture',reasoning:'default',delivery_basis:{expected_revision:1,facts:[],plans:[]}})});return {status:r.status,body:await r.json()};},fixture.chat);
  assert.equal(stale.body.error,'delivery_basis_conflict');assert.ok(stale.status>=400);report.checks.push('Stale revision is rejected, no implicit overwrite');
  await page.locator('.delivery-review').last().locator('summary').click();await page.screenshot({path:path.join(out,'shadow-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});for(const selector of ['.delivery-basis-editor','.delivery-review'])assert.equal(await page.locator(selector).last().evaluate(e=>e.scrollWidth<=e.clientWidth+1),true);
  report.mobileGeometry=await page.evaluate(()=>{const s=document.querySelector('#send').getBoundingClientRect(),e=document.querySelector('.delivery-basis-editor').getBoundingClientRect();return {height:innerHeight,sendTop:s.top,sendBottom:s.bottom,editorHeight:e.height};});
  assert.ok(report.mobileGeometry.sendTop>=0&&report.mobileGeometry.sendBottom<=report.mobileGeometry.height);
  await page.screenshot({path:path.join(out,'shadow-mobile.png'),fullPage:true});await page.setViewportSize({width:1400,height:1000});
  await page.locator('#delivery-basis-facts').fill('');await page.locator('#delivery-basis-plans').fill('');await page.locator('#message').fill('清空依据，之后不再使用旧计划核对。');await page.locator('#send').click();await page.locator('.delivery-review[data-review-state="NO_BASIS"]').waitFor();
  data=await page.evaluate(async id=>(await fetch('/api/chats/'+id)).json(),fixture.chat);assert.equal(data.delivery_basis.entries.length,0);assert.equal(data.delivery_basis.revision,3);
  report.checks.push('Explicit clear stops later checking; old plans remain historical only; feature panels fit desktop/mobile');
  assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;report.visibleError=await page.locator('#error').innerText().catch(()=>null);await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});process.exitCode=1;}finally{fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})();
