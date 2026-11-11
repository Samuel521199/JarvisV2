import assert from 'node:assert/strict';
import {validCamera} from '../apps/workbench/model-library-camera.js';
const good={position:[3,2,1],target:[0,0,0],up:[0,1,0],fov:42};assert.ok(validCamera(good));
for(const bad of [null,{}, {...good,position:[NaN,0,0]},{...good,up:[0,0,0]},{...good,fov:180},{...good,position:[0,0,0]},{...good,target:[1e7,0,0]},{...good,position:['3',2,1]}])assert.ok(!validCamera(bad));
console.log('PASS bounded camera coordinates, orientation and projection contract');
