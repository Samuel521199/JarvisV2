// Opt-in bridge to the first-party local inspection service. No eval or file edits.
export function connectViewerInspection({post, identity, objects, apply, observe, capture, parent}) {
 const label=document.createElement('label'),toggle=document.createElement('input'),notice=document.createElement('span');
 toggle.type='checkbox';toggle.id='jarvis-inspection';label.append(toggle,' Jarvis 检视');
 notice.id='jarvis-inspection-status';notice.setAttribute('role','status');notice.textContent='未连接';parent.append(label,notice);
 let client=null,timer=null,busy=false;
 const send=body=>post('/api/skill/studio3d-inspection',body);
 const binding=()=>({...identity(),client_id:client});
 toggle.onchange=async()=>{
  clearTimeout(timer);
  if(!toggle.checked){const old=client;client=null;if(old)await send({action:'stop',...identity(),client_id:old}).catch(()=>{});notice.textContent='已停止检视连接';return;}
  try{
   if(!identity().sha256)throw Error('请先等待模型加载');
   client=crypto.randomUUID().replaceAll('-','');
   await send({action:'register',...binding(),objects:objects()});
   notice.textContent='Jarvis 可切换视角和显示模式；可随时取消';tick();
  }catch(e){toggle.checked=false;client=null;notice.textContent='连接未完成：'+String(e.message).slice(0,120);}
 };
 async function tick(){
  if(!client||busy)return;
  busy=true;
  try{
   const bound=binding(),{request}=await send({action:'poll',...bound});
   if(request){
    let result;
    try{
     if(!toggle.checked||request.asset_id!==bound.asset_id||request.sha256!==bound.sha256)throw Error('模型或连接已改变');
     await apply(request.view);
     // Observe actual frames after controls, camera and visibility have settled.
     await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
     result={...observe(),applied:request.view};
     if(request.capture)Object.assign(result,capture());
    }catch(error){result={...identity(),error:String(error.message||error).slice(0,240)};}
    await send({action:'ack',...bound,id:request.id,result});
    notice.textContent=result.error?'检视未完成：'+result.error:'已完成 Jarvis 检视 · '+(result.mode||'当前视图');
   }
  }catch(error){toggle.checked=false;client=null;notice.textContent='连接已停止：'+String(error.message||error).slice(0,120);}
  finally{busy=false;if(client)timer=setTimeout(tick,1500);}
 }
}
