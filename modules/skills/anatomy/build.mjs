import fs from 'node:fs';
import {validatePlanetary} from './planetary-model.mjs';
import {validateScene} from './studio-model.mjs';
const root=new URL('../../../',import.meta.url);
const mechanism=process.argv[2]||'slider-crank';
if(!['slider-crank','planetary','studio'].includes(mechanism))throw Error('unregistered mechanism');
const sceneSchema=JSON.parse(fs.readFileSync(new URL('./scene-schema.json',import.meta.url),'utf8'));
const config=mechanism==='studio'?validateScene(JSON.parse(fs.readFileSync(0,'utf8')),sceneSchema):mechanism==='planetary'?validatePlanetary(JSON.parse(fs.readFileSync(0,'utf8'))):{};
const kit=fs.readFileSync(new URL('external/anatomy/kit/iso-kit.mjs',root),'utf8').replace(/^export /gm,'').replaceAll('</script','<\\/script');
let page=fs.readFileSync(new URL(mechanism==='studio'?'./studio.html':mechanism==='planetary'?'./planetary.html':'./page.html',import.meta.url),'utf8');
page=page.replace('/* ANATOMY_KIT */',()=>kit).replace('/* ANATOMY_SOURCE */',()=>fs.readFileSync(new URL('external/anatomy/source.json',root),'utf8'));
if(mechanism==='planetary'){
 page=page.replace('/* JARVIS_MODEL */',()=>fs.readFileSync(new URL('./planetary-model.mjs',import.meta.url),'utf8').replace(/^export /gm,''))
  .replace('/* ANATOMY_CONFIG */',()=>JSON.stringify(config))
  .replace('/* ANATOMY_LICENSE */',()=>JSON.stringify(fs.readFileSync(new URL('external/anatomy/LICENSE',root),'utf8')))
  .replace('/* JARVIS_PLANETARY */',()=>fs.readFileSync(new URL('./planetary-view.js',import.meta.url),'utf8'));
}
if(mechanism==='studio'){
 const safeJson=v=>JSON.stringify(v).replaceAll('<','\\u003c');
 for(const [token,data] of [
  ['/* SCENE_DATA */',safeJson(config)],['/* SCENE_SCHEMA */',safeJson(sceneSchema)],
  ['/* STUDIO_PRESETS */',safeJson(JSON.parse(fs.readFileSync(new URL('./studio-presets.json',import.meta.url),'utf8')))],
  ['/* STUDIO_MODEL */',fs.readFileSync(new URL('./studio-model.mjs',import.meta.url),'utf8').replace(/^export /gm,'')],
  ['/* STRUCTURE_3D */',fs.readFileSync(new URL('./structure3d.mjs',import.meta.url),'utf8').replace(/^export /gm,'')+'\n'+fs.readFileSync(new URL('./structure-scenes.mjs',import.meta.url),'utf8').replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'')],
  ['/* ANATOMY_LICENSE */',safeJson(fs.readFileSync(new URL('external/anatomy/LICENSE',root),'utf8'))],
  ['/* STUDIO_VIEW */',fs.readFileSync(new URL('./studio-view.js',import.meta.url),'utf8')]
 ])page=page.replace(token,()=>data);
}
process.stdout.write(page);
