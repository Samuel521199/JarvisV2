export {captureVoice as voicePractice} from './speech-recorder.js';

export function speakEnglish(text,onError){
 if(!window.speechSynthesis){onError('浏览器没有朗读能力。');return;}
 const voices=speechSynthesis.getVoices().filter(v=>v.localService&&/^en[-_]/i.test(v.lang));
 if(!voices.length){onError('尚未发现本机英文音色，请稍后重试；可在系统语音设置检查。');return;}
 speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(text);utterance.voice=voices[0];utterance.lang=voices[0].lang;utterance.rate=.85;utterance.onerror=()=>onError('朗读未完成，请检查系统音频输出。');speechSynthesis.speak(utterance);
}
