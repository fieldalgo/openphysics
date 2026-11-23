// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 13 (O5): "Use this run's inputs" lists only the settings that change, from → to.
const test=require('node:test');const assert=require('node:assert/strict');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
let I;
test.before(async()=>{I=await import(STATIC+'workspace-inputs.mjs');});
const doc=(shapes,extra={},materials={Core:'Silicon',Oxide:'Silica',Heater:''})=>({model:{wavelength:1550,coreMesh:30,shapes,...extra},setup:{materials}});
const rect=(w,x,more={})=>({name:'Core',type:'rect',material:'Silicon',x,y:0,w,h:220,...more});
test('only the settings that change, from → to, in the inspector words',()=>{
 assert.deepEqual(I.inputChanges(doc([rect(700,-350)],{modeCount:4}),doc([rect(600,-300)])),['Width 700 → 600 nm','Left x −350 → −300 nm','Modes to find 4 → 2']);
 assert.deepEqual(I.inputChanges(doc([rect(500,-250)]),doc([rect(500,-250)])),[]);
 assert.deepEqual(I.inputChanges(doc([rect(500,-250)],{groupIndex:true}),doc([rect(500,-250)],{wavelength:1500})),['Wavelength 1550 → 1500 nm','Group index on → off']);
 assert.deepEqual(I.inputChanges(doc([rect(500,-250)]),doc([rect(500,-250,{material:'Silicon nitride'})],{coreMesh:25})),['Core mesh size 30 → 25 nm','Material Silicon → Silicon nitride']);
});
test('with several shapes each change names its shape; a different count reads Shapes n → m',()=>{
 const two=w=>[rect(w,-250),{name:'Slab',type:'rect',material:'Silicon',x:-1000,y:-100,w:2000,h:100}];
 assert.deepEqual(I.inputChanges(doc(two(500)),doc(two(450))),['Core width 500 → 450 nm']);
 assert.deepEqual(I.inputChanges(doc([rect(500,-250)]),doc(two(500))),['Shapes 1 → 2']);
 const circle=r=>({name:'Rod',type:'circle',material:'Silicon',cx:0,cy:100,r});
 assert.deepEqual(I.inputChanges(doc([rect(500,-250),circle(100)]),doc([rect(500,-250),circle(120)])),['Rod radius 100 → 120 nm']);
});
