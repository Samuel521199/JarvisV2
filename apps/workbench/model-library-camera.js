export function validCamera(v){return !!v&&['position','target','up'].every(k=>Array.isArray(v[k])&&v[k].length===3&&v[k].every(x=>Number.isFinite(x)&&Math.abs(x)<=1e6))&&Number.isFinite(v.fov)&&v.fov>=10&&v.fov<=100&&Math.hypot(...v.up)>.1&&Math.hypot(...v.position.map((x,i)=>x-v.target[i]))>1e-6;}
export function connectLibraryCamera({asset,version,sha256,camera,controls,state,apply}){
 const token=new URLSearchParams(location.hash.slice(1)).get('compare'),embedded=!!token&&/^[a-f0-9]{32}$/.test(token)&&parent!==window;let applying=false,queued=false;
 const snapshot=()=>({position:camera.position.toArray(),target:controls.target.toArray(),up:camera.up.toArray(),fov:camera.fov});
 function set(v){if(!validCamera(v))return;applying=true;const damping=controls.enableDamping;controls.enableDamping=false;controls.update();camera.position.fromArray(v.position);controls.target.fromArray(v.target);camera.up.fromArray(v.up);camera.fov=v.fov;camera.updateProjectionMatrix();controls.update();controls.enableDamping=damping;state.libraryCamera=snapshot();applying=false;}
 const key='jarvis.library.camera.'+asset;
 if(!embedded){try{const saved=JSON.parse(sessionStorage.getItem(key));if(validCamera(saved))set(saved);}catch{}}
 function send(kind){const view=snapshot();state.libraryCamera=view;if(!embedded){try{sessionStorage.setItem(key,JSON.stringify(view));}catch{}}else parent.postMessage({type:'jarvis-library-view',token,asset,version,sha256,kind,camera:view},location.origin);}
 controls.addEventListener('change',()=>{if(applying||queued)return;queued=true;requestAnimationFrame(()=>{queued=false;send('camera');});});
 if(embedded){controls.enableDamping=false;const lod=document.getElementById('lod');if(lod){lod.disabled=true;lod.title='请使用对比页顶部的版本选择';}window.addEventListener('message',e=>{const v=e.data;if(e.origin!==location.origin||e.source!==parent||v?.type!=='jarvis-library-command'||v.token!==token||v.asset!==asset||v.sha256!==sha256)return;if(v.camera)set(v.camera);if(v.mode&&['pbr','wire','clay','base','normal','roughness','metalness'].includes(v.mode))apply({mode:v.mode});});send('ready');}
 state.libraryCamera=snapshot();return {set,snapshot};
}
