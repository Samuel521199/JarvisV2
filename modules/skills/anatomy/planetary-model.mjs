// Jarvis ideal simple planetary model; lengths mm, phase radians, rates rpm.
export const MODES = Object.freeze(['ring-fixed','sun-fixed','carrier-fixed']);
export function validatePlanetary(config={}) {
 const sun=config.sun_teeth??24, planet=config.planet_teeth??18, mode=config.mode??'ring-fixed';
 if(!Number.isInteger(sun)||!Number.isInteger(planet)||sun<18||sun>48||planet<18||planet>36||!MODES.includes(mode))throw Error('invalid planetary configuration');
 const ring=sun+2*planet;
 if((sun+ring)%3!==0)throw Error('three equally spaced planets require (sun+ring) divisible by 3');
 if((sun+planet)*Math.sin(Math.PI/3)<=planet+2)throw Error('adjacent planets collide');
 return {sun_teeth:sun,planet_teeth:planet,ring_teeth:ring,mode,module:2,pressure_angle:20,planets:3};
}
export function planetaryState(config,inputAngle,inputRpm=60) {
 const q=validatePlanetary(config), S=q.sun_teeth,R=q.ring_teeth,P=q.planet_teeth;
 if(!Number.isFinite(inputAngle)||!Number.isFinite(inputRpm)||Math.abs(inputAngle)>1e8||Math.abs(inputRpm)>120)throw Error('invalid input motion');
 let s,c,r,output;
 if(q.mode==='ring-fixed'){s=1;r=0;c=S/(S+R);output='carrier';}
 else if(q.mode==='sun-fixed'){s=0;c=1;r=(S+R)/R;output='ring';}
 else {s=1;c=0;r=-S/R;output='ring';}
 const a=inputAngle*Math.PI/180,spin=c-S/P*(s-c),orbit=(S+P)*q.module/2;
 const ringPhase=(P%2)*Math.PI/R;
 const planets=Array.from({length:3},(_,i)=>{const orbital=c*a+i*2*Math.PI/3;return {orbital,angle:(S+P)/P*orbital+Math.PI-Math.PI/P-S/P*s*a,x:orbit*Math.cos(orbital),y:orbit*Math.sin(orbital)};});
 return {...q,sunAngle:s*a,ringAngle:r*a+ringPhase,carrierAngle:c*a,planets,orbit,
  rates:{sun:s*inputRpm,ring:r*inputRpm,carrier:c*inputRpm,planet:spin*inputRpm},
  output,ratio:1/(output==='carrier'?c:r),willisResidual:(S*s+R*r-(S+R)*c)*inputRpm};
}
const inv = alpha=>Math.tan(alpha)-alpha;
export function toothHalfAngle(teeth,module,radius,internal=false) {
 const pitch=teeth*module/2,base=pitch*Math.cos(20*Math.PI/180);
 const delta=inv(Math.acos(Math.min(1,base/radius)))-inv(20*Math.PI/180);
 return Math.PI/(2*teeth)+(internal?delta:-delta);
}
export function externalProfile(teeth,module=2) {
 const pitch=teeth*module/2,root=pitch-1.25*module,tip=pitch+module,base=pitch*Math.cos(20*Math.PI/180),start=Math.max(root,base);
 const points=[],put=(r,a)=>points.push([r*Math.cos(a),r*Math.sin(a)]);
 for(let k=0;k<teeth;k++){
  const a=k*2*Math.PI/teeth,h=toothHalfAngle(teeth,module,start);
  put(root,a-Math.PI/teeth);put(root,a-h);put(start,a-h);
  for(let j=1;j<=5;j++){const r=start+(tip-start)*j/5;put(r,a-toothHalfAngle(teeth,module,r));}
  const ht=toothHalfAngle(teeth,module,tip);
  for(let j=1;j<=3;j++)put(tip,a-ht+2*ht*j/3);
  for(let j=4;j>=0;j--){const r=start+(tip-start)*j/5;put(r,a+toothHalfAngle(teeth,module,r));}
  put(root,a+h);put(root,a+Math.PI/teeth);
 }
 return points;
}
export function internalSector(teeth,module=2) {
 const pitch=teeth*module/2,tip=pitch-module,root=pitch+1.25*module,outer=root+7,half=Math.PI/teeth;
 // Explicit drawing relief avoids chord-sampling penetration at internal contacts.
 const points=[],put=(r,a)=>{const plotted=r<=root+1e-9?r+0.06:r;points.push([plotted*Math.cos(a),plotted*Math.sin(a)]);};
 for(let j=0;j<=4;j++)put(outer,-half+2*half*j/4);
 put(root,half);put(root,toothHalfAngle(teeth,module,root,true));
 for(let j=4;j>=0;j--){const r=tip+(root-tip)*j/5;put(r,toothHalfAngle(teeth,module,r,true));}
 const h=toothHalfAngle(teeth,module,tip,true);
 for(let j=1;j<=3;j++)put(tip,h-2*h*j/3);
 for(let j=1;j<=5;j++){const r=tip+(root-tip)*j/5;put(r,-toothHalfAngle(teeth,module,r,true));}
 put(root,-half);return points;
}
