const fs=require('node:fs'),cp=require('node:child_process'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/samuel/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const origin='http://127.0.0.1:18282';
const out='C:/Users/samuel/AppData/Local/Temp/Jarvis-mail-standing-browser-20261110';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:false});
 const report={passed:false,checks:[],errors:[],scope:'real browser UI, shared companion webpage; native window clicks not automated'};
 try{
  const context=await browser.newContext({viewport:{width:1360,height:920},reducedMotion:'reduce'});
  let key=cp.execFileSync('D:/soft/Python313/python.exe',['-B','-c',"from control.local_access import read_key; print(read_key('D:/Jarvis/user-data'))"],{cwd:'D:/Jarvis-dev',encoding:'utf8'}).trim();
  const auth=await context.request.post(origin+'/api/local-access',{headers:{Origin:origin},data:{key}});key='';assert.ok(auth.ok());
  const before=await(await context.request.get(origin+'/api/mail-standing')).json();
  for(const surface of ['workbench','companion']){
   const page=await context.newPage();page.on('pageerror',e=>report.errors.push({surface,message:e.message}));
   await page.goto(origin+(surface==='workbench'?'/':'/companion'),{waitUntil:'networkidle'});
   await page.locator(surface==='workbench'?'#core-state':'#work-button').click();
   await page.getByRole('button',{name:'持续办事',exact:true}).click();
   await page.getByRole('button',{name:'邮件与待办',exact:true}).click();
   await page.getByRole('heading',{name:'重要邮件持续助手',exact:true}).waitFor();
   assert.ok(await page.getByRole('button',{name:'+ 制定邮件安排',exact:true}).isVisible());
   await page.screenshot({path:out+'/'+surface+'.png'});
   report.checks.push({surface,passed:true,path:'work status -> standing -> mail standing'});
  }
  const after=await(await context.request.get(origin+'/api/mail-standing')).json();
  assert.deepEqual(after,before);assert.deepEqual(report.errors,[]);
  report.checks.push({case:'opening both surfaces does not create or activate a mandate',passed:true});
  report.passed=true;
 }catch(e){report.error=String(e.stack);process.exitCode=1;}
 finally{fs.writeFileSync(out+'/result.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await browser.close();}
})();
