const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.argv[2]);const config=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:960}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  assert.equal((await context.request.post(config.origin+'/api/local-access',{headers:{Origin:config.origin},data:{key:config.key}})).status(),200);
  const token=(await (await context.request.get(config.origin+'/api/session')).json()).token;
  const headers={Origin:config.origin,'X-Jarvis-Token':token};
  async function post(path,value){const r=await context.request.post(config.origin+path,{headers,data:value});assert.ok(r.ok(),await r.text());return r.json();}
  const chat=(await post('/api/chats',{})).id;
  async function send(text){
   const id='chat-commit-'+Math.random().toString(16).slice(2);
   await post('/api/chat/send',{chat_id:chat,request_id:id,text,provider:'openai',model:'test-model',reasoning:'default',assistant_mode:true});
   for(let attempt=0;attempt<100;attempt++){
    const data=await (await context.request.get(config.origin+'/api/chats/'+chat)).json(),turn=data.turns.find(t=>t.id===id);
    if(turn&&!['READY','RUNNING'].includes(turn.status))return turn;
    await new Promise(resolve=>setTimeout(resolve,100));
   }throw Error('Chat did not finish');
  }
  async function waitMode(id,mode){
   for(let n=0;n<50;n++){
    const data=await (await context.request.get(config.origin+'/api/chats/'+chat)).json(),turn=data.turns.find(t=>t.id===id);
    if(turn?.commitment_action?.mode===mode)return turn;
    await new Promise(r=>setTimeout(r,100));
   }throw Error('No '+mode+' receipt');
  }
  const original=await send('2030-01-01T12:00:00+08:00提醒我回邮件');await waitMode(original.id,'APPLIED');
  const pending=await send('明天下午提醒我整理周报');await waitMode(pending.id,'NEEDS_TIME');
  assert.equal((await (await context.request.get(config.origin+'/api/commitments')).json()).items.length,1);
  const clarification=await send('15:00 UTC+08:00');await waitMode(clarification.id,'APPLIED');
  const cancelled=await send('取消回邮件');const cancelReceipt=await waitMode(cancelled.id,'APPLIED');assert.equal(cancelReceipt.commitment_action.receipt.current.status,'CANCELLED');
  const manual=await send('明天下午提醒我检查日志');await waitMode(manual.id,'NEEDS_TIME');
  await page.goto(config.origin+'/#chat='+chat);
  await page.getByText('本地待办候选',{exact:true}).last().waitFor();
  if(await page.getByRole('button',{name:'跳过动画',exact:true}).isVisible())await page.getByRole('button',{name:'跳过动画',exact:true}).click();
  await page.locator('#cinema').waitFor({state:'hidden'});
  const form=page.locator('form').filter({has:page.getByRole('button',{name:'保存此本地待办',exact:true})}).last();
  await form.getByLabel('明确提醒时间',{exact:true}).fill('2030-01-01T15:00');
  await form.getByLabel('固定UTC偏移，例如 +08:00',{exact:true}).fill('+08:00');
  await page.waitForResponse(r=>r.url().endsWith('/api/chats/'+chat));
  assert.equal(await form.getByLabel('明确提醒时间',{exact:true}).inputValue(),'2030-01-01T15:00');
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/assistant/commitment'),{timeout:5000});
  await form.getByRole('button',{name:'保存此本地待办',exact:true}).click();
  const savedReply=await saved;const savedBody=await savedReply.json();assert.equal(savedBody.mode,'APPLIED',JSON.stringify(savedBody));
  await waitMode(manual.id,'APPLIED');
  await page.reload();await page.getByText('本地待办受理回执',{exact:true}).last().waitFor();
  if(await page.getByRole('button',{name:'跳过动画',exact:true}).isVisible())await page.getByRole('button',{name:'跳过动画',exact:true}).click();
  await page.locator('#cinema').waitFor({state:'hidden'});
  await page.getByText('本地待办受理回执',{exact:true}).last().locator('..').screenshot({path:config.screenshot,animations:'disabled'});
  const items=(await (await context.request.get(config.origin+'/api/commitments')).json()).items;
  assert.equal(items.length,3);assert.equal(items.find(i=>i.title==='回邮件').raw_status,'CANCELLED');
  assert.equal(items.find(i=>i.title==='检查日志').due_text,'2030-01-01T15:00:00+08:00');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,scope:'real local HTTP and browser; model responses are deterministic substitutes',chat_id:chat,
   checks:['automatic-explicit-time','ambiguous-time-no-write','linked-time-clarification','same-chat-cancel','explicit-time-card','reload-receipts'],errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
