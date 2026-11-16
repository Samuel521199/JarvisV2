import {el,button} from './ui.js';

// Local recording only. Opening the panel never opens the microphone.
export function captureVoice(parent,{onRecording,onError}){
 let releaseMic=null,opening=false,stream=null,context=null,processor=null,source=null,timer=null,chunks=[],samples=0,url=null,disposed=false;
 const status=el('p','录音保存在本机，请核对识别文字后再提交。','note');
 const playback=el('audio');playback.controls=true;
 const start=button('开始录音',async()=>{
  try{
   if(stream||disposed||opening)return;opening=true;
   if(!navigator.locks)throw Error('浏览器不支持跨窗口麦克风保护，请使用当前Chrome/Edge。');
   await new Promise((resolve,reject)=>navigator.locks.request('jarvis-microphone',{ifAvailable:true},lock=>{if(!lock){reject(Error('另一个Jarvis窗口正在录音。'));return;}return new Promise(release=>{releaseMic=release;resolve();});}));
   if(disposed){cleanup();return;}
   stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true},video:false});
   if(disposed){cleanup();return;}
   context=new AudioContext();source=context.createMediaStreamSource(stream);processor=context.createScriptProcessor(4096,1,1);chunks=[];samples=0;onRecording(null);
   processor.onaudioprocess=e=>{const a=e.inputBuffer.getChannelData(0);chunks.push(new Float32Array(a));samples+=a.length;};
   source.connect(processor);processor.connect(context.destination);status.textContent='正在录音，最多60秒；停止后可回听并确认转写。';timer=setTimeout(stop,60000);
  }catch(e){cleanup();onError('无法录音：'+e.message);}finally{opening=false;}
 });
 function cleanup(){releaseMic?.();releaseMic=null;clearTimeout(timer);if(processor){processor.disconnect();processor.onaudioprocess=null;}source?.disconnect();stream?.getTracks().forEach(t=>t.stop());stream=null;context?.close();}
 function stop(){
  if(!stream)return;
  const rate=context.sampleRate;cleanup();
  const full=new Float32Array(samples);let offset=0;for(const part of chunks){full.set(part,offset);offset+=part.length;}
  const n=Math.min(960000,Math.floor(samples*16000/rate));if(n<1600){onError('录音太短，请至少说一句话。');return;}
  const data=new ArrayBuffer(44+n*2),v=new DataView(data),put=(at,s)=>[...s].forEach((c,i)=>v.setUint8(at+i,c.charCodeAt(0)));
  put(0,'RIFF');v.setUint32(4,36+n*2,true);put(8,'WAVEfmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);put(36,'data');v.setUint32(40,n*2,true);
  for(let i=0;i<n;i++){const x=full[Math.min(samples-1,Math.floor(i*rate/16000))];v.setInt16(44+i*2,Math.max(-1,Math.min(1,x))*32767,true);}
  const bytes=new Uint8Array(data);let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(new Blob([data],{type:'audio/wav'}));playback.src=url;onRecording(btoa(binary));status.textContent='录音已准备，可回听并核对上方识别结果。';
 }
 parent.append(start,button('停止录音',stop),playback,status);
 return ()=>{disposed=true;cleanup();if(url)URL.revokeObjectURL(url);};
}
