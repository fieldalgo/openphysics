// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let opticalSection,sectionSvg,opticalDocument;
before(async()=>{
 ({opticalSection,sectionSvg}=await import('../../packages/simcase/src/simcase/studio/static/workspace-section.mjs'));
 ({opticalDocument}=await import('../../packages/simcase/src/simcase/studio/static/workspace-optical.mjs'));
});
test('section and submitted rectangle agree at minimum, decimal and maximum widths',()=>{
 for(const width of [300,550.5,900]){
  const section=opticalSection(width),c=section.core;
  assert.deepEqual(section.domain,{x:150,y:55,width:300,height:240});
  assert.ok(Math.abs(c.width-width/10)<1e-12);assert.equal(c.height,22);
  assert.equal(c.y,153);assert.equal(c.x+c.width/2,300);
  const d=opticalDocument({width,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica'}});
  const shape=d.geometry.shapes[0];assert.ok(Math.abs((c.x-300)/100-shape.x)<1e-14);
  assert.equal((175-c.y-c.height)/100,shape.y);assert.equal(c.height/100,shape.h);
  assert.ok(Math.abs(c.width/c.height-width/220)<1e-14);
 }
});
test('physical view contains only submitted bodies and four inspectable PEC edges',()=>{
 const svg=sectionSvg(500,'Core','optical-left','Boundaries');
 assert.equal((svg.match(/data-pick-body=/g)||[]).length,2);
 assert.equal((svg.match(/data-pick-edge=/g)||[]).length,4);
 assert.ok(!svg.includes('data-pick-body="Heater"'));assert.ok(svg.includes('500 × 220 nm'));
 for(const width of [0,299,901,NaN,Infinity,'500'])assert.throws(()=>opticalSection(width));
});
