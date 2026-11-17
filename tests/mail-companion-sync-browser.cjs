// Real mail view modules with a deliberately unresolved synthetic sync.
// No real mailbox, credentials, model calls or remote message effects.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('C:/Users/samuel/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const output=path.resolve(process.argv[2]);fs.mkdirSync(output,{recursive:true});
const source=path.resolve(__dirname,'../apps/workbench');
const html=`<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/companion-shell.css"><body class="presence-surface"><main class="desktop"><aside id="project-dock"></aside><div id="card" hidden></div><div id="project-dialog" hidden></div><aside id="mail-dock"><button id="dock-button"><span class="count"></span></button><div class="dock-preview"></div></aside><section id="mail-dialog" class="mail-dialog" hidden></section><div id="error" hidden></div></main><script type="module">
import {mailApi} from '/mail-client.js';import {mountMailCompanion} from '/mail-companion.js';
const message={id:'synthetic-message',from:'Synthetic sender <fixture@example.com>',subject:'Synthetic cached letter',snippet:'Local acceptance only',unread:true,classification:{category:'normal',folder:'Test',reason:'Fixture'}};
const state={status:'connected',email:'owner@example.com',account_generation:'g1',snapshot_at:1,unread_count:1,items:[message],capabilities:{read:true,modify:true},view_preferences:{mark_read_on_open:false},authorization:{status:'SUCCEEDED'}};
window.fixture={syncCalls:0,readCalls:0,holdRead:false};mailApi.overview=async()=>structuredClone(state);
mailApi.run=async(operation)=>{if(operation!=='sync')throw Error('Unexpected operation');fixture.syncCalls++;return new Promise(resolve=>fixture.releaseSync=()=>resolve({status:'FAILED'}));};
mailApi.command=async command=>{if(command.action!=='cached_message')throw Error('Unexpected mailbox write');fixture.readCalls++;if(fixture.holdRead)await new Promise(resolve=>fixture.releaseRead=resolve);return {id:message.id,subject:message.subject,from:message.from,date:'Fixture',body:'This full cached body is visible during background sync.',from_cache:true,labels:['INBOX','UNREAD'],account_generation:'g1'};};
window.mail=mountMailCompanion();document.getElementById('dock-button').onclick=()=>mail.open();window.ready=true;
</script>`;
const server=http.createServer((req,res)=>{if(req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');return res.end(html);}const file=path.resolve(source,'.'+decodeURIComponent(req.url.split('?')[0]));if(!file.startsWith(source+path.sep)||!fs.existsSync(file)){res.statusCode=404;return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript; charset=utf-8':'text/css; charset=utf-8');res.end(fs.readFileSync(file));});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({channel:'msedge',headless:true}),report={scope:'Actual mail component in browser; synthetic deferred transport, no real mailbox effects',passed:false,checks:[],errors:[]};
 try{
  const page=await browser.newPage({viewport:{width:800,height:950}});page.on('pageerror',e=>report.errors.push(e.message));
  async function load(){await page.goto(origin);await page.waitForFunction(()=>window.ready);await page.locator('#dock-button').click();await page.waitForFunction(()=>fixture.syncCalls===1);await page.getByRole('button',{name:'正在同步…',exact:true}).waitFor();}
  await load();assert.equal(await page.locator('.live-mail-row').isEnabled(),true,'Background sync must not disable message reading');
  await page.evaluate(()=>mail.open());assert.equal(await page.evaluate(()=>fixture.syncCalls),1,'Reopening must not submit duplicate sync');
  await page.locator('.live-mail-row').click();await page.locator('.mail-detail-body').waitFor();assert.match(await page.locator('.mail-detail-body').innerText(),/full cached body/);
  await page.screenshot({path:path.join(output,'body-during-sync.png')});
  await page.evaluate(()=>fixture.releaseSync());await page.waitForFunction(()=>document.getElementById('mail-live-error')?.textContent.includes('操作未完成'));
  assert.equal(await page.locator('.mail-detail-body').isVisible(),true,'Sync completion must preserve the selected body');
  report.checks.push('Cached body opens while sync is unresolved, duplicate sync suppressed, sync failure preserves reader');
  await load();await page.evaluate(()=>fixture.holdRead=true);await page.locator('.live-mail-row').click();await page.waitForFunction(()=>fixture.readCalls===1);
  await page.evaluate(()=>fixture.releaseSync());await page.getByRole('button',{name:'刷新邮件',exact:true}).waitFor();
  assert.equal(await page.locator('.live-mail-row').isDisabled(),true,'Finishing sync must not release the independent active-read guard');
  await page.evaluate(()=>fixture.releaseRead());await page.locator('.mail-detail-body').waitFor();
  await page.getByRole('button',{name:'← 返回邮件',exact:true}).click();assert.equal(await page.locator('.live-mail-row').isEnabled(),true);
  report.checks.push('Pending read remains protected across sync completion and rows recover after reading');
  await load();await page.getByRole('button',{name:'关闭邮件对话框',exact:true}).click();await page.evaluate(()=>fixture.releaseSync());
  assert.equal(await page.locator('#mail-dialog').isHidden(),true,'Background completion must not reopen a closed panel');
  report.checks.push('Sync completion never reopens a closed mail panel');assert.equal(report.errors.length,0);report.passed=true;
 }catch(error){report.failure=error.message;throw error;}
 finally{fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(report,null,2)+'\n');await browser.close();await new Promise(resolve=>server.close(resolve));}
 console.log(JSON.stringify(report));
})().catch(error=>{console.error(error.message);process.exitCode=1;server.close();});
