// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D mesh job's pure helpers (model3d-mesh-model.mjs): the estimate's words, the steps, the
// elapsed time, "taking longer than the estimate", and the per-triangle colours.
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let M;
before(async()=>{M=await import('../../packages/simcase/src/simcase/studio/static/model3d-mesh-model.mjs');});

test('the estimate reads "Estimate 48,000 tetrahedra · about 30 s" at the card size',()=>{
 assert.equal(M.estimateText({tetrahedra:47787,seconds:47787*6e-4}),'Estimate 48,000 tetrahedra · about 30 s');
 assert.equal(M.estimateText({tetrahedra:20160,seconds:12.096}),'Estimate 20,000 tetrahedra · about 10 s');
 assert.equal(M.estimateText({tetrahedra:114796,seconds:68.88}),'Estimate 110,000 tetrahedra · about 1 min');
 assert.equal(M.estimateText({tetrahedra:12.6,seconds:0.0076}),'Estimate 13 tetrahedra · under 1 s');
 assert.equal(M.durationText(4.4),'about 4 s');assert.equal(M.durationText(185),'about 3 min');
 assert.equal(M.roundedCount(999),'1,000');assert.equal(M.roundedCount(150),'150');
});

test('elapsed time is m:ss',()=>{
 assert.equal(M.elapsedText(0),'0:00');assert.equal(M.elapsedText(9.99),'0:09');
 assert.equal(M.elapsedText(61),'1:01');assert.equal(M.elapsedText(3600),'60:00');assert.equal(M.elapsedText(-1),'0:00');
});

test('the steps Studio knows, with the expected meshing time',()=>{
 const s={status:'running',step:'meshing',expected_s:28.8,elapsed_s:3};
 assert.deepEqual(M.stepList(s).map(x=>[x.label,x.state]),[['Forming geometry','done'],
  ['Meshing (expected about 30 s)','current'],['Checking the mesh','todo'],['Ready','todo']]);
 assert.deepEqual(M.stepList({...s,status:'done',step:'ready'}).map(x=>x.state),['done','done','done','done']);
 assert.deepEqual(M.stepList({...s,status:'cancelled',step:null}).map(x=>x.state),['todo','todo','todo','todo']);
 assert.equal(M.progressText(s),'Meshing (expected about 30 s) · 0:03');
});

test('"taking longer than the estimate" once elapsed passes twice the estimate',()=>{
 const s={status:'running',step:'meshing',expected_s:10,elapsed_s:20};
 assert.equal(M.longer(s),false);
 assert.equal(M.longer({...s,elapsed_s:20.001}),true);
 assert.equal(M.progressText({...s,elapsed_s:75}),'Meshing (expected about 10 s) · 1:15 · taking longer than the estimate');
 assert.equal(M.longer({...s,status:'done',elapsed_s:99}),false);
});

test('cancel is named Cancel meshing and keeps nothing',()=>{
 assert.equal(M.CANCEL_LABEL,'Cancel meshing');
 assert.equal(M.progressText({status:'cancelled',step:null,expected_s:1,elapsed_s:3}),'Meshing cancelled; nothing kept.');
 assert.equal(M.progressText({status:'error',error:{message:'boom'},expected_s:1,elapsed_s:3}),'Meshing failed: boom');
});

test('Mesh is disabled with the reason',()=>{
 assert.equal(M.meshBlocked({estimate:{tetrahedra:1,seconds:1},refused:null,running:false}),null);
 assert.equal(M.meshBlocked({estimate:null,refused:'about 900 tetrahedra; the limit is 600',running:false}),
  'about 900 tetrahedra; the limit is 600');
 assert.match(M.meshBlocked({estimate:{},refused:null,running:true}),/cancel it/);
});

test('stats rows and per-triangle colours',()=>{
 const rows=M.statsRows({stats:{nodes:5262,tetrahedra:23652,regions:3,quality_min:0.37558,quality_median:0.81983,surface_triangles:7569}});
 assert.deepEqual(rows,[['Nodes','5,262'],['Tetrahedra','23,652'],['Regions','3'],['Quality, min','0.376'],
  ['Quality, median','0.820'],['Surface triangles','7,569']]);
 const positions=new Float32Array([0,0,0,1,0,0,0,1,0,1,1,0]),indices=new Uint32Array([0,1,2,1,3,2]);
 const out=M.triangleColors(positions,indices,t=>t?'b':'a',r=>r==='a'?[1,0,0]:[0,0,1],t=>t?0.5:1,t=>true);
 assert.equal(out.positions.length,18);
 assert.deepEqual([...out.colors.slice(0,3)],[1,0,0]);assert.deepEqual([...out.colors.slice(9,12)],[0,0,0.5]);
 assert.equal(M.triangleColors(positions,indices,()=>'a',()=>[1,1,1],()=>1,t=>t===1).positions.length,9);
});
