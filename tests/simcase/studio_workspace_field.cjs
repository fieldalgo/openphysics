// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let readOpticalField,fieldScalars;
before(async()=>{
({readOpticalField,fieldScalars}=await import('../../packages/simcase/src/simcase/studio/static/workspace-field.mjs'));
});
const test=require('node:test');const assert=require('node:assert/strict');

const fixture=()=>({nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],vector_fields:[{location:'triangle_centroids',components:['Ex','Ey','Ez'],normalization:'max_centroid_magnitude',amplitude_unit:'relative',real:[[[3,0,0]],[[0,0,0]]],imag:[[[0,4,0]],[[0,0,0]]]}]});
test('complex 3-4-5 reference and common vector denominator for components',()=>{const f=readOpticalField(fixture());assert.equal(fieldScalars(f,0).maximum,5);assert.deepEqual(fieldScalars(f,0).values,[1]);assert.deepEqual(fieldScalars(f,0,'Ex').values,[.6]);assert.deepEqual(fieldScalars(f,0,'Ey').values,[.8]);assert.deepEqual(fieldScalars(f,1).values,[0]);});
test('reject metadata, missing samples, nonfinite samples and bad topology',()=>{for(const change of [d=>d.vector_fields[0].location='nodes',d=>d.vector_fields[0].real[0]=[],d=>d.vector_fields[0].imag[0][0][0]=NaN,d=>d.triangles[0][2]=999,d=>d.nodes[0][0]=Infinity]){const d=fixture();change(d);assert.throws(()=>readOpticalField(d));}});
test('result samples are isolated from source mutation and selection is bounded',()=>{const d=fixture(),f=readOpticalField(d);d.vector_fields[0].real[0][0][0]=100;assert.equal(fieldScalars(f,0).maximum,5);assert.throws(()=>fieldScalars(f,2));assert.throws(()=>fieldScalars(f,0,'power'));});
