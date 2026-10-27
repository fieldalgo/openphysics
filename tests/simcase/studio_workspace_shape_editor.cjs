// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let E,validateShape;
before(async()=>{E=await import('../../packages/simcase/src/simcase/studio/static/workspace-shape-editor.mjs');({validateShape}=await import('../../packages/simcase/src/simcase/studio/static/workspace-shapes.mjs'));});
const core={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
test('moving keeps the whole shape inside the window without changing its size',()=>{
 assert.deepEqual(E.moveShape(core,100,-50),{...core,x:-150,y:-50});
 assert.deepEqual(E.moveShape(core,5000,5000),{...core,x:1000,y:980});
 const rod={name:'Rod',type:'circle',material:'Air',cx:0,cy:0,r:200};assert.deepEqual(E.moveShape(rod,-9999,0),{...rod,cx:-1300});
 const tri={name:'T',type:'polygon',material:'Silicon',points:[[0,0],[100,0],[0,100]]};assert.deepEqual(E.moveShape(tri,10,20).points,[[10,20],[110,20],[10,120]]);
 for(const shape of [E.moveShape(core,5000,5000),E.moveShape(rod,-9999,0)])validateShape(shape);
 assert.throws(()=>E.moveShape(core,NaN,0));
});
test('edge, radius and vertex handles respect the minimum size and the window',()=>{
 assert.deepEqual(E.resizeRect(core,'left',-400),{...core,x:-400,w:650});assert.deepEqual(E.resizeRect(core,'right',300),{...core,w:550});
 assert.deepEqual(E.resizeRect(core,'top',400),{...core,h:400});assert.deepEqual(E.resizeRect(core,'bottom',-100),{...core,y:-100,h:320});
 assert.equal(E.resizeRect(core,'left',9999).w,10);assert.equal(E.resizeRect(core,'top',-50).h,10);assert.equal(E.resizeRect(core,'right',9999).w,1750);assert.equal(E.resizeRect(core,'bottom',-9999).y,-1200);
 assert.throws(()=>E.resizeRect(core,'middle',0));
 const rod={name:'Rod',type:'circle',material:'Air',cx:1000,cy:0,r:200};assert.equal(E.resizeCircle(rod,900).r,500);assert.equal(E.resizeCircle(rod,1).r,10);
 const tri={name:'T',type:'polygon',material:'Silicon',points:[[0,0],[100,0],[0,100]]};
 assert.deepEqual(E.moveVertex(tri,2,-9999,50).points,[[0,0],[100,0],[-1500,50]]);assert.deepEqual(tri.points[2],[0,100]);
 assert.throws(()=>E.moveVertex(tri,3,0,0));assert.equal(E.snapNm(12.4),10);assert.equal(E.snapNm(-13),-15);assert.equal(E.snapNm(7,1),7);
});
test('drag steps are a fixed menu and snapping follows the chosen step',()=>{
 assert.deepEqual([...E.SNAP_STEPS],[1,5,10,50]);assert.equal(E.snapNm(137,50),150);assert.equal(E.snapNm(137,10),140);assert.equal(E.snapNm(137.4,1),137);
});
