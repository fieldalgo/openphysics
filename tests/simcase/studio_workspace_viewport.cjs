// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');
const assert=require('node:assert/strict');
let SchematicCamera;
before(async()=>({SchematicCamera}=await import('../../packages/simcase/src/simcase/studio/static/workspace-viewport.mjs')));
test('zoom retains the centre, pan stays in the schematic, fit restores extent',()=>{
 const c=new SchematicCamera();assert.deepEqual(c.box,[0,0,600,350]);
 c.scale(2);assert.deepEqual(c.box,[150,87.5,300,175]);
 c.pan(10,-10);assert.deepEqual(c.box,[300,0,300,175]);
 c.fit();assert.deepEqual(c.box,[0,0,600,350]);
});
test('finite zoom limits and independent cameras survive repeated interaction',()=>{
 const a=new SchematicCamera(),b=new SchematicCamera();
 for(let i=0;i<100;i++)a.scale(1.25);
 assert.equal(a.zoom,4);a.pan(-100,100);assert.deepEqual(a.box,[0,262.5,150,87.5]);
 const box=a.box;for(const f of [NaN,Infinity,0,-1])a.scale(f);a.pan(NaN,1);assert.deepEqual(a.box,box);
 for(let i=0;i<100;i++)a.scale(.8);
 assert.deepEqual(a.box,[0,0,600,350]);assert.deepEqual(b.box,[0,0,600,350]);
});
test('optical fit shows the window or the design as large as the zoom limits allow',async()=>{
 const {WINDOW_VIEW,shapesView,sectionSvg}=await import('../../packages/simcase/src/simcase/studio/static/workspace-section.mjs');
 const c=new SchematicCamera();c.fitTo(WINDOW_VIEW);assert.ok(Math.abs(c.zoom-350/272)<1e-12);const [x,y,w,h]=c.box;
 assert.ok(x<=150&&x+w>=450&&y<=40&&y+h>=306,'window, title and coordinate line stay visible');
 const core=[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}];
 c.fitTo(shapesView(core));const b=c.box;assert.ok(b[0]<=275&&b[0]+b[2]>=325&&b[1]<=153&&b[1]+b[3]>=175);assert.ok(c.zoom>3);
 c.fitTo(shapesView([{name:'Dot',type:'circle',material:'Silicon',cx:1400,cy:-1100,r:50}]));assert.equal(c.zoom,4);assert.deepEqual(c.box.map(v=>Math.round(v*1000)/1000),[365,241.25,150,87.5]);
 for(const bad of [[0,0,0,10],[NaN,0,1,1],[0,0,-5,5]]){const before=c.box;c.fitTo(bad);assert.deepEqual(c.box,before);}
 const svg=sectionSvg(core);assert.equal((svg.match(/<path d="M[\d.]+ 55 V295"/g)||[]).length,29);assert.equal((svg.match(/stroke-opacity="0.22"/g)||[]).length,10);assert.ok(svg.indexOf('data-grid')<svg.indexOf('data-pick-shape'));
});
