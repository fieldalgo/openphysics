// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let OpticalPreflight;
before(async()=>({OpticalPreflight}=await import('../../packages/simcase/src/simcase/studio/static/workspace-preflight.mjs')));
test('a document check captures inputs, never submits a job and retains server identity',async()=>{
 let resolve;const calls=[];const p=new OpticalPreflight((path,body)=>{calls.push([path,body]);return new Promise(r=>resolve=r);});const input={model:{width:500}},doc={name:'capture'};
 const pending=p.check(input,doc,'abc');input.model.width=700;doc.name='edited';await p.check(input,doc,'def');assert.equal(calls.length,1);assert.equal(calls[0][0],'/api/validate?workspace_instance=abc');assert.equal(calls[0][1].doc.name,'capture');
 resolve({ok:true,summary:'Accepted',notes:['fixed wavelength']});await pending;assert.equal(p.record.input.model.width,500);assert.equal(p.record.serverInstance,'abc');assert.equal(p.record.ok,true);assert.equal(p.busy,false);
});
test('rejected documents replace acceptance while transport and malformed responses preserve it with an error',async()=>{
 const p=new OpticalPreflight(async()=>({ok:false,error:'unsupported material'}));await p.check({}, {},'a');assert.equal(p.record.ok,false);assert.equal(p.record.error,'unsupported material');const prior=p.record;
 p.api=async()=>{throw Error('offline');};await p.check({}, {},'b');assert.equal(p.record,prior);assert.equal(p.error,'offline');assert.equal(p.busy,false);
 p.api=async()=>({ok:true,summary:'x',notes:[42]});await p.check({}, {},'b');assert.equal(p.record,prior);assert.match(p.error,/Invalid validation/);
});
