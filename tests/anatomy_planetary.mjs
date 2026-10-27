import assert from 'node:assert/strict';
import {validatePlanetary,planetaryState,externalProfile,internalSector,toothHalfAngle} from '../modules/skills/anatomy/planetary-model.mjs';
const close=(a,b,t=1e-8)=>assert.ok(Math.abs(a-b)<t,`${a} != ${b}`);
for(const [mode,expected] of [['ring-fixed',[60,0,120/7,-40]],['sun-fixed',[0,84,60,140]],['carrier-fixed',[60,-24,0,-80]]]){
 const q=planetaryState({mode},0,60);['sun','ring','carrier','planet'].forEach((k,i)=>close(q.rates[k],expected[i]));
}
const phase=x=>Math.atan2(Math.sin(x-Math.PI),Math.cos(x-Math.PI));let cases=0,worst=0;
for(let S=18;S<=48;S++)for(let P=18;P<=36;P++){
 const R=S+2*P,valid=(S+R)%3===0;
 if(!valid){assert.throws(()=>validatePlanetary({sun_teeth:S,planet_teeth:P}));continue;}
 for(const mode of ['ring-fixed','sun-fixed','carrier-fixed'])for(let angle=-720;angle<=720;angle+=15){
 const q=planetaryState({sun_teeth:S,planet_teeth:P,mode},angle,60);
 // Independent pitch-point velocity and angular tooth phase checks.
 close(q.rates.sun*S,q.rates.carrier*(S+P)-q.rates.planet*P);
 close(q.rates.ring*R,q.rates.carrier*(S+P)+q.rates.planet*P);
 for(const p of q.planets){close(Math.hypot(p.x,p.y),S+P);
 const external=phase(S*(p.orbital-q.sunAngle)+P*(p.orbital+Math.PI-p.angle));
 const internal=phase(R*(p.orbital-q.ringAngle)-P*(p.orbital-p.angle));
 worst=Math.max(worst,Math.abs(external),Math.abs(internal));close(external,0);close(internal,0);
 }cases++;
 }
}
for(const value of [{sun_teeth:17},{planet_teeth:37},{sun_teeth:19,planet_teeth:18},{mode:'free'},{sun_teeth:NaN}])assert.throws(()=>validatePlanetary(value));
assert.throws(()=>planetaryState({},Infinity));
for(const n of [18,19,24,36,48]){
 const ext=externalProfile(n),rs=ext.map(p=>Math.hypot(...p));close(Math.min(...rs),n-2.5);close(Math.max(...rs),n+2);
 close(toothHalfAngle(n,2,n),Math.PI/(2*n));assert.ok(ext.every(p=>p.every(Number.isFinite)));
}
assert.ok(internalSector(60).every(p=>p.every(Number.isFinite)));
console.log(JSON.stringify({status:'passed',motion_cases:cases,planet_phase_checks:cases*6,worst_phase_radians:worst,known_examples:3,tooth_profile_bounds:true}));
