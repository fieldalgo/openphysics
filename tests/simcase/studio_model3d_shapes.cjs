// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D view's helpers on curved faces (cylinders and spheres in builder shapes): a face with axis null
// and its shape, and the display note in the names panel's detail line.
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let M;
before(async()=>{M=await import('../../packages/simcase/src/simcase/studio/static/model3d-model.mjs');});
const NOTE='Shape drawn for display; the mesh follows it to within its size';
const view={unit:'m',display_note:NOTE};

test('a curved face is shaded by one value and named by its shape',()=>{
 const side={id:8,shape:'cylinder',axis:null,at:null,area:1.88,exterior:false,tag:null,minus:['via'],plus:['background'],
  names:['via.side']};
 assert.equal(M.shadeOf(side),M.CURVED_SHADE);
 assert.equal(M.shadeOf({axis:'x'}),M.SHADE.x);
 const lines=M.faceLines(view,side);
 assert.equal(lines.title,'Face 8 · cylinder');
 assert.equal(lines.detail,`area 1.88 m² · interior · ${NOTE}`);
 assert.equal(lines.sides,'via | background');
});

test('a planar face of a builder shape keeps its axis line and adds the note',()=>{
 const cap={id:5,shape:'plane',axis:'z',at:0,area:0.282743,exterior:true,tag:'z0',minus:[],plus:['via'],
  names:['domain.z0','via.bottom']};
 const lines=M.faceLines(view,cap);
 assert.equal(lines.title,'Face 5 · z = 0 m');
 assert.equal(lines.detail,`area 0.282743 m² · exterior · tag z0 · ${NOTE}`);
 const box=M.faceLines({unit:'um'},{...cap,area:4});
 assert.equal(box.detail,'area 4 um² · exterior · tag z0');      // no note without display_note (slice A)
});
