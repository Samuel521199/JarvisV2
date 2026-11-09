const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.argv[2]);
const config=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:900}});
  const errors=[];const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  const unlock=await context.request.post(config.origin+'/api/local-access',{headers:{Origin:config.origin},data:{key:config.key}});assert.equal(unlock.status(),200);
  await page.goto(config.origin+'/settings#tasks');
  await page.getByRole('button',{name:'新增个人待办',exact:true}).click();
  await page.getByLabel('待办事项',{exact:true}).fill('浏览器待办闭环');
  await page.getByLabel('原始要求或来源说明（本人填写）',{exact:true}).fill('本人测试要求：到期后在本地工作视图提醒。');
  await page.getByLabel('提醒时间（留空则只记待办）',{exact:true}).fill('2001-01-01T12:00');
  await page.getByLabel('固定UTC偏移，例如 +08:00',{exact:true}).fill('+08:00');
  await page.getByRole('button',{name:'保存',exact:true}).click();
  const row=page.locator('.work-item').filter({hasText:'浏览器待办闭环'});
  await row.getByRole('button',{name:'标记已阅',exact:true}).waitFor({timeout:12000});
  const token=(await (await context.request.get(config.origin+'/api/session')).json()).token;
  const item=(await (await context.request.get(config.origin+'/api/commitments')).json()).items.find(i=>i.title==='浏览器待办闭环');
  assert.equal(item.raw_status,'DUE');assert.equal(item.attention.unread,true);
  await row.getByRole('button',{name:'标记已阅',exact:true}).click();
  const other=await context.newPage();other.on('pageerror',e=>errors.push(e.message));
  await other.goto(config.origin+'/companion');
  await other.waitForFunction(()=>document.querySelector('#work-summary').textContent!=='正在连接本机服务');
  await other.getByRole('button',{name:'所有工作与未读结果',exact:true}).click();
  const otherRow=other.locator('.work-item').filter({hasText:'浏览器待办闭环'});
  await otherRow.getByRole('button',{name:'标记完成',exact:true}).waitFor();
  assert.equal(await otherRow.getByRole('button',{name:'标记已阅',exact:true}).count(),0);
  await otherRow.getByRole('button',{name:'改期',exact:true}).click();
  await other.getByLabel('提醒时间（留空则只记待办）',{exact:true}).fill('2030-01-01T12:00');
  await other.getByRole('button',{name:'保存',exact:true}).click();
  await otherRow.getByText('等待约定时间',{exact:true}).waitFor();
  await otherRow.getByRole('button',{name:'标记完成',exact:true}).click();
  // Open terminal groups before checking the rendered result.
  await other.locator('.work-group[data-state="finished"]').evaluate(n=>n.open=true);
  await otherRow.getByText('主人已标记完成',{exact:true}).waitFor();
  await page.bringToFront();await page.reload();await page.getByRole('button',{name:'新增个人待办',exact:true}).waitFor();
  await page.locator('.work-group[data-state="finished"]').waitFor();
  await page.locator('.work-group[data-state="finished"]').evaluate(n=>n.open=true);
  await page.locator('.work-item').filter({hasText:'浏览器待办闭环'}).getByText('主人已标记完成',{exact:true}).waitFor();
  await page.locator('.work-item').filter({hasText:'浏览器待办闭环'}).screenshot({path:config.screenshot,animations:'disabled'});
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,errors,scope:'headless real workbench and companion entry; not native shell',checks:['create','due','explicit-read','cross-view-read','reschedule','complete','reload']}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
