// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let opticalBlock,opticalDocument;
before(async()=>{
({opticalBlock,opticalDocument}=await import('../../packages/simcase/src/simcase/studio/static/workspace-optical.mjs'));
});
const test=require('node:test');
const assert=require('node:assert/strict');

function context(){const c={state:{width:700,electric:false,heat:false,structure:false,optics:true},setup:{materials:{Core:'Silicon',Oxide:'Silica'}}};c.opticalBlock=()=>opticalBlock(c.state,c.setup);c.opticalDocument=()=>opticalDocument(c.state,c.setup);return c;}
test('bounded optical adapter converts nm and fixes window/boundary without heater',()=>{
 const c=context(),d=c.opticalDocument();assert.equal(c.opticalBlock(),'');assert.equal(d.geometry.shapes.length,1);assert.equal(d.geometry.shapes[0].w,.7);assert.equal(d.geometry.shapes[0].x,-.35);assert.equal(d.geometry.shapes[0].h,.22);assert.equal(d.physics.em1.wavelength,1.55);assert.equal(d.physics.em1.boundary.left,'pec');c.state.width=900;assert.equal(d.geometry.shapes[0].w,.7);
});
test('coupled interfaces and unsupported materials are blocked',()=>{
 for(const key of ['electric','heat','structure']){const c=context();c.state[key]=true;assert.notEqual(c.opticalBlock(),'');}
 const c=context();c.setup.materials.Core='Platinum';assert.notEqual(c.opticalBlock(),'');c.setup.materials.Core='Silicon nitride';assert.equal(c.opticalBlock(),'');assert.equal(c.opticalDocument().geometry.shapes[0].material,'Si3N4');
});
