// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let sectionSvg,toSvg,toNm,opticalDocument;
before(async()=>{
 ({sectionSvg,toSvg,toNm}=await import('../../packages/simcase/src/simcase/studio/static/workspace-section.mjs'));
 ({opticalDocument}=await import('../../packages/simcase/src/simcase/studio/static/workspace-optical.mjs'));
});
const shapes=[{name:'Slab',type:'rect',material:'Silicon',x:-1500,y:0,w:3000,h:90},{name:'Rod',type:'circle',material:'Silicon nitride',cx:0,cy:500,r:150},{name:'Wedge <b>',type:'polygon',material:'Air',points:[[-300,-600],[300,-600],[0,-300]]}];
test('drawing and submitted document use the same nanometre coordinates',()=>{
 assert.deepEqual(toSvg(-1500,1200),[150,55]);assert.deepEqual(toSvg(1500,-1200),[450,295]);toNm(...toSvg(123,-456)).forEach((v,i)=>assert.ok(Math.abs(v-[123,-456][i])<1e-9));
 const named=shapes.map((s,i)=>({...s,name:'S'+i}));
 const svg=sectionSvg(named),d=opticalDocument({wavelength:1550,coreMesh:30,shapes:named,electric:false,heat:false,structure:false,optics:true},{materials:{Oxide:'Silica'}});
 assert.ok(svg.includes('points="150,175 450,175 450,166 150,166"'));assert.deepEqual(d.geometry.shapes[0].points,[[-1.5,0],[1.5,0],[1.5,.09],[-1.5,.09]]);
 assert.ok(svg.includes('cx="300" cy="125" r="15"'));assert.deepEqual(d.geometry.shapes[1],{name:'s2',material:'Si3N4',mesh_size:.03,type:'circle',cx:0,cy:.5,r:.15});
 assert.ok(svg.includes('points="270,235 330,235 300,205"'));assert.deepEqual(d.geometry.shapes[2],{name:'s3',material:'vacuum',type:'polygon',points:[[-.3,-.6],[.3,-.6],[0,-.3]]});
});
test('every shape is selectable in draw order, names are escaped and boundaries stay inspectable',()=>{
 const svg=sectionSvg(shapes.map((s,i)=>i===2?{...s,name:'Wedge'}:s),{selected:1});
 assert.equal((svg.match(/data-pick-shape=/g)||[]).length,3);assert.ok(svg.indexOf('data-pick-shape="0"')<svg.indexOf('data-pick-shape="2"'));
 assert.ok(svg.includes('Select shape Rod (circle, Silicon nitride)'));assert.ok(svg.includes('Rod · 300 × 300 nm extent'));
 const escaped=sectionSvg([{...shapes[0],name:'A<b>'}]);assert.ok(!escaped.includes('<b>'));assert.ok(escaped.includes('A&lt;b&gt;'));
 const boundaries=sectionSvg(shapes.slice(0,1),{mode:'Boundaries',selectedEdge:'optical-left'});
 assert.equal((boundaries.match(/data-pick-edge=/g)||[]).length,4);assert.ok(!boundaries.includes('role="button" tabindex="0" aria-label="Select shape'));
});
