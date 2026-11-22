// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let readOpticalField,fieldScalars;
before(async()=>{
({readOpticalField,fieldScalars}=await import('../../packages/simcase/src/simcase/studio/static/workspace-field.mjs'));
});
const test=require('node:test');const assert=require('node:assert/strict');

// a section 5.3.4 payload: node coordinates in metres; the field named unnormalized_electric_field (x, y, z)
const fixture=()=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6]],field_units:{node_coordinates:'m'},triangles:[[0,1,2]],vector_fields:[{name:'unnormalized_electric_field',location:'triangle_centroids',components:['x','y','z'],unit:'1',normalization:'max_centroid_magnitude',time_convention:'exp(-i omega t)',real:[[[3,0,0]],[[0,0,0]]],imag:[[[0,4,0]],[[0,0,0]]]}]});
test('complex 3-4-5 reference and common vector denominator for components',()=>{const f=readOpticalField(fixture());assert.equal(fieldScalars(f,0).maximum,5);assert.deepEqual(fieldScalars(f,0).values,[1]);assert.deepEqual(fieldScalars(f,0,'Ex').values,[.6]);assert.deepEqual(fieldScalars(f,0,'Ey').values,[.8]);assert.deepEqual(fieldScalars(f,1).values,[0]);});
test('reject metadata, missing samples, nonfinite samples and bad topology',()=>{for(const change of [d=>d.vector_fields[0].location='nodes',d=>d.vector_fields[0].real[0]=[],d=>d.vector_fields[0].imag[0][0][0]=NaN,d=>d.triangles[0][2]=999,d=>d.node_coordinates[0][0]=Infinity,d=>d.vector_fields[0].components=['Ex','Ey','Ez'],d=>d.vector_fields[0].amplitude_unit='relative',d=>delete d.vector_fields[0].time_convention,d=>d.field_units.node_coordinates='um']){const d=fixture();change(d);assert.throws(()=>readOpticalField(d));}});
test('coordinates in metres are drawn in micrometres; the metre values are kept',()=>{const f=readOpticalField(fixture());assert.deepEqual(f.nodes,[[0,0],[1,0],[0,1]]);assert.deepEqual(f.node_coordinates,[[0,0],[1e-6,0],[0,1e-6]]);});
test('result samples are isolated from source mutation and selection is bounded',()=>{const d=fixture(),f=readOpticalField(d);d.vector_fields[0].real[0][0][0]=100;assert.equal(fieldScalars(f,0).maximum,5);assert.throws(()=>fieldScalars(f,2));assert.throws(()=>fieldScalars(f,0,'power'));});

test('plot axes tick on round nanometre values inside the view, labelled in nm',async()=>{
 const {nmTicks,formatNm}=await import('../../packages/simcase/src/simcase/studio/static/workspace-field.mjs');
 const nm=(a,b,n)=>nmTicks(a,b,n).map(v=>formatNm(v));
 assert.deepEqual(nm(-1.5,1.5,7),['−1500','−1000','−500','0','500','1000','1500']);
 assert.deepEqual(nm(-1.5,1.5,5),['−1000','0','1000']);
 // the core-region view of round 3 (ticks were 0.87 / 0.15 / −0.57 µm)
 assert.deepEqual(nm(-0.57,0.87,5),['−500','0','500']);
 assert.deepEqual(nm(-0.25,0.75,5),['−200','0','200','400','600']);
 for(const [a,b,n] of [[-1.5,1.5,3],[-0.57,0.87,7],[-0.0123,0.0177,5],[0.1,0.1004,4]]){
  const ticks=nmTicks(a,b,n);assert.ok(ticks.length>=1&&ticks.length<=n,`${a} ${b} ${n}: ${ticks}`);
  for(const t of ticks){assert.ok(t>=a-1e-12&&t<=b+1e-12);assert.ok(Number.isInteger(Math.round(t*1e7)/1e4),'whole or round nm');}
 }
 assert.ok(!nmTicks(-1,1,5).some(t=>Object.is(t,-0)),'no negative zero');
 assert.throws(()=>nmTicks(1,1));assert.throws(()=>nmTicks(0,NaN));assert.throws(()=>nmTicks(0,1,1));
 assert.equal(formatNm(-0.57),'−570');assert.equal(formatNm(0.1234567,1),'123.5');assert.equal(formatNm(-0.00001),'0');assert.equal(formatNm(0.15,1),'150');
});
