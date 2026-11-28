// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// A domain bound given by a parameter or an expression: Studio's Domain row, its mesh and element
// size guards (diagonal/400 to diagonal/4) and Add feature's defaults use the domain the server's
// check evaluated (check.domain, numbers in the component's unit); before that answer has come, a
// bound that is not a number is unknown, as before.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let M,C;
test.before(async()=>{M=await import(STATIC+'workspace-model3d.mjs');C=await import(STATIC+'model3d-mesh-model.mjs');});
const card=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-layer-stack-3d.json'),'utf8'));
// card 1 written out in numbers, then with its domain top as an expression
const numeric=()=>{const d=card(),c=d.geometry.components.stack3d;d.geometry.parameters={t_ox:{value:'10 um'},via_w:{value:'20 um'}};
 c.domain={xmin:0,xmax:200,ymin:0,ymax:200,zmin:0,zmax:610};c.features[0].layers[1].thickness=10;
 Object.assign(c.features[1],{xmin:90,xmax:110,ymin:90,ymax:110,zmin:500,zmax:510});return d;};
const expr=()=>{const d=numeric();d.geometry.components.stack3d.domain.zmax='500 + t_ox + 100';return d;};
const EVALUATED={xmin:0,xmax:200,ymin:0,ymax:200,zmin:0,zmax:610};
const W={estimateText:null,meshBlocked:null};
const meshField=doc=>M.fieldsOf(doc,'mesh')[0];

test('the Domain row: the evaluated domain where a bound is an expression',()=>{
 const check={features:[{text:''},{text:'',size:[20,20,10]}],regions:[],display:{faces:[]},domain:EVALUATED};
 const note=(doc,ch)=>M.treeRows(doc,ch,null,null).find(r=>r.key==='domain').note;
 assert.equal(note(numeric(),null),'x 0–200 · y 0–200 · z 0–610 µm');
 assert.equal(note(expr(),check),'x 0–200 · y 0–200 · z 0–610 µm');
 assert.equal(note(expr(),null),'x 0–200 · y 0–200 µm','before the check has answered: as before');
});

test("Studio's size guards use the evaluated domain's diagonal",()=>{
 const sentence='Mesh element size must be between 1.68–168 µm.';
 assert.equal(M.editField(numeric(),meshField(numeric()),'1 um').problem,sentence);
 assert.equal(M.editField(expr(),meshField(expr()),'1 um',{domain:EVALUATED}).problem,sentence);
 assert.equal(M.editField(expr(),meshField(expr()),'1 um').problem,undefined,'no evaluated domain: no guard, as before');
 const f=M.fieldsOf(expr(),'feature:1').find(x=>x.key==='features[1].element_size');
 assert.equal(M.editField(expr(),f,'1 um',{domain:EVALUATED}).problem,'Via element size must be between 1.68–168 µm.');
 // a box bound against an evaluated domain bound
 const zmax=M.fieldsOf(expr(),'feature:1').find(x=>x.key==='features[1].zmax');
 assert.equal(M.editField(expr(),zmax,'700',{domain:EVALUATED}).problem,'Via z max must be between 500–610 µm.');
});

test("Add feature's defaults sit in the evaluated domain",()=>{
 const z=(doc,opt)=>{const f=M.addFeature(doc,'box',opt).geometry.components.stack3d.features.at(-1);return [f.zmin,f.zmax];};
 assert.deepEqual(z(numeric()),[152.5,457.5]);
 assert.deepEqual(z(expr(),{domain:EVALUATED}),[152.5,457.5]);
 const layers=M.addFeature(expr(),'layers',{domain:EVALUATED}).geometry.components.stack3d.features.at(-1);
 assert.deepEqual([layers.z0,layers.layers[0].thickness],[152.5,305]);
});
