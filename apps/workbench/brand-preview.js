import {$,el,button,get,savePreferences} from './ui.js';
import {brandState,cinema,setSound,unlockSound,soundState} from './brand.js';
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const copy={idle:['待命 / STANDBY','能量稳定，等你开口。'],thinking:['思考 / PROCESSING','扫描推进 · 分区响应 · 思路汇聚。'],sleep:['休眠 / SLEEP','暂时休息，等你唤醒。'],offline:['连接中断 / OFFLINE','失去连接，等待本机服务恢复。']};
for(const [id,label] of [['idle','待命'],['thinking','思考'],['sleep','休眠'],['offline','连接中断']]){
 const b=button(label,()=>{brandState(id);$('preview-readout').textContent=copy[id][0];$('preview-status').textContent=copy[id][1];for(const n of $('preview-states').children)n.setAttribute('aria-pressed',String(n===b));});b.setAttribute('aria-pressed',String(id==='idle'));$('preview-states').append(b);
}
for(const size of [16,24,32,48,64]){const n=el('div'),img=el('img');img.src='/brand/icon.png';img.width=size;img.height=size;img.alt=size+' 像素';n.append(img,el('span',String(size)));$('icon-sizes').append(n);}
function motionLabel(){const paused=document.documentElement.hasAttribute('data-brand-paused');$('pause-motion').disabled=reduced.matches;$('pause-motion').textContent=reduced.matches?'系统已减弱动效':paused?'播放动效':'暂停动效';$('pause-motion').setAttribute('aria-pressed',String(paused||reduced.matches));}
$('pause-motion').onclick=()=>{document.documentElement.toggleAttribute('data-brand-paused');document.dispatchEvent(new Event('jarvis-preferences'));motionLabel();};
// Preview pause is local to this page; it does not overwrite the user's preference.
$('boot-preview').onclick=()=>cinema(false,{preview:true});$('exit-preview').onclick=()=>cinema(true,{preview:true});
function soundLabel(){const s=soundState();$('sound-toggle').textContent=!s.enabled?'音效：关':s.unlocked?'音效：开':'音效：点击解锁';$('sound-toggle').setAttribute('aria-pressed',String(s.enabled&&s.unlocked));}
$('sound-toggle').onclick=async()=>{const s=soundState(),value=!(s.enabled&&s.unlocked);setSound(value);if(value)await unlockSound();try{await savePreferences({sound:value});}catch(e){$('preview-error').textContent=e.message;}soundLabel();};
document.addEventListener('jarvis-sound',soundLabel);reduced.addEventListener('change',motionLabel);
get('/api/snapshot').then(s=>{setSound(!!s.settings.ui.sound);document.documentElement.toggleAttribute('data-brand-paused',!!s.settings.ui.motion_off);motionLabel();}).catch(e=>{$('preview-error').textContent=e.message;});motionLabel();soundLabel();
