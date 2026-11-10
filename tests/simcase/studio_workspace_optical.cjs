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
test('bounded optical adapter writes a format 0.3 document in nm and fixes window/boundary without heater',()=>{
 const c=context(),d=c.opticalDocument();assert.equal(c.opticalBlock(),'');assert.equal(d.openphysics,'0.3');assert.equal(d.geometry.length_unit,'nm');assert.equal(d.geometry.depth,null);
 assert.equal(d.geometry.shapes.length,1);assert.deepEqual(d.geometry.shapes[0].points,[[-350,0],[350,0],[350,220],[-350,220]]);assert.equal(d.physics.em1.vacuum_wavelength,'1550 nm');
 assert.equal(d.physics.em1.mode_count,2);assert.equal(d.physics.em1.effective_index_threshold,1.45);assert.equal(d.geometry.background.material,'physmat:SiO2');
 assert.equal(d.physics.em1.boundary.left,'pec');c.state.width=900;assert.equal(d.geometry.shapes[0].points[1][0],350);
});
test('coupled interfaces and unsupported materials are blocked',()=>{
 for(const key of ['electric','heat','structure']){const c=context();c.state[key]=true;assert.notEqual(c.opticalBlock(),'');}
 const c=context();c.setup.materials.Core='Platinum';assert.notEqual(c.opticalBlock(),'');c.setup.materials.Oxide='Air';assert.notEqual(c.opticalBlock(),'');c.setup.materials.Oxide='Silica';c.setup.materials.Core='Silicon nitride';assert.equal(c.opticalBlock(),'');assert.equal(c.opticalDocument().geometry.shapes[0].material,'physmat:Si3N4');
});
