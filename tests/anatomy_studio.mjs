import assert from 'node:assert/strict';
import fs from 'node:fs';
import {validateScene,engineCylinder,motorState,waveState,sceneState,assemblyState} from '../modules/skills/anatomy/studio-model.mjs';
const schema=JSON.parse(fs.readFileSync(new URL('../modules/skills/anatomy/scene-schema.json',import.meta.url))),presets=JSON.parse(fs.readFileSync(new URL('../modules/skills/anatomy/studio-presets.json',import.meta.url)));
for(const p of Object.values(presets))assert.deepEqual(validateScene(validateScene(p,schema),schema),validateScene(p,schema));
let cylinders=0,motors=0,waves=0,couplings=0;
for(const crank_mm of [20,40,70])for(const rod_ratio of [2.5,3,5])for(const count of [1,2,4,6,8])for(let angle=0;angle<720;angle+=3)for(let i=0;i<count;i++){
 const p={crank_mm,rod_ratio,cylinders:count},s=engineCylinder(p,angle,i);assert.ok(Math.abs(Math.hypot(s.pinX,s.piston-s.pinZ)-crank_mm*rod_ratio)<1e-8);assert.ok(s.displacement>=-1e-8&&s.displacement<=2*crank_mm+1e-8);assert.equal(s.intake,s.phase<180);assert.equal(s.exhaust,s.phase>=540);assert.equal(s.flame>0,s.phase>360&&s.phase<540);assert.ok(!s.spark||s.phase>=360&&s.phase<374);cylinders++;
}
for(const voltage of [0,3,12,24])for(const resistance of [1,4,20])for(const constant of [.02,.08,.3])for(const load of [0,.04,.2])for(const switch_closed of [false,true]){
 const p={voltage,resistance,constant,load,switch_closed},s=motorState(p);assert.ok(s.rpm>=0&&s.current>=-1e-9);assert.ok(Math.abs(s.inputPower-s.copperLoss-s.loadPower-s.frictionPower)<1e-8);if(s.omega>0)assert.ok(Math.abs(s.torque-load-.0002*s.omega)<1e-9);if(!switch_closed)assert.equal(s.rpm+s.current,0);motors++;
}
const motor=motorState({voltage:12,resistance:4,constant:.08,load:.04,switch_closed:true});assert.ok(Math.abs(motor.omega-111.11111111111111)<1e-8);assert.ok(Math.abs(motor.current-.7777777777777778)<1e-8);
for(const amplitude of [0,.01,.04])for(const wavelength of [.5,1,4])for(const depth of [.2,.5,2])for(const interference of [true,false])for(let t=0;t<3;t+=.17)for(const x of [0,.17,.8,2]){
 const p={amplitude,wavelength,depth,interference},s=waveState(p,x,t);assert.ok(Math.abs(s.height)<=amplitude+1e-9);assert.ok(Math.abs(s.omega**2-9.81*s.k*Math.tanh(s.k*depth))<1e-8);if(interference)assert.ok(Math.abs(waveState(p,wavelength/4,t).height)<1e-9);waves++;
}
const composed=validateScene(presets['electric-water'],schema);
for(const voltage of [0,6,12,24])for(const switch_closed of [false,true])for(let t=0;t<4;t+=.05){const p=structuredClone(composed);p.modules[0].params.voltage=voltage;p.modules[0].params.switch_closed=switch_closed;const s=sceneState(p,t);assert.ok(Math.abs(s.gear.rpm+s.motor.rpm/2)<1e-9);assert.equal(s.pump.rpm,s.gear.rpm);assert.ok(Math.abs(s.water.drive-Math.min(1,Math.abs(s.pump.rpm)/600))<1e-9);if(!switch_closed)assert.equal(s.water.wave.amplitude,0);couplings++;}
let partsChecked=0;const parts=presets.robot.modules[0].params.parts;
for(let t=0;t<10;t+=.031){const state=assemblyState(parts,t);for(const part of Object.values(state)){const R=part.rotation;for(let i=0;i<3;i++)for(let j=0;j<3;j++)assert.ok(Math.abs(R[i].reduce((s,v,k)=>s+v*R[j][k],0)-(i===j?1:0))<1e-9);assert.ok(part.vertices.flat().every(Number.isFinite));const m=parts.find(p=>p.id===part.id);assert.ok(Math.abs(Math.hypot(...part.center.map((v,i)=>v-part.position[i]))-Math.hypot(...m.offset))<1e-8);assert.ok(Math.abs(part.value)<=m.amplitude+1e-8);partsChecked++;}}
const sample=structuredClone(parts.slice(0,2));sample[0].position=[10,0,0];sample[0].rotation=[0,0,0];sample[1].position=[5,0,0];sample[1].offset=[10,0,0];sample[1].rotation=[0,0,0];sample[1].amplitude=90;sample[1].frequency=.25;sample[1].phase=0;let ref=assemblyState(sample,1).shoulder;assert.ok(Math.abs(ref.center[0]-15)<1e-9&&Math.abs(ref.center[1]-10)<1e-9&&Math.abs(ref.center[2])<1e-9);
sample[1].joint='prismatic';sample[1].axis='x';sample[1].amplitude=10;ref=assemblyState(sample,1).shoulder;assert.ok(Math.abs(ref.center[0]-35)<1e-9&&Math.abs(ref.center[1])<1e-9);
for(const bad of [null,{}, {...presets.engine,code:'alert(1)'}])assert.throws(()=>validateScene(bad,schema));
for(const change of [{parent:'elbow'},{shape:'html'},{color:'url(x)'},{position:[0,0,151]},{amplitude:181},{code:'bad'}]){const scene=structuredClone(presets.robot);Object.assign(scene.modules[0].params.parts[0],change);assert.throws(()=>validateScene(scene,schema));}
console.log(JSON.stringify({cylinders,motors,waves,couplings,partsChecked,presets:Object.keys(presets).length,referenceMotor:{omega:motor.omega,current:motor.current},passed:true}));
