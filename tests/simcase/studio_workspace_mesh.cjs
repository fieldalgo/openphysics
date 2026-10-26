// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let readMesh,MeshPreview;
before(async()=>({readMesh,MeshPreview}=await import('../../packages/simcase/src/simcase/studio/static/workspace-mesh.mjs')));
const mesh=()=>({units:{length:'um'},nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],regions:[1],region_names:['background','core'],stats:{nodes:99,triangles:99,min_angle:45,quality_mean:.8}});
test('mesh preview validates coordinates, connectivity, units, regions and quality; counts derive from arrays',()=>{
 const m=readMesh(mesh());assert.equal(m.stats.nodes,3);assert.equal(m.stats.triangles,1);
 for(const change of [d=>d.units.length='nm',d=>d.nodes[0][0]=NaN,d=>d.triangles[0][0]=99,d=>d.regions=[2],d=>d.stats.min_angle=-1,d=>d.stats.quality_mean=2]){const d=mesh();change(d);assert.throws(()=>readMesh(d));}
});
test('mesh requests retain captured inputs, ignore duplicate starts, and preserve the previous preview on failure',async()=>{
 let resolve,calls=0;const input={model:{width:500}};const p=new MeshPreview(async()=>{calls++;return new Promise(r=>resolve=r);});const pending=p.generate(input,{});input.model.width=700;await p.generate(input,{});assert.equal(calls,1);resolve(mesh());await pending;assert.equal(p.record.input.model.width,500);assert.equal(p.busy,false);
 const previous=p.record;p.api=async()=>{throw Error('offline');};await p.generate(input,{});assert.equal(p.record,previous);assert.equal(p.error,'offline');assert.equal(p.busy,false);
});
