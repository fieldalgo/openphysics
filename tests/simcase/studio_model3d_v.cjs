// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Studio 3D fixes V1–V11 (agent round 3D-2), pure helpers.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let M;
test.before(async()=>{M=await import(STATIC+'workspace-model3d.mjs');});
const card1=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-layer-stack-3d.json'),'utf8'));
const card2=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-via-slab-3d.json'),'utf8'));

test('V5: the line after a run uses the Settings table\'s place words (no coordinates)',()=>{
 const t={value:336.0512,unit:'K',node:7,position_m:[3.85e-5,1.63e-4,5.1e-4],region:'SiO2'};
 const tail=' Its results belong to that run; editing the model does not change them.';
 assert.equal(M.runCompleteText(0,{temperature_max:{...t,regions:['SiO2','Si (top)']}}),'Run 1 complete: maximum 336.051 K at the SiO2 / Si (top) interface.'+tail);
 assert.equal(M.runCompleteText(2,{temperature_max:t}),'Run 3 complete: maximum 336.051 K in SiO2.'+tail);
 assert.equal(M.runCompleteText(0,{temperature_max:{...t,regions:['SiO2']}}),'Run 1 complete: maximum 336.051 K in SiO2.'+tail);
});
