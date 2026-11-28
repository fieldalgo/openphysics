// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Studio 3D fixes X1–X7 (agent round 3D-3), pure helpers.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let M;
test.before(async()=>{M=await import(STATIC+'workspace-model3d.mjs');});
const card1=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-layer-stack-3d.json'),'utf8'));
const card2=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-via-slab-3d.json'),'utf8'));
const off=(side,kind='crosses')=>({ok:false,code:'E-3D-COMBINATION',path:'geometry.components.c.features[0]',feature_index:0,
 refused:kind==='crosses'?`cylinder 'via' crosses the side domain.${side} between z = 0 and 1 m; a cylinder must lie inside or outside every side it spans`
  :`cylinder 'via' touches domain.${side} at one line; move it inside or away`});
const at=(k,v)=>{const d=card2();d.geometry.components.c.features[0][k]=v;return d;};

test('X1: strict bounds and grid values one step inside, for each side; the r bound too',()=>{
 const a=M.crossingAdvice(off('x1'),at('cx',0.8));
 assert.equal(a.text,'Cylinder via crosses the domain side x = 1 m. Keep cx < 0.7 m (cx + r < 1 m). Or r < 0.2 m.');
 assert.deepEqual(a.tries,[{field:'cx',values:[0.69,0.68,0.67]},{field:'r',values:[0.19,0.18,0.17]}]);
 const b=M.crossingAdvice(off('x0'),at('cx',-0.8));
 assert.equal(b.text,'Cylinder via crosses the domain side x = −1 m. Keep cx > −0.7 m (cx − r > −1 m). Or r < 0.2 m.');
 assert.deepEqual(b.tries,[{field:'cx',values:[-0.69,-0.68,-0.67]},{field:'r',values:[0.19,0.18,0.17]}]);
 const y=M.crossingAdvice(off('y1'),at('cy',0.9));
 assert.deepEqual(y.tries,[{field:'cy',values:[0.69,0.68,0.67]},{field:'r',values:[0.099,0.098,0.097]}]);
 const y0=M.crossingAdvice(off('y0'),at('cy',-0.75));
 assert.deepEqual(y0.tries,[{field:'cy',values:[-0.69,-0.68,-0.67]},{field:'r',values:[0.24,0.23,0.22]}]);
 // the engine's tangency refusal: plain words and the same strict bounds
 const t=M.crossingAdvice(off('x1','touches'),at('cx',0.7));
 assert.equal(t.text,'Cylinder via touches the domain side x = 1 m along a line. Keep cx < 0.7 m (cx + r < 1 m). Or r < 0.3 m.');
 assert.deepEqual(t.tries,[{field:'cx',values:[0.69,0.68,0.67]},{field:'r',values:[0.29,0.28,0.27]}]);
 // a value the server confirmed is named in the text
 assert.equal(M.adviceText(a,{cx:0.69,r:0.19}),'Cylinder via crosses the domain side x = 1 m. Keep cx < 0.7 m (cx + r < 1 m): cx = 0.69 m forms. Or r < 0.2 m: r = 0.19 m forms.');
 assert.equal(M.adviceText(a,{cx:0.69}),'Cylinder via crosses the domain side x = 1 m. Keep cx < 0.7 m (cx + r < 1 m): cx = 0.69 m forms. Or r < 0.2 m.');
 // a grid value on the bound itself is not offered (strictly inside)
 assert.deepEqual(M.gridInside(0.7,-1),[0.69,0.68,0.67]);assert.deepEqual(M.gridInside(0.705,-1),[0.7,0.69,0.68]);
 assert.deepEqual(M.gridInside(-0.7,1),[-0.69,-0.68,-0.67]);assert.deepEqual(M.gridInside(120,-1),[110,100,99]);
 assert.equal(M.crossingAdvice({...off('x1'),refused:'something else'},at('cx',0.8)),null);
});

test('X3: the other 3D card opens a question naming the held model, what is lost, and four ways on',()=>{
 const q=M.openOtherQuestion({from:'Via in a layer stack (3D heat)',to:'Copper via through a slab (3D heat)',runs:1,saved:'none'});
 assert.equal(q.title,'Open Copper via through a slab (3D heat)?');
 assert.deepEqual(q.lines,['This project holds Via in a layer stack (3D heat); a project holds one 3D model.',
  ...M.replaceLines({from:'Via in a layer stack (3D heat)',runs:1,saved:'none'})]);
 assert.deepEqual(q.buttons.map(b=>[b.act,b.label]),[['save','Save and replace'],['replace','Replace without saving'],['tab','Open in a new tab'],['cancel','Cancel']]);
 assert.equal(M.OTHER_CARD_ACTION,'Open model');
 assert.equal(M.NOT_SAVED_NOT_REPLACED,'Not replaced: the project file was not saved.');
});
