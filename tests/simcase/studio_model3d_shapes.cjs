// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D builder's Cylinder and Sphere forms (E2-UI, F1 and F2): their fields, Studio's own
// guards in the 2D range sentence, the tree's summary, and Add feature's defaults.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let M;
test.before(async()=>{M=await import(STATIC+'workspace-model3d.mjs');});
const card2=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-via-slab-3d.json'),'utf8'));
const comp=doc=>doc.geometry.components.c;
// card 2 with its cylinder replaced by a sphere at the centre (a C5 sphere_in_box document)
const sphereDoc=()=>{const d=card2();comp(d).features=[{name:'ball',type:'sphere',cx:0,cy:0,cz:0.5,r:0.3,material:'copper'}];return d;};
const field=(doc,node,label)=>M.fieldsOf(doc,node).find(f=>f.label===label);
const edit=(doc,node,label,raw)=>M.editField(doc,field(doc,node,label),raw);

test('F2: Add feature takes Cylinder and Sphere; Extrude stays greyed with its reason',()=>{
 assert.deepEqual(M.FEATURE_TYPES.filter(t=>t.available).map(t=>t.label),['Box','Layers','Cylinder','Sphere']);
 assert.deepEqual(M.FEATURE_TYPES.filter(t=>!t.available).map(t=>[t.label,t.reason]),[['Extrude','Extrude comes with a later geometry step']]);
 // a cylinder through the whole slab at the domain's x-y centre, a quarter of the smaller x-y extent
 const c=M.addFeature(card2(),'cylinder');
 assert.deepEqual(comp(c).features.at(-1),{name:'cylinder',type:'cylinder',cx:0,cy:0,r:0.5,zmin:0,zmax:1,material:'slab'});
 // a sphere at the domain's centre, a quarter of its smallest extent
 const s=M.addFeature(card2(),'sphere');
 assert.deepEqual(comp(s).features.at(-1),{name:'sphere',type:'sphere',cx:0,cy:0,cz:0.5,r:0.25,material:'slab'});
 assert.equal(comp(M.addFeature(c,'cylinder')).features.at(-1).name,'cylinder_2');
});

test('F1: the Cylinder and Sphere fields, in table order',()=>{
 assert.deepEqual(M.fieldsOf(card2(),'feature:0').map(f=>[f.label,f.kind]),
  [['name','name'],['axis','fixed'],['cx','length'],['cy','length'],['r','length'],['zmin','length'],['zmax','length'],['material','material']]);
 // the axis is shown read-only: z (fixed)
 assert.equal(field(card2(),'feature:0','axis').value,'z (fixed)');
 assert.equal(edit(card2(),'feature:0','axis','x').problem,'This field cannot be edited here.');
 assert.deepEqual(M.fieldsOf(sphereDoc(),'feature:0').map(f=>[f.label,f.kind]),
  [['name','name'],['cx','length'],['cy','length'],['cz','length'],['r','length'],['material','material']]);
});

test('F1: numbers, quantities, parameters and expressions are taken as for a box',()=>{
 assert.equal(comp(edit(card2(),'feature:0','r','0.25').doc).features[0].r,0.25);
 assert.equal(comp(edit(card2(),'feature:0','r','200 mm').doc).features[0].r,'200 mm');
 assert.equal(comp(edit(card2(),'feature:0','cx','0.1 - 0.05').doc).features[0].cx,'0.1 - 0.05');
 const p=M.addParameter(card2(),'rv','0.2 m');
 assert.equal(comp(edit(p,'feature:0','r','rv').doc).features[0].r,'rv');
 assert.equal(comp(edit(sphereDoc(),'feature:0','cz','0.4').doc).features[0].cz,0.4);
});

test("F1: Studio's guards are r > 0 and zmin < zmax only, in the 2D form of words",()=>{
 assert.equal(edit(card2(),'feature:0','r','0').problem,'Via r must be greater than 0 m.');
 assert.equal(edit(sphereDoc(),'feature:0','r','-0.1').problem,'Ball r must be greater than 0 m.');
 assert.equal(edit(card2(),'feature:0','zmin','1').problem,'Via z min must be less than 1 m.');
 assert.equal(edit(card2(),'feature:0','zmax','0').problem,'Via z max must be greater than 0 m.');
 // a centre or radius against the domain is a combination: the server checks it (W5 shows the engine's stem)
 assert.equal(edit(card2(),'feature:0','r','1.5').problem,undefined);
 assert.equal(edit(card2(),'feature:0','cx','2').problem,undefined);
 assert.equal(edit(card2(),'feature:0','zmax','2').problem,undefined);
 assert.equal(edit(sphereDoc(),'feature:0','cz','1.2').problem,undefined);
 assert.equal(edit(sphereDoc(),'feature:0','r','0.6').problem,undefined);
 // a parameter or an expression is not guarded here (the server evaluates it)
 assert.equal(edit(card2(),'feature:0','r','5 * 1').problem,undefined);
});

test('the tree: a cylinder and a sphere with their radius beside them',()=>{
 const rows=M.treeRows(card2(),null,null,null);
 assert.deepEqual(rows.filter(r=>r.key.startsWith('feature:')).map(r=>[r.label,r.note]),[['1 Cylinder via','r 0.3 m · z 0–1 m']]);
 assert.deepEqual(M.treeRows(sphereDoc(),null,null,null).filter(r=>r.key.startsWith('feature:')).map(r=>[r.label,r.note]),[['1 Sphere ball','r 0.3 m']]);
});
