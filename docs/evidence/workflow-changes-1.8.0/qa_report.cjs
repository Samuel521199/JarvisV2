const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage(),errors=[],viewports=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
  for(const [name,width,height] of [['desktop',1400,1000],['mobile',390,844]]){
   await page.setViewportSize({width,height});await page.goto('file:///'+path.join(__dirname,'report.html').replaceAll('\\','/'));
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
   if(overflow)errors.push(name+' page overflow');
   await page.screenshot({path:path.join(__dirname,'report-'+name+'.png'),fullPage:true});
   await page.screenshot({path:path.join(__dirname,'report-'+name+'-summary.png')});
   await page.locator('details').last().locator('summary').click();
   await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0));
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))errors.push(name+' expanded overflow');
   viewports.push({viewport:name,width,overflow});
  }
 }catch(e){errors.push(e.stack)}finally{await browser.close()}
 const result={passed:errors.length===0,errors,viewports};fs.writeFileSync(path.join(__dirname,'report-ui.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));if(errors.length)process.exitCode=1;
})();
