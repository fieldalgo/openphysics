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

test('U4: the run just finished is up to date; another kept run means no need to run',()=>{
 assert.equal(M.keptRunText(0,0),'Run 1 is up to date with these inputs.');
 assert.equal(M.keptRunText(1,null),'No need to run: Run 2 already has these results.');
 assert.equal(M.keptRunText(1,0),'No need to run: Run 2 already has these results.','the run just finished is another one');
});

const VALUES={heat_rate_by_selection:{z0:{value:-4,unit:'W'}},total_source:{value:4,unit:'W'},balance_residual:{value:-1e-13,unit:'W'},
 relative_balance_residual:{value:2e-14,unit:'1'},temperature_min:{value:300,unit:'K',position_m:[0,0,0],region:'Si'},
 temperature_max:{value:336.05,unit:'K',position_m:[3.85e-5,1.63e-4,5.1e-4],region:'SiO2'}};

test('U3: the sign of a heat rate in one line; Tmax at an interface; whole model vs surface',()=>{
 assert.equal(M.HEAT_RATE_SIGN,'Heat rate: positive into the model, negative out of it (a fixed temperature that removes heat shows a negative rate).');
 const rows=M.valuesRows(VALUES,'um');
 assert.deepEqual(rows.slice(0,2).map(r=>r[0]),['Temperature, max (whole model)','Temperature, min (whole model)']);
 assert.equal(rows[0][1],'336.05 K in SiO2 at (38.5, 163, 510) µm','a record without regions: as before');
 const live={...VALUES,temperature_max:{...VALUES.temperature_max,regions:['SiO2','Si (top)']},temperature_min:{...VALUES.temperature_min,regions:['Si']}};
 const r2=M.valuesRows(live,'um');
 assert.equal(r2[0][1],'336.05 K at the SiO2 / Si (top) interface, (38.5, 163, 510) µm');
 assert.equal(r2[1][1],'300 K in Si at (0, 0, 0) µm','one region: in it');
 assert.equal(M.colourBarTitle,'Surface temperature');
});
