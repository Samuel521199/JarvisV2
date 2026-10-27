import fs from 'node:fs';import assert from 'node:assert/strict';
import {operationTransforms,transmissionRatios,assemblyItems,assemblyOffsets} from '../modules/skills/anatomy/engineering-motion.mjs';
const scene=JSON.parse(fs.readFileSync(new URL('../modules/skills/anatomy/engineering-presets.json',import.meta.url)))['racecar'];
const ratios=transmissionRatios(scene);assert.equal(ratios.pinion,4);assert.equal(ratios['lay-shaft'],-2);assert.equal(ratios['output-gear'],1);const transforms=operationTransforms(scene,[.3,.1,.2,.1],10);assert.ok(transforms['pinion']);assert.ok(!transforms['cockpit']);
const body=assemblyItems(scene,'bodywork','parts');assert.equal(body.length,5);assert.equal(Object.keys(assemblyOffsets(scene,body,2,0)).length,2);const all=assemblyItems(scene,'','groups');assert.equal(all.length,9);assert.equal(Object.keys(assemblyOffsets(scene,all,all.length,0)).length,72);
fs.writeFileSync(new URL('../docs/evidence/anatomy-race-2026-10-23/js-math.json',import.meta.url),JSON.stringify({ratios,transforms}));console.log('racer: 4:1 reduction, keyed shafts, gear mesh ratio residual, rigid transforms and shell groups passed');
