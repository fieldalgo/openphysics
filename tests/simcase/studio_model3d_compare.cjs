// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Studio 3D Compare (C3): two runs of the same 3D model side by side. Pure helpers: the values
// table with B − A, the inputs that differ, whether the two runs share a mesh, and the surface ΔT.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let C;
test.before(async()=>{C=await import(STATIC+'workspace-model3d-compare.mjs');});
const card1=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-layer-stack-3d.json'),'utf8'));
const card2=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-via-slab-3d.json'),'utf8'));
const values=(o={})=>({run:'h3d-a',component:'stack3d',document_sha256:'x',
 heat_rate_by_selection:{z0:{value:-1.25,unit:'W'},z1:{value:1.0,unit:'W'}},
 total_source:{value:0.25,unit:'W'},balance_residual:{value:1e-12,unit:'W'},relative_balance_residual:{value:4e-13,unit:''},
 temperature_min:{value:300,unit:'K',node:3,position_m:[0,0,0],region:'Si'},
 temperature_max:{value:336.05,unit:'K',node:7,position_m:[3.85e-5,1.63e-4,5.1e-4],region:'SiO2'},
 mesh:{key:'k1',nodes:1551,tetrahedra:6774,route:'extrude',reused:false},...o});
const rec=(doc,v)=>({run:v.run,document:doc,values:v,surface:{unit:'um'}});

test('C3-1: values side by side with B − A, from the two records',()=>{
 const a=rec(card1(),values()),b=rec(card1(),values({run:'h3d-b',
  temperature_max:{...values().temperature_max,value:340.55},heat_rate_by_selection:{z0:{value:-1.5,unit:'W'},z1:{value:1.25,unit:'W'}},
  mesh:{key:'k2',nodes:1600,tetrahedra:7000,route:'extrude',reused:false}}));
 const rows=C.compareRows(a,b,'um');
 const by=Object.fromEntries(rows.map(r=>[r[0],r.slice(1)]));
 assert.deepEqual(rows.map(r=>r[0]),['Temperature, max (whole model)','Temperature, min (whole model)','Heat rate through z0','Heat rate through z1',
  'Total heat source','Energy balance residual','Mesh nodes','Mesh tetrahedra','Mesh route','Mesh element size']);
 assert.deepEqual(by['Temperature, max (whole model)'],['336.05 K in SiO2 at (38.5, 163, 510) µm','340.55 K in SiO2 at (38.5, 163, 510) µm','+4.5 K']);
 assert.deepEqual(by['Temperature, min (whole model)'][2],'0 K');
 assert.deepEqual(by['Heat rate through z0'],['-1.25 W','-1.5 W','−0.25 W']);
 assert.deepEqual(by['Heat rate through z1'][2],'+0.25 W');
 assert.deepEqual(by['Mesh nodes'],['1,551','1,600','+49']);
 assert.deepEqual(by['Mesh tetrahedra'],['6,774','7,000','+226']);
 assert.deepEqual(by['Mesh route'],['extrude','extrude','']);
 assert.deepEqual(by['Mesh element size'],['40 µm','40 µm','']);
 // Δ is B − A computed directly
 assert.equal(C.delta(340.55,336.05),340.55-336.05);
 // a selection only one run has: the other cell is "—" and Δ is empty
 const c=rec(card1(),values({heat_rate_by_selection:{z0:{value:-1.25,unit:'W'}}}));
 assert.deepEqual(Object.fromEntries(C.compareRows(c,a,'um').map(r=>[r[0],r.slice(1)]))['Heat rate through z1'],['—','1 W','']);
});

test('C3-2: the inputs that differ, in the tree\'s words; none: an empty list',()=>{
 const a=card1();
 const t=card1();t.geometry.parameters.t_ox.value='5 um';
 assert.deepEqual(C.inputChanges(a,t),['Parameter t_ox: 10 µm → 5 µm']);
 const z=card1();z.physics.heat.prescribed_temperature.z1='330 K';
 assert.deepEqual(C.inputChanges(a,z),['Fixed temperature z1: none → 330 K']);
 const m=card1();m.mesh.element_size='30 um';
 assert.deepEqual(C.inputChanges(a,m),['Mesh element size: 40 µm → 30 µm']);
 assert.deepEqual(C.inputChanges(a,card1()),[]);
 // a feature's field, a material's property and a removed fixed temperature
 const f=card1();f.geometry.components.stack3d.features[1].xmax=120;f.materials.Cu.thermal_conductivity='390 W/(m K)';delete f.physics.heat.prescribed_temperature.z0;
 const before=a.geometry.components.stack3d.features[1].xmax;
 assert.deepEqual(C.inputChanges(a,f),[`via xmax: ${before} → 120`,'Cu thermal conductivity: 400 W/(m K) → 390 W/(m K)','Fixed temperature z0: 300 K → none']);
});

test('C3-3: the same mesh is the same geometry+mesh digest with equal counts; a boundary change keeps it',()=>{
 const v=values();
 assert.equal(C.sameMesh(v,values({run:'h3d-b'})),true,'a boundary-only change: same key, same counts');
 assert.equal(C.sameMesh(v,values({mesh:{...v.mesh,key:'k2'}})),false,'a t_ox or element-size change: another digest');
 assert.equal(C.sameMesh(v,values({mesh:{...v.mesh,nodes:1552}})),false);
 assert.equal(C.sameMesh(v,values({mesh:{...v.mesh,tetrahedra:6775}})),false);
 const a=rec(card1(),v),b=rec(card1(),values({mesh:{key:'k2',nodes:1600,tetrahedra:7000,route:'extrude'}}));
 b.document.mesh.element_size='30 um';
 assert.equal(C.meshNotice(a,a),null);
 assert.equal(C.meshNotice(a,b),'The runs have different meshes (A: 1,551 nodes, size 40 µm; B: 1,600 nodes, size 30 µm). Values are compared; the surface temperature is not compared point by point.');
});

test('C3-4: the surface ΔT on a shared mesh, its range and largest magnitude; its legend',()=>{
 const ta=Float32Array.from([300,310,320]),tb=Float32Array.from([301,309,325]);
 const d=C.surfaceDelta(ta,tb);
 assert.deepEqual([...d.delta],[1,-1,5]);
 assert.deepEqual([d.min,d.max,d.maxAbs],[-1,5,5]);
 assert.equal(C.deltaLegend(d),'ΔT (B − A): −1–5 K · largest |ΔT| 5 K');
 assert.equal(C.surfaceDelta(ta,Float32Array.from([1,2])),null,'different lengths: not compared');
 // the encoded map round-trips (the result view decodes base64 float32)
 const text=C.encodeF32(Float32Array.from([1.5,-2]));
 assert.deepEqual([...new Float32Array(Uint8Array.from(Buffer.from(text,'base64')).buffer)],[1.5,-2]);
});

test('C3-6: the pickers default to the two newest runs; fewer than two runs says so',()=>{
 assert.deepEqual(C.defaultPair(5),[3,4]);
 assert.deepEqual(C.defaultPair(2),[0,1]);
 assert.equal(C.defaultPair(1),null);
 assert.equal(C.NEEDS_TWO,'Compare needs two runs of this 3D model.');
 assert.equal(C.inputsText([]),'Same inputs.');
});
