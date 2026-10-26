// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let lineProfile,profileCsv,probeField;
before(async()=>{({lineProfile,profileCsv}=await import('../../packages/simcase/src/simcase/studio/static/workspace-profile.mjs'));({probeField}=await import('../../packages/simcase/src/simcase/studio/static/workspace-probe.mjs'));});
const square=()=>({nodes:[[0,0],[1,0],[0,1],[1,1]],triangles:[[0,1,2],[1,3,2]]});
test('analytic unit square profiles preserve exact triangle intervals without interpolation',()=>{
 for(const axis of ['x','y']){const p=lineProfile(square(),[.2,.8],axis,.25);assert.deepEqual(p.map(s=>[s.start,s.end,s.index,s.value]),[[0,.75,0,.2],[.75,1,1,.8]]);assert.equal(p.reduce((sum,s)=>sum+(s.end-s.start)*s.value,0),.35000000000000003);}
 assert.deepEqual(lineProfile(square(),[.2,.8],'x',2),[]);
});
test('coincident edges, overlapping triangles, reversed winding and degeneracy follow painted field order',()=>{
 const field={nodes:[[0,0],[1,0],[0,1],[1,-1]],triangles:[[0,1,2],[0,3,1],[2,1,0],[0,1,1]]};const values=[.2,.4,.8,1];
 assert.deepEqual(lineProfile(field,values,'x',0).map(s=>[s.start,s.end,s.index]),[[0,1,2]]);
 for(const axis of ['x','y'])for(const coordinate of [-.5,0,.1,.5,1])for(const s of lineProfile(field,values,axis,coordinate)){const point=(s.start+s.end)/2;const probe=probeField(field,values,axis==='x'?point:coordinate,axis==='x'?coordinate:point);assert.equal(s.index,probe.index);assert.equal(s.value,probe.value);}
});
test('disconnected mesh gaps remain gaps and CSV carries interval provenance and units',()=>{
 const field={nodes:[[0,0],[1,0],[0,1],[2,0],[3,0],[2,1]],triangles:[[0,1,2],[3,4,5]]};const segments=lineProfile(field,[.2,.8],'x',.5);assert.deepEqual(segments.map(s=>[s.start,s.end]),[[0,.5],[2,2.5]]);
 const text=profileCsv([{run:{job:'abcdef12',origin:'imported'},segments}],'x',.5,1,'Ey');assert.match(text,/start_um,end_um,triangle,centroid_x_um/);assert.match(text,/abcdef12,imported,2,Ey,x,0.5,0,0.5,1,/);assert.equal(text.trim().split('\n').length,3);
 assert.throws(()=>lineProfile(field,[.2],'x',0));assert.throws(()=>lineProfile(field,[.2,NaN],'x',0));assert.throws(()=>lineProfile(field,[.2,.8],'z',0));assert.throws(()=>lineProfile(field,[.2,.8],'x',NaN));
});
