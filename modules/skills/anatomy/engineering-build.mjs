import fs from 'node:fs';
const data=JSON.parse(fs.readFileSync(0,'utf8'));
if(data.scene?.schema!=='anatomy.engineering.v1'||data.result?.schema!=='anatomy.engineering.result.v1')throw Error('Engineering data contract required');
const read=p=>fs.readFileSync(new URL(p,import.meta.url),'utf8');
const page=read('./engineering.html').replace('/* ENGINEERING_DATA */',()=>JSON.stringify(data).replaceAll('<','\\u003c')).replace('/* STRUCTURE_MODEL */',()=>read('./structure3d.mjs').replace(/^export /gm,'')).replace('/* ENGINEERING_VIEW */',()=>read('./engineering-view.js')).replace('/* ENGINEERING_SOURCE */',()=>read('../../../external/anatomy/source.json')).replace('/* ENGINEERING_LICENSE */',()=>JSON.stringify(read('../../../external/anatomy/LICENSE')));
process.stdout.write(page.replace('/* ENGINEERING_GPU */',()=>read('./engineering-gpu.mjs').replace(/^export /gm,'')).replace('/* ENGINEERING_MOTION */',()=>read('./engineering-motion.mjs').replace(/^export /gm,'')));
