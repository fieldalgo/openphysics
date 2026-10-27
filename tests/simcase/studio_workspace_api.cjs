// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let solverApi;
let APPLICATIONS,templatePhysics;
let opticalBlock,opticalDocument;
before(async()=>{
({solverApi}=await import('../../packages/simcase/src/simcase/studio/static/workspace-api.mjs'));
({APPLICATIONS,templatePhysics}=await import('../../packages/simcase/src/simcase/studio/static/workspace-applications.mjs'));
({opticalBlock,opticalDocument}=await import('../../packages/simcase/src/simcase/studio/static/workspace-optical.mjs'));
});
const test=require('node:test');
const assert=require('node:assert/strict');




test('API serializes submitted snapshot and parses successful response',async()=>{
 const body={doc:{width:500}};let sent;
 const result=await solverApi('/api/validate',body,async(path,options)=>{
  sent=options;assert.equal(path,'/api/validate');body.doc.width=700;
  return {ok:true,json:async()=>({ok:true})};
 });
 assert.deepEqual(result,{ok:true});assert.equal(sent.method,'POST');
 assert.equal(JSON.parse(sent.body).doc.width,500);assert.equal(sent.signal.aborted,false);
});
test('GET and backend errors preserve the explicit API contract',async()=>{
 await solverApi('/api/jobs/12345678',undefined,async(path,options)=>{
  assert.equal(options.method,'GET');assert.equal(options.body,undefined);
  return {ok:true,json:async()=>({status:'done'})};
 });
 await assert.rejects(solverApi('/api/run',{},async()=>({ok:false,json:async()=>({detail:'Offline'})})),/Offline/);
 await assert.rejects(solverApi('/api/run',{},async()=>({ok:true,json:async()=>{throw Error('HTML');}})),/not JSON/);
 await assert.rejects(solverApi('/api/run',{},async()=>{throw Error('Disconnected');}),/Disconnected/);
});
test('application availability agrees with actual execution gates',async()=>{
 const setup={materials:{Core:'Silicon',Oxide:'Silica'}};
 for(const app of APPLICATIONS){
  const model={width:500,...templatePhysics(app.id)},heat=await import('../../packages/simcase/src/simcase/studio/static/workspace-heat.mjs');
  const heatOnly=model.heat&&!model.electric&&!model.structure&&!model.optics;
  const runnable=heatOnly?heat.thermalBlock(heat.validateThermal(heat.DEFAULT_THERMAL))==='':opticalBlock(model,setup)==='';
  assert.equal(runnable,app.available,app.id);
  if(heatOnly)assert.equal(heat.heatDocument(heat.DEFAULT_THERMAL).physics.heat1.type,'thermal.steady2d');
  if(!app.available)assert.throws(()=>opticalDocument(model,setup));
 }
 const a=templatePhysics('optical');a.heat=true;assert.equal(templatePhysics('optical').heat,false);
 assert.throws(()=>templatePhysics('unimplemented'));
});

test('HTTP failure status reaches job recovery without replacing server detail',async()=>{
 for(const status of [404,409,500])await assert.rejects(solverApi('/api/jobs/12345678',undefined,async()=>({ok:false,status,json:async()=>({detail:'Captured server detail'})})),error=>error.status===status&&error.message==='Captured server detail');
});
