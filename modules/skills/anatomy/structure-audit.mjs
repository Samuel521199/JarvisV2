// Trusted deterministic audit of declarative scenes; never executes model code.
import fs from 'node:fs';
import * as models from './studio-model.mjs';
import {buildStructure,structureView} from './structure-scenes.mjs';
const schema=JSON.parse(fs.readFileSync(new URL('./scene-schema.json',import.meta.url),'utf8'));
const scene=models.validateScene(JSON.parse(fs.readFileSync(0,'utf8')),schema);
const report={schema:'anatomy.structure.audit.v1',scope:'geometry and limited teaching models; not screenshot vision or CFD',modules:[],checks:{finite_geometry:true,unique_parts:true,camera_parallax:true},unfulfilled:scene.unfulfilled};
for(const m of scene.modules){const states=models.sceneState(scene,.11),mesh=buildStructure(m,states[m.id],.11,{effects:true,explode:0},models),a=structureView(m,states[m.id],.11,{shell:'section',azimuth:38,elevation:25,effects:true},models),b=structureView(m,states[m.id],.11,{shell:'section',azimuth:128,elevation:45,effects:true},models);
 const finite=mesh.faces.every(f=>f.points.flat().every(Number.isFinite)),unique=new Set(mesh.parts.map(p=>p.id)).size===mesh.parts.length;report.checks.finite_geometry&&=finite;report.checks.unique_parts&&=unique;report.checks.camera_parallax&&=a.svg!==b.svg;
 report.modules.push({id:m.id,type:m.type,label:m.label,configuration:m.params,stats:a.stats,parts:mesh.parts.map(p=>({id:p.id,label:p.label,layer:p.layer,note:p.note})),effects:mesh.effects.map(e=>({kind:e.kind,...e.kind==='flame'?{start:e.start,end:e.end,radius:e.radius}:{count:e.count}}))});
}
report.limits=['Software projection with polygon depth sorting; no per-pixel z buffer or ray-traced transparency','Housing-only section, no exact solid section cap/CAD manufacturing geometry','Flows and flames are prescribed 3D paths/volumes, not computed fluids/combustion','Motor steady state, water linear 1D shown as 3D surface; no loads fed upstream','No screenshot was supplied to the model in this audit; visual beauty is not evaluated'];
process.stdout.write(JSON.stringify(report));
