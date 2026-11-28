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

test('V9: each name says whether it selects only this face or also others; an interior face says how to see it',()=>{
 const view={faces:[
  {id:4,axis:'z',names:['stack.oxide.top','stack.top.bottom','via.z1'],alone:['via.z1'],minus:['via'],plus:['Si (top)'],exterior:false},
  {id:5,axis:'z',names:['domain.z1','stack.top.top'],alone:['domain.z1','stack.top.top'],minus:['Si (top)'],plus:[],exterior:true},
  {id:6,axis:'x',names:['domain.x0','stack.sub.domain.x0'],alone:['stack.sub.domain.x0'],minus:[],plus:['Si'],exterior:true},
  {id:7,axis:'x',names:['domain.x0','stack.oxide.domain.x0'],alone:['stack.oxide.domain.x0'],minus:[],plus:['SiO2'],exterior:true},
  {id:9,axis:'z',names:['stack.oxide.top','stack.top.bottom'],alone:[],minus:['SiO2'],plus:['Si (top)'],exterior:false},
  {id:12,axis:'x',names:['via.x0'],alone:['via.x0'],minus:['SiO2'],plus:['via'],exterior:false}]};
 assert.deepEqual(M.nameScopes(view,view.faces[0]),[['stack.oxide.top','also face 9'],['stack.top.bottom','also face 9'],['via.z1','only this face']]);
 assert.deepEqual(M.nameScopes(view,view.faces[2]),[['domain.x0','also face 7'],['stack.sub.domain.x0','only this face']]);
 assert.equal(M.interiorHint(view.faces[0]),'Interior face: hide Si (top), the region above it, with Regions in the view toolbar to see it.');
 assert.equal(M.interiorHint(view.faces[5]),'Interior face: hide via, the region on its +x side, with Regions in the view toolbar to see it.');
 assert.equal(M.interiorHint(view.faces[1]),null,'an exterior face needs no hint');
});

test('V1: Use for → Fixed temperature takes its value: the reason while it is missing or wrong; the node with it',()=>{
 assert.equal(M.useTemperatureProblem(''),'Type a temperature in K to apply.');
 assert.equal(M.useTemperatureProblem('   '),'Type a temperature in K to apply.');
 assert.equal(M.useTemperatureProblem('330'),null);
 assert.equal(M.useTemperatureProblem('330 K'),null);
 assert.match(M.useTemperatureProblem('-5'),/Fixed temperature/);
 assert.match(M.useTemperatureProblem('abc'),/^Enter fixed temperature/);
 const d=M.setFixedTemperature(card1(),'stack.top.top','330');
 assert.equal(d.physics.heat.prescribed_temperature['stack.top.top'],'330 K');
 assert.equal(M.fixedNoticeText('stack.top.top',d),'Fixed temperature 330 K on stack.top.top.');
});

test('V10: a cylinder crossing a domain side gets a plain suggestion, inside only; the engine text stays',()=>{
 const doc=cx=>{const d=card2();d.geometry.components.c.features[0].cx=cx;return d;};
 const off=side=>({ok:false,code:'E-3D-COMBINATION',path:'geometry.components.c.features[0]',feature_index:0,
  refused:`cylinder 'via' crosses the side domain.${side} between z = 0 and 1 m; a cylinder must lie inside or outside every side it spans`});
 assert.equal(M.crossingAdvice(off('x1'),doc(0.8)),'Cylinder via crosses the domain side x = 1 m. Keep cx ≤ 0.7 m (cx + r ≤ 1 m), or r ≤ 0.2 m.');
 assert.equal(M.crossingAdvice(off('x0'),doc(-0.8)),'Cylinder via crosses the domain side x = −1 m. Keep cx ≥ −0.7 m (cx − r ≥ −1 m), or r ≤ 0.2 m.');
 const y=card2();y.geometry.components.c.features[0].cy=0.9;
 assert.equal(M.crossingAdvice(off('y1'),y),'Cylinder via crosses the domain side y = 1 m. Keep cy ≤ 0.7 m (cy + r ≤ 1 m), or r ≤ 0.1 m.');
 const y0=card2();y0.geometry.components.c.features[0].cy=-0.75;
 assert.equal(M.crossingAdvice(off('y0'),y0),'Cylinder via crosses the domain side y = −1 m. Keep cy ≥ −0.7 m (cy − r ≥ −1 m), or r ≤ 0.25 m.');
 // a centre or radius written as an expression: the inequality alone
 const e=card2();e.geometry.components.c.features[0].cx='0.5 + 0.3';
 assert.equal(M.crossingAdvice(off('x1'),e),'Cylinder via crosses the domain side x = 1 m. Keep cx ≤ 0.7 m (cx + r ≤ 1 m).');
 assert.equal(M.crossingAdvice({...off('x1'),refused:'something else'},doc(0.8)),null);
});

test('V3: the estimate refusal gives the smallest accepted size and a size that meshes in about a minute',()=>{
 const OFF={ok:false,code:'E-MESH-ESTIMATE',path:'mesh.element_count_limit',refused:'…',feature_index:null,tetrahedra:19215000,limit:600000,
  suggested_size:6.36,suggested_tetrahedra:597583,suggested_seconds:358.55,suggested_minute:11.7,minute_tetrahedra:98783,minute_seconds:59.27};
 assert.equal(M.meshRefusalText(OFF,'um'),'Component 1 needs about 19,215,000 tetrahedra; the limit is 600,000. Element size 6.36 µm meshes about 597,583 tetrahedra (estimated about 6 min); 11.7 µm about 98,783 (estimated about 1 min).');
 // one size does both: a single sentence
 assert.equal(M.meshRefusalText({...OFF,suggested_seconds:40,suggested_minute:6.36,minute_tetrahedra:597583,minute_seconds:40},'um'),'Component 1 needs about 19,215,000 tetrahedra; the limit is 600,000. Element size 6.36 µm meshes about 597,583 tetrahedra (estimated about 40 s).');
 // no minute size found: the smallest size only, with its estimate
 assert.equal(M.meshRefusalText({...OFF,suggested_minute:null},'um'),'Component 1 needs about 19,215,000 tetrahedra; the limit is 600,000. Element size 6.36 µm meshes about 597,583 tetrahedra (estimated about 6 min).');
 // the tree's Mesh 1 note says what is wrong: too fine
 const card=card1();
 const rows=M.treeRows(card,{features:[{text:''},{text:''}],regions:[1],display:{faces:[]},mesh:OFF},null,null);
 assert.equal(rows.find(r=>r.key==='mesh').note,'too fine');
});
