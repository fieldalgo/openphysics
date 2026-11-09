// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// GL-6: the geometry lab's pure helpers (no DOM, no server).
const {test,before}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
let M,STARTERS;
const root=path.resolve(__dirname,'../..');
before(async()=>{
 M=await import('../../packages/simcase/src/simcase/studio/static/geometry-lab-model.mjs');
 ({STARTERS}=await import('../../packages/simcase/src/simcase/studio/static/geometry-lab-starters.mjs'));
});
const example=name=>JSON.parse(fs.readFileSync(path.join(root,'examples/simcase',name+'.json'),'utf8'));

test('starters are the shipped version 1 examples',()=>{
 for(const name of ['geometry_v1_soi_strip','geometry_v1_imprint_rib'])assert.deepEqual(STARTERS[name],example(name));
 assert.deepEqual(Object.keys(STARTERS).sort(),['geometry_v1_imprint_rib','geometry_v1_soi_strip']);
});

test('a parameter edit changes exactly that value and leaves the input untouched',()=>{
 const doc=example('geometry_v1_imprint_rib'),before=JSON.stringify(doc);
 const edited=M.setParameter(doc,'w',0.61);
 assert.equal(JSON.stringify(doc),before);
 const hand=JSON.parse(before);hand.geometry.parameters.w.value=0.61;
 assert.deepEqual(edited,hand);
 assert.deepEqual(M.setParameter(doc,'w','0.61'),hand);
 assert.deepEqual(M.setParameter(doc,'w',' 6.1e-1 '),hand);
 assert.equal(M.setParameter(doc,'slab','t / 2').geometry.parameters.slab.value,'t / 2');
 assert.equal(M.setParameter(doc,'slab','-.5').geometry.parameters.slab.value,-0.5);
 assert.throws(()=>M.setParameter(doc,'nope',1),/Unknown parameter nope/);
 assert.throws(()=>M.setParameter(doc,'w',''),/empty/);
 assert.throws(()=>M.setParameter(doc,'w',Infinity),/finite/);
 assert.throws(()=>M.setParameter(doc,'w','1e999'),/too large/);
 assert.throws(()=>M.setParameter(doc,'w','-1e999'),/too large/);
 assert.throws(()=>M.setParameter(doc,'w','1e-400'),/too small/);
 assert.equal(M.setParameter(doc,'w','0e5').geometry.parameters.w.value,0);
 assert.equal(M.setParameter(doc,'w','0.000').geometry.parameters.w.value,0);
});

test('a slider is offered only for a plain number with a numeric range, in short decimal steps',()=>{
 const sl=M.sliderOf({written:0.5,range:[0.3,0.9]});
 assert.deepEqual(sl,{min:0.3,max:0.9,step:0.001,decimals:3});
 assert.equal(M.sliderValue(sl,'0.6030000000000001'),0.603);
 assert.equal(M.sliderValue(sl,'0.95'),0.9);assert.equal(M.sliderValue(sl,'0.1'),0.3);
 assert.deepEqual(M.sliderOf({written:500,range:[200,2000]}),{min:200,max:2000,step:1,decimals:0});
 assert.deepEqual(M.sliderOf({written:3,range:[0,1000]}),{min:0,max:1000,step:1,decimals:0});
 assert.equal(M.sliderOf({written:'w/2',range:[0.3,0.9]}),null);
 assert.equal(M.sliderOf({written:0.5,range:null}),null);
 assert.equal(M.sliderOf({written:0.5,range:[0.9,0.3]}),null);
 assert.equal(M.sliderOf({written:0.5,range:['a',1]}),null);
});

test('only documents with a version 1 geometry block are read',()=>{
 assert.equal(M.isVersion1(example('geometry_v1_soi_strip')),true);
 assert.equal(M.isVersion1(example('soi_strip')),false);
 assert.equal(M.isVersion1(null),false);assert.equal(M.isVersion1({geometry:'x'}),false);
 assert.equal(M.isVersion1(M.newDocument()),true);
});

test('the saved text is two-space JSON with a newline and parses back to the document',()=>{
 const doc=M.setParameter(example('geometry_v1_imprint_rib'),'w',0.42);
 const text=M.serializeDocument(doc);
 assert.ok(text.endsWith('}\n'));assert.deepEqual(JSON.parse(text),doc);
 assert.equal(text,JSON.stringify(doc,null,2)+'\n');
 assert.equal(M.saveName({name:'SOI strip / v1'}),'SOI_strip_v1.json');
 assert.equal(M.saveName({}),'geometry.json');assert.equal(M.saveName({name:'a.json'}),'a.json');
 assert.equal(M.saveName({name:'///'}),'geometry.json');
});

test('the view keeps one scale for both axes, centres the domain and points y up',()=>{
 const v=M.viewTransform({xmin:-1.5,xmax:1.5,ymin:-1.2,ymax:1.2},800,560,16);
 assert.equal(v.scale,Math.min(768/3,528/2.4));
 assert.equal(v.x(-1.5)+v.x(1.5),800);assert.equal(v.y(-1.2)+v.y(1.2),560);
 assert.ok(v.y(1.2)<v.y(-1.2));
 assert.equal(v.y(1.2),16);
});

test('cell paths follow each loop through its curves in their direction, holes as extra closed loops',()=>{
 const view={x:x=>x,y:y=>y};
 const curves=[{points:[[0,0],[2,0]]},{points:[[2,0],[2,2]]},{points:[[0,2],[2,2]]},{points:[[0,0],[0,2]]},
  {points:[[1,0.5],[0.5,1],[1,1.5]]},{points:[[1,1.5],[1.5,1],[1,0.5]]}];
 const cell={loops:[[[0,true],[1,true],[2,false],[3,false]],[[4,true],[5,true]]]};
 assert.equal(M.cellPath(cell,curves,view),'M0 0 L2 0 L2 2 L0 2 L0 0 Z M1 0.5 L0.5 1 L1 1.5 L1.5 1 L1 0.5 Z');
 assert.equal(M.curvePath([[0.12345,1],[2,3]],view),'M0.123 1 L2 3');
});

test('highlights are looked up by key in the current answer, never carried as indices',()=>{
 const before={regions:[{name:'rib',cells:[4,5]},{name:'background',cells:[0]}],
  selections:[{name:'wall',kind:'boundary',entries:[4,7,10,11]},{name:'si',kind:'region',entries:[1,3]}],
  tags:[{tag:'left',curves:[5,6]}]};
 const after={regions:[{name:'rib',cells:[2]}],selections:[{name:'wall',kind:'boundary',entries:[4,5,7,8,11]}],tags:[]};
 assert.deepEqual([...M.highlightOf(before,'selection:wall').curves],[4,7,10,11]);
 assert.deepEqual([...M.highlightOf(after,'selection:wall').curves],[4,5,7,8,11]);
 assert.deepEqual([...M.highlightOf(before,'selection:si').cells],[1,3]);
 assert.deepEqual([...M.highlightOf(before,'region:rib').cells],[4,5]);
 assert.deepEqual([...M.highlightOf(after,'region:rib').cells],[2]);
 assert.deepEqual([...M.highlightOf(before,'tag:left').curves],[5,6]);
 for(const key of ['tag:left','selection:si','region:gone',null,'odd']){
  const h=M.highlightOf(after,key);assert.equal(h.cells.size+h.curves.size,0,String(key));
 }
 assert.deepEqual([...M.highlightOf(before,'region:a:b').cells],[]);
 assert.deepEqual([...M.highlightOf({regions:[{name:'a:b',cells:[9]}]},'region:a:b').cells],[9]);
});

test('a refusal is shown with the engine message unchanged',()=>{
 const msg="feature 'bow': its boundary crosses itself at (500000, 500000) pm between bow.s1 and bow.s3";
 assert.equal(M.refusalText(200,{ok:false,refused:msg}),msg);
 assert.equal(M.refusalText(422,{detail:'Bad'}),'Bad');
 assert.equal(M.refusalText(422,{detail:[{msg:'Field required'}]}),'Field required');
 assert.match(M.refusalText(500,null),/500/);
});

test('region colours are stable by region order; background is grey',()=>{
 const view={regions:[{name:'slab'},{name:'rib'},{name:'background'}]};
 assert.equal(M.regionColor(view,'background'),'#d9dde3');
 assert.notEqual(M.regionColor(view,'slab'),M.regionColor(view,'rib'));
 assert.equal(M.regionColor(view,'slab'),M.regionColor({regions:[{name:'slab'}]},'slab'));
 assert.equal(M.areaLabel(0.2250000001,'um'),'0.225 um²');
});
