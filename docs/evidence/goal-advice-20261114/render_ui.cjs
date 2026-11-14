const fs=require('node:fs/promises'),path=require('node:path'),assert=require('node:assert/strict');
const [port,base,out]=process.argv.slice(2);
(async()=>{
 const pages=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();
 const target=pages.find(p=>p.type==='page');assert(target);
 const ws=new WebSocket(target.webSocketDebuggerUrl),pending=new Map();let serial=0;
 await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
 ws.addEventListener('message',event=>{const value=JSON.parse(event.data);if(!value.id)return;const p=pending.get(value.id);if(!p)return;pending.delete(value.id);if(value.error)p.reject(Error(value.error.message));else p.resolve(value.result);});
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>(await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result.value;
 const rows=[];
 try{
  await call('Page.enable');
  for(const [name,width,height,mobile] of [['desktop',1280,1600,false],['mobile',390,1600,true]]){
   await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile});
   await call('Page.navigate',{url:base+'/?viewport='+name});
   let ready=false;for(let n=0;n<50;n++){await new Promise(r=>setTimeout(r,100));ready=await evaluate(`location.search.includes('viewport=${name}')&&document.body?.dataset.ready==='true'`);if(ready)break;}assert(ready);
   const metrics=await evaluate(`({innerWidth,scrollWidth:document.documentElement.scrollWidth,panels:document.querySelectorAll('.planning-advice').length,containerOverflow:[...document.querySelectorAll('.planning-advice')].some(n=>n.scrollWidth>n.clientWidth+1),text:document.body.innerText})`);
   const checks={exactViewport:metrics.innerWidth===width,noPageOverflow:metrics.scrollWidth<=width+1,noPanelOverflow:!metrics.containerOverflow,threePanels:metrics.panels===3,states:metrics.text.includes('需要重新核对')&&metrics.text.includes('经验贡献仍未证明')&&metrics.text.includes('没有把旧建议重新提供给本次模型')};
   const screenshot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(path.join(out,name+'.png'),Buffer.from(screenshot.data,'base64'));
   const row={viewport:name,width,height,metrics:{innerWidth:metrics.innerWidth,scrollWidth:metrics.scrollWidth,panels:metrics.panels,containerOverflow:metrics.containerOverflow},checks,passed:Object.values(checks).every(Boolean)};rows.push(row);
  }
  const clicked=await evaluate(`(()=>{document.querySelector('.planning-advice button').click();return document.body.dataset.upstreamOpened==='true'})()`);assert(clicked);
  await fs.writeFile(path.join(out,'render-result.json'),JSON.stringify({tool:'existing headless Edge and built-in Node DevTools client; no dependency installation',scope:'shared component with real synthetic receipt and labelled display states; not complete live workbench',rows,upstreamButtonWorks:clicked,passed:rows.every(r=>r.passed)},null,2)+'\n');
  console.log(JSON.stringify({rows,upstreamButtonWorks:clicked}));
 }finally{try{await call('Browser.close');}catch(e){}ws.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
