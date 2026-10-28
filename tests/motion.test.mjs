import {test} from 'node:test';
import assert from 'node:assert/strict';
import {bowlPose,spoonPose} from '../src/motion-math.mjs';
test('bowl moves from head to lap with a path around the face',()=>{
 assert.equal(bowlPose(0).y,1.48);assert.ok(Math.abs(bowlPose(1).y+.19)<1e-9);assert.ok(bowlPose(.5).x<-.5);assert.ok(bowlPose(1).z>1);
});
test('spoon position is continuous through every phase and cycle seam',()=>{
 for(const boundary of [1.1,2.5,3.15,5.4,10.8]){const a=spoonPose(boundary-1e-4),b=spoonPose(boundary+1e-4);assert.ok(Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z)<.001)}
});
test('spoon reaches mouth before rice disappears and returns to bowl',()=>{
 assert.equal(spoonPose(2.7).bite,true);assert.equal(spoonPose(3).grain,0);assert.equal(spoonPose(0).progress,0);assert.ok(spoonPose(2.7).y>spoonPose(0).y);
});
