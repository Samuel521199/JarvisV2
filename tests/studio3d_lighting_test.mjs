import assert from 'node:assert/strict';
import {keyLightOffset} from '../apps/workbench/studio3d-lighting.js';
assert.deepEqual(keyLightOffset(0,2),[-1,2.4,1.6]);
const origin=keyLightOffset(0,2),opposite=keyLightOffset(180,2);
assert.ok(Math.abs(origin[0]+opposite[0])<1e-12);
assert.ok(Math.abs(origin[2]+opposite[2])<1e-12);
assert.equal(opposite[1],origin[1]);
for(const angle of [-180,-75,-1,0,30,53.25,90,180]){
 const p=keyLightOffset(angle,2);
 assert.ok(Math.abs(Math.hypot(p[0],p[2])-Math.hypot(origin[0],origin[2]))<1e-12);
 assert.equal(p[1],2.4);
}
for(const angle of [-181,181,NaN,Infinity,'90',true])assert.throws(()=>keyLightOffset(angle,1));
for(const span of [0,-1,NaN,Infinity,'1',true])assert.throws(()=>keyLightOffset(0,span));
console.log('PASS: default placement, opposite-facing direction, height/radius preservation and invalid-input rejection');
