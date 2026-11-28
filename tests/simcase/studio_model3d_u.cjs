// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Studio 3D fixes U1–U8 (the agent round's findings), pure helpers.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let M,C;
test.before(async()=>{M=await import(STATIC+'workspace-model3d.mjs');C=await import(STATIC+'model3d-mesh-model.mjs');});
const card=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-layer-stack-3d.json'),'utf8'));
const W=()=>({estimateText:C.estimateText,meshBlocked:C.meshBlocked});
const ENGINE="component 'stack3d': about 153720000 tetrahedra from the element sizes (T = 6.3 sum(V/h^3)); the limit is 600000 (mesh.element_count_limit)";
const OFF={ok:false,code:'E-MESH-ESTIMATE',path:'mesh.element_count_limit',refused:ENGINE,feature_index:null,tetrahedra:153720000,limit:600000,suggested_size:5.37};

test('U1: an estimate refusal in plain words, with thousands separators and the smallest size',()=>{
 assert.equal(M.meshRefusalText(OFF,'um'),'Component 1 needs about 153,720,000 tetrahedra; the limit is 600,000. Use an element size of at least 5.37 µm.');
 assert.equal(M.meshRefusalText({...OFF,suggested_size:null},'um'),'Component 1 needs about 153,720,000 tetrahedra; the limit is 600,000. Increase the element size.');
 const other={ok:false,code:'E-CONTRACT',refused:'geometry.components.c: feature … below the mesher tolerance',feature_index:null};
 assert.equal(M.meshRefusalText(other,'um'),other.refused,'other refusals keep the engine\'s words');
});

test('U1: shown once: Mesh and Run point to Messages; the label reads Element size',()=>{
 const check={features:[],regions:[],display:{faces:[]},mesh:OFF,run:{ok:true}};
 assert.equal(M.meshReason({check},W()),'Fix 1 problem in Messages to mesh');
 assert.equal(M.runReason({check},W()),'Fix 1 problem in Messages to run');
 assert.equal(M.fieldsOf(card(),'mesh')[0].label,'Element size');
 assert.equal(M.fieldsOf(card(),'feature:1').find(f=>f.key==='features[1].element_size').label,'Element size');
});
