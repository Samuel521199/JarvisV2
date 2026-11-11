// Reuse the same authenticated viewer in Jarvis pages and content tools.
export function mountModel(container,{asset,version='original',title='三维模型'}={}){
 const valid=x=>typeof x==='string'&&/^[a-z0-9][a-z0-9-]{0,63}$/.test(x);
 if(!valid(asset)||!valid(version))throw Error('Invalid library asset or version');
 const frame=document.createElement('iframe');frame.src='/model-library/view/'+asset+'/'+version+'#embed';frame.title=title;frame.loading='lazy';frame.style.cssText='width:100%;height:420px;border:0;border-radius:12px';container.append(frame);return frame;
}
