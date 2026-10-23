import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as models from '../modules/skills/anatomy/studio-model.mjs';
import {clipPolygon,cameraProjection,projectStructure} from '../modules/skills/anatomy/structure3d.mjs';
import {buildStructure,structureView} from '../modules/skills/anatomy/structure-scenes.mjs';
const schema=JSON.parse(fs.readFileSync(new URL('../modules/skills/anatomy/scene-schema.json',import.meta.url))),presets=JSON.parse(fs.readFileSync(new URL('../modules/skills/anatomy/studio-presets.json',import.meta.url)));
let scenes=0,faces=0,vertices=0,particles=0;const records=[];
for(const preset of Object.values(presets)){
 const scene=models.validateScene(preset,schema);
 for(const time of [0,.03,.11,.29]){const states=models.sceneState(scene,time);
  for(const m of scene.modules){const mesh=buildStructure(m,states[m.id],time,{effects:true,explode:.2},models);assert.ok(mesh.parts.length>=2);assert.equal(new Set(mesh.parts.map(p=>p.id)).size,mesh.parts.length);const ids=new Set(mesh.parts.map(p=>p.id));
   for(const face of mesh.faces){assert.ok(ids.has(face.part));assert.ok(face.points.length>=3);assert.ok(face.points.flat().every(Number.isFinite));assert.match(face.color,/^#[a-f0-9]{6}$/i);faces++;vertices+=face.points.length;}
   for(const p of mesh.particles){assert.ok(p.position.every(Number.isFinite));assert.ok(p.radius>0&&p.opacity>=0&&p.opacity<=1);particles++;}
   const a=projectStructure(mesh,{azimuth:38,elevation:25,shell:'section'}),b=projectStructure(mesh,{azimuth:128,elevation:45,shell:'section'});assert.notEqual(a.svg,b.svg);assert.ok(!/NaN|undefined|Infinity/.test(a.svg));assert.ok(a.stats.clipped>=0);scenes++;
   if(time===.11)records.push({type:m.type,parts:mesh.parts.map(p=>({id:p.id,label:p.label,layer:p.layer})),stats:a.stats,effects:mesh.effects.map(e=>e.kind)});
  }
 }
}
for(let cut=-1;cut<=1;cut+=.1){const clipped=clipPolygon([[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0]],cut);assert.ok(clipped.every(p=>p[1]>=cut-1e-9));assert.ok(clipped.flat().every(Number.isFinite));}
const jet=models.validateScene(presets.jet,schema),jm=jet.modules[0],js=models.sceneState(jet,.11).jet,jmesh=buildStructure(jm,js,.11,{effects:true},models);
assert.equal(jmesh.parts.filter(p=>p.id.startsWith('compressor-rotor')).length,5);assert.equal(jmesh.parts.filter(p=>p.id.startsWith('compressor-stator')).length,5);assert.equal(jmesh.parts.filter(p=>p.id.startsWith('turbine-rotor')).length,2);assert.equal(jmesh.effects.filter(e=>e.kind==='flame').length,8);
const fire=jmesh.particles.filter(p=>p.part==='flames');assert.ok(fire.every(p=>p.position[0]>=5&&p.position[0]<=76));assert.ok(fire.every(p=>Math.hypot(p.position[1],p.position[2])>24&&Math.hypot(p.position[1],p.position[2])<41));
const cold=structuredClone(jet);cold.modules[0].params.throttle=0;assert.equal(buildStructure(cold.modules[0],models.sceneState(cold,1).jet,1,{effects:true},models).particles.length,0);
const pumpScene={...presets.waves,modules:[{id:'pump',type:'pump',label:'pump',params:{rpm:0},effects:['flow']}]},pmp=models.validateScene(pumpScene,schema);assert.equal(buildStructure(pmp.modules[0],models.sceneState(pmp,1).pump,1,{effects:true},models).particles.length,0);
const engine=models.validateScene(presets.engine,schema),em=engine.modules[0],es=models.sceneState(engine,.11).engine,eg=buildStructure(em,es,.11,{effects:true},models);assert.ok(eg.parts.some(p=>p.id==='camshafts'));assert.ok(eg.parts.some(p=>p.id==='timing'));assert.equal(eg.parts.filter(p=>p.id.startsWith('piston-')).length,4);assert.equal(eg.parts.filter(p=>p.id.startsWith('coolant-')).length,4);
for(const dot of eg.particles.filter(p=>p.part==='gas-0')){const top=em.params.crank_mm*(1+em.params.rod_ratio)+40-18,low=es.cylinders[0].piston+12;assert.ok(dot.position[2]>=low-1e-6&&dot.position[2]<=top+1e-6);assert.ok(Math.hypot(dot.position[0]+157.5,dot.position[1])<40);}
const closed=projectStructure(jmesh,{shell:'closed'}),cut=projectStructure(jmesh,{shell:'section',cut:0}),hidden=projectStructure(jmesh,{shell:'hidden'});assert.ok(cut.stats.clipped>0);assert.ok(closed.stats.visibleFaces>cut.stats.visibleFaces&&cut.stats.visibleFaces>hidden.stats.visibleFaces);
const test=cameraProjection([[0,0,0],[1,1,1]],{azimuth:0,elevation:0});assert.notEqual(test.project([0,0,0])[2],test.project([0,1,0])[2]);
console.log(JSON.stringify({status:'passed',scenes,faces,vertices,particles,checks:['finite meshes','camera parallax','cut clipping','internal inventories','flame containment','off state stops particles'],inventories:records}));
