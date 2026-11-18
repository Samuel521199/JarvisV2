import {el,button} from './ui.js';

function microphoneError(error){
 const messages={
  NotAllowedError:'麦克风权限未开启，请允许 Jarvis 使用麦克风后重试。',
  NotFoundError:'找不到可用麦克风，请连接设备后重试。',
  NotReadableError:'麦克风无法使用，请检查设备是否被占用。'
 };
 return messages[error.name]||error.message||'无法启动麦克风。';
}

export function microphone({onStart=()=>{},onRecording,onError}){
 let releaseMic,stream,context,processor,source,timer;
 let chunks=[],samples=0,opening=false,recording=false,disposed=false;

 async function start(){
  if(disposed||opening||recording)return;
  opening=true;
  try{
   if(!navigator.mediaDevices?.getUserMedia)throw Error('当前页面无法使用麦克风，请在 Jarvis 工作台或 Edge 中打开。');
   if(!navigator.locks)throw Error('当前浏览器无法协调麦克风，请使用 Edge 或 Chrome。');
   // Resume while the microphone button's user activation is still available.
   context=new AudioContext();
   const resume=context.resume();
   resume.catch(()=>{});
   await new Promise((resolve,reject)=>navigator.locks.request('jarvis-microphone',{ifAvailable:true},lock=>{
    if(!lock){reject(Error('另一个 Jarvis 窗口正在录音。'));return;}
    if(disposed){resolve();return;}
    return new Promise(release=>{releaseMic=release;resolve();});
   }).catch(reject));
   if(disposed)return;
   const input=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true},video:false});
   if(disposed){input.getTracks().forEach(track=>track.stop());return;}
   stream=input;
   for(const track of input.getAudioTracks()){
    track.addEventListener('ended',()=>{
     if(stream!==input)return;
     cleanup();onError('麦克风已断开，请连接后重试。');
    },{once:true});
   }
   timer=setTimeout(()=>{
    disposed=true;cleanup();onError('麦克风已连接，但音频无法启动，请重新点击麦克风。');
   },3000);
   await resume;
   clearTimeout(timer);
   if(disposed)return;
   source=context.createMediaStreamSource(stream);
   processor=context.createScriptProcessor(4096,1,1);
   chunks=[];samples=0;
   processor.onaudioprocess=event=>{
    const channel=event.inputBuffer.getChannelData(0);
    chunks.push(new Float32Array(channel));
    samples+=channel.length;
   };
   source.connect(processor);processor.connect(context.destination);
   recording=true;
   timer=setTimeout(stop,60000);
   onStart();
  }catch(error){
   cleanup();
   if(!disposed)onError(microphoneError(error));
  }finally{opening=false;}
 }

 function cleanup(){
  clearTimeout(timer);recording=false;
  if(processor){processor.disconnect();processor.onaudioprocess=null;processor=null;}
  source?.disconnect();source=null;
  stream?.getTracks().forEach(track=>track.stop());stream=null;
  const current=context;context=null;
  if(current&&current.state!=='closed')void current.close().catch(()=>{});
  releaseMic?.();releaseMic=null;
 }

 function stop(){
  if(!recording)return;
  const rate=context.sampleRate;
  cleanup();
  const full=new Float32Array(samples);
  let offset=0;
  for(const part of chunks){full.set(part,offset);offset+=part.length;}
  chunks=[];
  const count=Math.min(960000,Math.floor(samples*16000/rate));
  if(count<1600){onError('录音太短或没有收到声音，请再说一次。');return;}
  const data=new ArrayBuffer(44+count*2),view=new DataView(data);
  const put=(at,text)=>[...text].forEach((letter,i)=>view.setUint8(at+i,letter.charCodeAt(0)));
  put(0,'RIFF');view.setUint32(4,36+count*2,true);put(8,'WAVEfmt ');view.setUint32(16,16,true);
  view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);
  view.setUint16(32,2,true);view.setUint16(34,16,true);put(36,'data');view.setUint32(40,count*2,true);
  for(let i=0;i<count;i++){
   const value=full[Math.min(samples-1,Math.floor(i*rate/16000))];
   view.setInt16(44+i*2,Math.max(-1,Math.min(1,value))*32767,true);
  }
  onRecording(new Uint8Array(data));
 }

 return {start,stop,close(){disposed=true;cleanup();chunks=[];}};
}

export function audioBase64(bytes){
 let binary='';
 for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
 return btoa(binary);
}

// English practice keeps the existing playback and explicit recording controls.
export function captureVoice(parent,{onRecording,onError}){
 let url;
 const status=el('p','录音保存在本机，请核对识别文字后再提交。','note');
 const playback=el('audio');playback.controls=true;
 const capture=microphone({
  onStart(){
   status.textContent='正在录音，最多60秒；停止后可回听并确认转写。';
   onRecording(null);
  },
  onRecording(bytes){
   if(url)URL.revokeObjectURL(url);
   url=URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));playback.src=url;
   status.textContent='录音已准备，可回听并核对上方识别结果。';
   onRecording(audioBase64(bytes));
  },
  onError
 });
 parent.append(button('开始录音',capture.start),button('停止录音',capture.stop),playback,status);
 return ()=>{capture.close();if(url)URL.revokeObjectURL(url);};
}
