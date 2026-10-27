import {el} from './ui.js';
import {brandLabels} from './brand-state.js';
export {cinema,enterCinema} from './brand-lifecycle.js';
export {setSound,unlockSound,soundState} from './brand-sound.js';
let current='idle';
const reduced=matchMedia('(prefers-reduced-motion: reduce)'),logos=new Set();
const observer=new IntersectionObserver(entries=>{for(const e of entries){e.target.dataset.inView=String(e.isIntersecting);if(!e.isIntersecting)e.target.reset();}});
class Logo extends HTMLElement{
 connectedCallback(){
  this.abort?.abort();this.abort=new AbortController();logos.add(this);
  if(!this.querySelector('.jarvis-surface')){
   const layer=(name,art=true)=>{const n=el('span',undefined,'jarvis-'+name);if(art){const img=el('img');img.src='/brand/core.png';img.alt='';img.draggable=false;n.append(img);}return n;};
   const floating=layer('float',false),surface=layer('surface',false),segments=layer('segments',false),meter=layer('meter',false);meter.setAttribute('aria-hidden','true');
   for(let i=0;i<4;i++){const n=layer('segment');n.style.setProperty('--segment',i);segments.append(n);}
   for(let i=0;i<5;i++){const n=el('i');n.style.setProperty('--bar',i);meter.append(n);}
   surface.append(layer('idle-halo'),layer('edge'),layer('echo'),layer('core'),segments,layer('scan',false),layer('star'),layer('glint'),layer('sheen',false));floating.append(surface);this.replaceChildren(floating,meter);
  }
  this.style.setProperty('--jarvis-art','url(/brand/core.png)');this.setAttribute('role','img');this.setAttribute('interactive','');this.setState(current);this.reset();
  const target=this.closest('a,button')||this;if(target===this)this.tabIndex=0;else this.removeAttribute('tabindex');const options={signal:this.abort.signal,passive:true};
  const move=e=>{if(!this.canReact())return;this.point=[e.clientX,e.clientY];if(this.frame)return;this.frame=requestAnimationFrame(()=>{this.frame=0;if(!this.canReact())return;const r=this.getBoundingClientRect();if(!r.width||!r.height)return;const x=Math.max(-1,Math.min(1,(this.point[0]-r.left)/r.width*2-1)),y=Math.max(-1,Math.min(1,(this.point[1]-r.top)/r.height*2-1));this.engage(-y*8,x*9);});};
  target.addEventListener('pointerenter',move,options);target.addEventListener('pointermove',move,options);
  for(const event of ['pointerleave','pointercancel','blur'])target.addEventListener(event,()=>this.reset(),options);
  target.addEventListener('focus',()=>{if(this.canReact())this.engage(-3,3);},options);
  target.addEventListener('pointerdown',e=>{if(e.pointerType==='touch'&&this.canReact())this.engage(-3,3);},options);target.addEventListener('pointerup',e=>{if(e.pointerType==='touch')this.reset();},options);observer.observe(this);
 }
 canReact(){return this.isConnected&&!reduced.matches&&!document.hidden&&this.dataset.inView!=='false'&&!document.documentElement.hasAttribute('data-brand-paused')&&!document.documentElement.hasAttribute('data-brand-cinema')&&['idle','thinking'].includes(this.dataset.state);}
 engage(x,y){this.dataset.engaged='true';this.style.setProperty('--tilt-x',x.toFixed(2)+'deg');this.style.setProperty('--tilt-y',y.toFixed(2)+'deg');}
 reset(){if(this.frame)cancelAnimationFrame(this.frame);this.frame=0;delete this.dataset.engaged;this.style.setProperty('--tilt-x','0deg');this.style.setProperty('--tilt-y','0deg');}
 setState(state){this.dataset.state=state;this.setAttribute('aria-label','Jarvis · '+brandLabels[state]);if(!this.canReact())this.reset();}
 disconnectedCallback(){this.reset();this.abort?.abort();observer.unobserve(this);logos.delete(this);}
}
customElements.define('jarvis-logo',Logo);
export function brandState(state){if(!Object.hasOwn(brandLabels,state))return;current=state;for(const n of logos)n.setState(state);}
function resetMotion(){for(const n of logos)if(!n.canReact())n.reset();}
document.addEventListener('visibilitychange',()=>{document.documentElement.toggleAttribute('data-brand-hidden',document.hidden);resetMotion();});
document.addEventListener('jarvis-preferences',resetMotion);document.addEventListener('jarvis-cinema',resetMotion);reduced.addEventListener('change',resetMotion);
document.documentElement.toggleAttribute('data-brand-hidden',document.hidden);
