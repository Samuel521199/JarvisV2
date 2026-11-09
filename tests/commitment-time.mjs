import assert from 'node:assert/strict';
import {exactTime,offsetText} from '../apps/workbench/commitment-time.js';
assert.equal(offsetText(480),'+08:00');assert.equal(offsetText(-210),'-03:30');
assert.equal(exactTime('2030-01-01T12:00','+08:00'),'2030-01-01T12:00:00+08:00');
assert.equal(exactTime('','+08:00'),null);
for(const zone of ['+14:30','+00:90','08:00','+15:00'])assert.throws(()=>exactTime('2030-01-01T12:00',zone));
console.log('Explicit fixed-offset commitment time passed');
