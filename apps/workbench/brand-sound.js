// Bounded local synthesis; a real gesture is required to unlock audio.
let enabled=false,context=null,generation=0;
const sources=new Set();
export function soundState(){return {enabled,unlocked:context?.state==='running'};}
export function stopSound(){generation++;for(const n of sources){try{n.stop();}catch{}}sources.clear();}
export function setSound(value){enabled=!!value;if(!enabled)stopSound();document.dispatchEvent(new Event('jarvis-sound'));}
export async function unlockSound(){if(!enabled)return false;try{const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return false;context ||= new Audio();await context.resume();document.dispatchEvent(new Event('jarvis-sound'));return context.state==='running';}catch{return false;}}
function note(delay,duration,from,to,volume=.025,type='sine'){
 const o=context.createOscillator(),g=context.createGain(),at=context.currentTime+delay;o.type=type;o.frequency.setValueAtTime(from,at);o.frequency.exponentialRampToValueAtTime(to,at+duration);g.gain.setValueAtTime(0,at);g.gain.linearRampToValueAtTime(volume,at+.015);g.gain.exponentialRampToValueAtTime(.0001,at+duration);o.connect(g);g.connect(context.destination);sources.add(o);o.onended=()=>{o.disconnect();g.disconnect();sources.delete(o);};o.start(at);o.stop(at+duration+.03);
}
export async function playSound(kind,{gesture=false}={}){
 stopSound();const ticket=generation;if(!enabled)return false;
 if(context?.state!=='running'&&(!gesture||!await unlockSound()))return false;
 if(ticket!==generation||!enabled||document.hidden)return false;
 const boot=kind==='boot';note(0,1.2,boot?65:420,boot?190:65,.025);
 for(let i=0;i<9;i++)note(.12+i*.17,.11,boot?440+i*70:950-i*65,110,.022,'triangle');
 note(1.85,.5,boot?100:240,boot?52:38,.035);note(2.08,.65,boot?660:300,boot?990:45,.014);return true;
}
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopSound();});
window.addEventListener('pagehide',()=>{stopSound();context?.close();context=null;});
