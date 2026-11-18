import {el,button,post} from './ui.js';
import {captureVoice} from './speech-recorder.js';

const id=()=> 'speech-'+crypto.randomUUID();
const wait=()=>new Promise(resolve=>setTimeout(resolve,200));
const recognitionErrors={
 speech_disabled:'本机语音识别已关闭，可在「设置 → 本地模型」检查语音设置。',
 speech_model_missing:'请在「设置 → 本地模型」选择语音识别模型。',
 model_runtime_missing:'离线语音组件缺失或已变更，请在「设置 → 本地模型」检查。',
 model_integrity:'语音模型文件校验失败，请在「设置 → 本地模型」修复。',
 speech_busy:'正在处理另一段语音，请稍后再试。',
 speech_cancelled:'语音识别已取消。'
};

export function speechTranscriber(scope){
 let active=null,generation=0;
 function cancel(){
  generation++;
  const previous=active;active=null;
  if(previous)void post('/api/speech',{action:'cancel',id:previous}).catch(()=>{});
 }
 return {
  cancel,
  async transcribe(audio,language='auto'){
   cancel();
   const current=generation,audioId='audio-'+crypto.randomUUID().replaceAll('-','');
   const ident=id();
   try{
    await post('/api/speech',{action:'record',id:audioId,audio,...scope});
    if(current!==generation)return null;
    active=ident;
    await post('/api/speech',{action:'transcribe',id:ident,audio_id:audioId,language,...scope});
    if(current!==generation){
     await post('/api/speech',{action:'cancel',id:ident}).catch(()=>{});
     return null;
    }
    const deadline=Date.now()+120000;
    while(current===generation&&Date.now()<deadline){
     const state=await post('/api/speech',{action:'status'});
     if(current!==generation)return null;
     const job=state.jobs.find(item=>item.id===ident);
     if(job?.state==='SUCCEEDED'){
      if(!job.result?.text||job.result.flags?.includes('no_speech'))throw Error('没有听清，请确认麦克风后再说一次。');
      return {id:ident,text:job.result.text};
     }
     if(job&&!['QUEUED','RUNNING'].includes(job.state)){
      throw Error(recognitionErrors[job.error]||'本机语音识别未完成（'+(job.error||job.state)+'）。');
     }
     await wait();
    }
    if(current===generation)throw Error('本机语音识别超时，请稍后重试。');
    return null;
   }catch(error){
    if(current!==generation)return null;
    cancel();
    if(recognitionErrors[error.code])throw Error(recognitionErrors[error.code]);
    throw error;
   }finally{if(active===ident)active=null;}
  }
 };
}

export function speechInput(parent,{scope,onRecognized,onRecording=()=>{},onError}){
 let disposed=false,warm=null;
 const input=speechTranscriber(scope);
 const note=el('p','本机识别准备中；录音停止后自动转写，确认后才提交。','note');note.setAttribute('role','status');
 const language=el('select');for(const [value,label] of [['auto','中文 / English / 混说'],['en','English'],['zh','中文']])language.add(new Option(label,value));language.setAttribute('aria-label','识别语言提示');
 parent.append(language,note);
 const cleanup=captureVoice(parent,{onError,onRecording:async audio=>{
  input.cancel();onRecording(audio);onRecognized(null,null);
  if(!audio)return;
  try{
   note.textContent='正在本机识别；首次加载可能需要数秒。';
   const result=await input.transcribe(audio,language.value);
   if(!result||disposed)return;
   note.textContent='已离线转写。回听、核对文字后提交；不确定的词请修正。';onRecognized(result.text,result.id);
  }catch(error){if(!disposed){note.textContent='自动识别未完成，可重录或手动确认原话。';onError(error.message);}}
 }});
 (async()=>{try{
  const state=await post('/api/speech',{action:'status'});if(disposed)return;
  if(!state.available){note.textContent='请在本地模型管理中选择语音识别默认模型；当前可录音后手动填写。';return;}
  warm=id();await post('/api/speech',{action:'warm',id:warm,...scope});
  if(disposed){await post('/api/speech',{action:'cancel',id:warm});return;}
  note.textContent='离线语音已接入，点击开始录音。';
 }catch(error){if(!disposed)note.textContent='语音准备未完成：'+error.message;}})();
 return ()=>{disposed=true;cleanup();input.cancel();if(warm)void post('/api/speech',{action:'cancel',id:warm}).catch(()=>{});};
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
