// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');
const assert=require('node:assert/strict');
let SchematicCamera;
before(async()=>({SchematicCamera}=await import('../../packages/simcase/src/simcase/studio/static/workspace-viewport.mjs')));
test('zoom retains the centre, pan stays in the schematic, fit restores extent',()=>{
 const c=new SchematicCamera();assert.deepEqual(c.box,[0,0,600,350]);
 c.scale(2);assert.deepEqual(c.box,[150,87.5,300,175]);
 c.pan(10,-10);assert.deepEqual(c.box,[300,0,300,175]);
 c.fit();assert.deepEqual(c.box,[0,0,600,350]);
});
test('finite zoom limits and independent cameras survive repeated interaction',()=>{
 const a=new SchematicCamera(),b=new SchematicCamera();
 for(let i=0;i<100;i++)a.scale(1.25);
 assert.equal(a.zoom,4);a.pan(-100,100);assert.deepEqual(a.box,[0,262.5,150,87.5]);
 const box=a.box;for(const f of [NaN,Infinity,0,-1])a.scale(f);a.pan(NaN,1);assert.deepEqual(a.box,box);
 for(let i=0;i<100;i++)a.scale(.8);
 assert.deepEqual(a.box,[0,0,600,350]);assert.deepEqual(b.box,[0,0,600,350]);
});
