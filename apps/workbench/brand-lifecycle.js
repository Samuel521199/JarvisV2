import {el,button,savePreferences} from './ui.js';
import {playSound,stopSound,setSound,soundState,unlockSound} from './brand-sound.js';
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
let active=null,entryPending=false;
const motionOff=()=>reduced.matches||document.documentElement.hasAttribute('data-brand-paused');
function signal(away=false){document.dispatchEvent(new CustomEvent('jarvis-cinema',{detail:{away}}));}
// Leaving this screen does not stop the host, discard a draft or cancel a task.
export function cinema(leave=false,{preview=false,gesture=true}={}){
  if(active||document.hidden)return false;
  const previous=document.activeElement,dialog=el('dialog',undefined,'jarvis-cinema');
  dialog.id='cinema';dialog.dataset.sequence=leave?'exit':'boot';dialog.style.setProperty('--cinema-art','url(/brand/core.png)');
  dialog.setAttribute('aria-labelledby','cinema-title');if(motionOff())dialog.dataset.reduced='';
  const grid=el('div',undefined,'cinema-grid');grid.setAttribute('aria-hidden','true');
  const header=el('header',undefined,'cinema-header'),word=el('span','JARVIS');word.append(el('small','PERSONAL INTELLIGENCE'));
  header.append(word,el('span',leave?'02 / DISASSEMBLY':'01 / ASSEMBLY','cinema-edition'));
  const center=el('div',undefined,'cinema-center'),stage=el('div',undefined,'cinema-stage'),parts=el('div',undefined,'cinema-parts');stage.setAttribute('aria-hidden','true');
  for(let i=0;i<9;i++){const part=el('span',undefined,'cinema-part cinema-part-'+i),img=el('img');img.src='/brand/core.png';img.alt='';img.draggable=false;part.append(img);parts.append(part);}
  stage.append(el('div',undefined,'cinema-ghost'),parts,el('div',undefined,'cinema-flare'));
  const copy=el('div',undefined,'cinema-copy'),title=el('h2',leave?'暂别，仍与你同在。':'我在，准备开始。');title.id='cinema-title';
  const description=el('p',preview?'视觉演示 · 不改变助手运行状态':leave?'正在离开工作台 · 后台助手继续运行':'进入你的智能工作台。','cinema-description');
  copy.append(el('p',leave?'UNTIL NEXT TIME':'ASSEMBLY SEQUENCE','cinema-kicker'),title,description);
  const progress=el('div',undefined,'cinema-progress');progress.setAttribute('aria-hidden','true');progress.append(el('span'));
  const coordinate=el('div','J / CORE','cinema-coordinate');coordinate.setAttribute('aria-hidden','true');
  const back=button('返回工作台',()=>{close();cinema();},'cinema-return');back.hidden=true;
  center.append(coordinate,stage,copy,progress,back);
  const controls=el('footer',undefined,'cinema-controls'),sound=button('',async()=>{
    const old=soundState(),value=!(old.enabled&&old.unlocked);setSound(value);
    if(value)await unlockSound();await savePreferences({sound:value});updateSound();
    if(value&&!record.ended)await playSound(leave?'exit':'boot',{gesture:true});
  }),hint=el('span','机械音效可选 · Esc 跳过'),skip=button('跳过动画',finish);
  const updateSound=()=>{const s=soundState();sound.textContent=!s.enabled?'音效：关':s.unlocked?'音效：开':'音效：点击解锁';sound.setAttribute('aria-pressed',String(s.enabled&&s.unlocked));};
  controls.append(sound,hint,skip);dialog.append(grid,header,center,controls);
  const record={dialog,finish,close,ended:false,timer:0};active=record;
  function close(){clearTimeout(record.timer);stopSound();dialog.close();dialog.remove();document.removeEventListener('jarvis-sound',updateSound);if(active===record)active=null;document.documentElement.removeAttribute('data-brand-cinema');signal(false);if(previous?.isConnected)previous.focus({preventScroll:true});}
  function finish(){clearTimeout(record.timer);stopSound();if(!leave||preview){close();return;}record.ended=true;dialog.dataset.ended='';title.textContent='工作台已离开';description.textContent='后台助手继续运行；返回可继续当前会话。';skip.hidden=true;hint.textContent='返回可继续当前会话';back.hidden=false;back.focus();signal(true);}
  dialog.addEventListener('cancel',e=>{e.preventDefault();if(record.ended)close();else finish();});
  document.body.append(dialog);dialog.showModal();document.documentElement.setAttribute('data-brand-cinema','');signal(leave&&!preview);skip.focus();
  document.addEventListener('jarvis-sound',updateSound);updateSound();
  if(!motionOff())void playSound(leave?'exit':'boot',{gesture});
  record.timer=setTimeout(finish,motionOff()?250:leave?3300:3900);return true;
}
export function enterCinema(){entryPending=true;if(!document.hidden){entryPending=false;cinema(false,{gesture:false});}}
document.addEventListener('visibilitychange',()=>{if(document.hidden){if(active&&!active.ended)active.finish();}else if(entryPending)enterCinema();});
function adaptMotion(){if(motionOff()&&active&&!active.ended)active.finish();}
reduced.addEventListener('change',adaptMotion);document.addEventListener('jarvis-preferences',adaptMotion);
window.addEventListener('pagehide',()=>{entryPending=false;active?.close();});
