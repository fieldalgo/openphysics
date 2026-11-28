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

test('V4: document text shown in the Names box reads µm (faces\' coordinates and areas)',()=>{
 assert.equal(M.shownText('Face 4 · z = 510 um'),'Face 4 · z = 510 µm');
 assert.equal(M.shownText('area 400 um² · interior'),'area 400 µm² · interior');
 assert.equal(M.shownText('sum of drums'),'sum of drums','only the unit word');
});

test('V7: the mesh line names Component 1 with the elapsed time; old stats are the kept mesh\'s',()=>{
 const view={component:'stack3d',key:'k1',stats:{nodes:1551,tetrahedra:6774,regions:4}};
 assert.equal(M.meshDoneText(view,{status:'done',elapsed_s:1.234,reused:false}),'Meshed Component 1 in 1.2 s: 1,551 nodes, 6,774 tetrahedra, 4 regions.');
 assert.equal(M.meshDoneText(view,{status:'done',elapsed_s:0,reused:true}),'Meshed Component 1 (the kept mesh of this geometry and mesh block): 1,551 nodes, 6,774 tetrahedra, 4 regions.');
 assert.equal(M.meshDoneText({...view,stats:{nodes:153720,tetrahedra:812345,regions:4}},{status:'done',elapsed_s:83.6}),'Meshed Component 1 in 1 min 24 s: 153,720 nodes, 812,345 tetrahedra, 4 regions.');
 // the kept stats are labelled when the document's mesh no longer matches (another key, or a refusal)
 assert.equal(M.keptMeshLabel(view,{mesh:{ok:true,key:'k1'}}),null);
 assert.equal(M.keptMeshLabel(view,{mesh:{ok:true,key:'k2'}}),'Kept mesh (before the last change)');
 assert.equal(M.keptMeshLabel(view,{mesh:{ok:false,code:'E-MESH-ESTIMATE'}}),'Kept mesh (before the last change)');
 assert.equal(M.keptMeshLabel(null,{mesh:{ok:true,key:'k1'}}),null);
});
