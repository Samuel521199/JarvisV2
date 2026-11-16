import {el,button,post} from './ui.js';
import {captureVoice} from './speech-recorder.js';

const id=()=> 'speech-'+crypto.randomUUID();
const wait=()=>new Promise(resolve=>setTimeout(resolve,200));
export function speechInput(parent,{scope,onRecognized,onRecording=()=>{},onError}){
 let disposed=false,generation=0,active=null,warm=null;
 const note=el('p','本机识别准备中；录音停止后自动转写，确认后才提交。','note');note.setAttribute('role','status');
 const language=el('select');for(const [value,name] of [['auto','中文 / English / 混说'],['en','English'],['zh','中文']])language.add(new Option(name,value));language.setAttribute('aria-label','识别语言提示');
 parent.append(language,note);
 async function poll(ident,epoch){
  const deadline=Date.now()+120000;
  while(!disposed&&epoch===generation&&Date.now()<deadline){
   const state=await post('/api/speech',{action:'status'});if(disposed||epoch!==generation)return null;
   const job=state.jobs.find(j=>j.id===ident);
   if(job?.state==='SUCCEEDED')return job.result;
   if(job&&!['QUEUED','RUNNING'].includes(job.state))throw Error('语音未完成：'+(job.error||job.state));
   await wait();
  }
  if(!disposed&&epoch===generation)throw Error('转写等待超时；请刷新核对，未自动重试。');return null;
 }
 async function cancel(){const previous=active;active=null;if(previous)await post('/api/speech',{action:'cancel',id:previous}).catch(()=>{});}
 const cleanup=captureVoice(parent,{onError,onRecording:async audio=>{
  generation++;const epoch=generation;await cancel();if(disposed||epoch!==generation)return;
  onRecording(audio);onRecognized(null,null);
  if(!audio)return;
  try{
   const audioId='audio-'+crypto.randomUUID().replaceAll('-','');note.textContent='正在本机识别；首次加载可能需要数秒。';
   await post('/api/speech',{action:'record',id:audioId,audio,...scope});if(disposed||epoch!==generation)return;
   active=id();const ident=active;await post('/api/speech',{action:'transcribe',id:ident,audio_id:audioId,language:language.value,...scope});
   const result=await poll(ident,epoch);if(!result||disposed||epoch!==generation)return;
   active=null;if(!result.text||result.flags?.includes('no_speech'))throw Error('未检测到可靠语音，请重新录音。');
   note.textContent='已离线转写。回听、核对文字后提交；不确定的词请修正。';onRecognized(result.text,ident);
  }catch(e){if(!disposed&&epoch===generation){note.textContent='自动识别未完成，可重录或手动确认原话。';onError(e.message);}}
 }});
 (async()=>{try{const state=await post('/api/speech',{action:'status'});if(disposed)return;if(!state.available){note.textContent='请在本地模型管理中选择语音识别默认模型；当前可录音后手动填写。';return;}warm=id();await post('/api/speech',{action:'warm',id:warm,...scope});if(disposed){await post('/api/speech',{action:'cancel',id:warm});return;}note.textContent='离线语音已接入，点击开始录音。';}catch(e){if(!disposed)note.textContent='语音准备未完成：'+e.message;}})();
 return ()=>{disposed=true;generation++;cleanup();cancel();if(warm)post('/api/speech',{action:'cancel',id:warm}).catch(()=>{});};
}

export function speechOutput(parent,onError){
 let disposed=false,current=null;const audio=el('audio');audio.controls=true;parent.append(audio);
 return {async play(source){
  if(current)await post('/api/speech',{action:'cancel',id:current}).catch(()=>{});
  audio.pause();const ident=id();current=ident;
  try{await post('/api/speech',{action:'speak',id:ident,...source});const deadline=Date.now()+45000;
   while(!disposed&&current===ident&&Date.now()<deadline){const state=await post('/api/speech',{action:'status'});if(disposed||current!==ident)return;const job=state.jobs.find(j=>j.id===ident);if(job?.state==='SUCCEEDED'){const value=await post('/api/speech',{action:'audio',id:ident});if(disposed||current!==ident)return;audio.src='data:audio/wav;base64,'+value.audio;await audio.play();return;}if(job&&!['QUEUED','RUNNING'].includes(job.state))throw Error(job.error||job.state);await wait();}
   if(!disposed&&current===ident)throw Error('朗读等待超时，未自动重试。');
  }catch(e){if(!disposed&&current===ident)onError('本机朗读未完成：'+e.message);}
 },close(){disposed=true;audio.pause();audio.removeAttribute('src');if(current)post('/api/speech',{action:'cancel',id:current}).catch(()=>{});}};
}
