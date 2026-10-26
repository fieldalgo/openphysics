// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let probeField,triangleAt;
before(async()=>({probeField,triangleAt}=await import('../../packages/simcase/src/simcase/studio/static/workspace-probe.mjs')));
const field={nodes:[[0,0],[1,0],[0,1],[1,1]],triangles:[[0,1,2],[1,3,2]]};
test('probe selects containing triangles and their stored values without interpolation',()=>{
 assert.deepEqual(probeField(field,[.2,.8],.1,.1),{index:0,centroid:[1/3,1/3],value:.2,x:.1,y:.1});
 assert.equal(probeField(field,[.2,.8],.8,.8).value,.8);
 assert.equal(probeField(field,[.2,.8],.2,.2).value,.2);
 assert.equal(probeField(field,[.2,.8],.5,.5).index,1);
 assert.equal(probeField(field,[.2,.8],1.1,.5),null);
 assert.throws(()=>triangleAt(field,NaN,0));assert.throws(()=>probeField(field,[.2],0,0));
});
test('probe supports reversed winding and translated small physical coordinates; degenerate cells do not match',()=>{
 const f={nodes:[[10,20],[10.001,20],[10,20.001]],triangles:[[2,1,0]]};assert.equal(triangleAt(f,10.0001,20.0001).index,0);assert.equal(triangleAt(f,9,20),null);
 assert.equal(triangleAt({nodes:[[0,0],[1,1],[2,2]],triangles:[[0,1,2]]},1,1),null);
});
