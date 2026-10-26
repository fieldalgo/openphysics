// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let OpticalJobMonitor,validatePending,readPending,storePending,snapshot;
before(async()=>{({OpticalJobMonitor,validatePending,readPending,storePending}=await import('../../packages/simcase/src/simcase/studio/static/workspace-job.mjs'));({snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));});
const record=()=>({version:1,job:'1234abcd',serverInstance:'a'.repeat(32),serverVersion:'0.1.0',revision:3,startedAt:'2026-10-26T12:00:00Z',input:snapshot({width:500,height:300,electric:false,heat:false,structure:false,optics:true,voltage:1},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''})});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
test('pending record preserves captured inputs and rejects malformed records before storage',()=>{
 let raw=null;const storage={getItem:()=>raw,setItem:(k,v)=>raw=v,removeItem:()=>raw=null};const r=record();storePending(storage,r);assert.deepEqual(readPending(storage),r);const saved=raw;
 for(const patch of [{job:'../wrong'},{serverInstance:'x'},{revision:-1},{startedAt:3},{serverVersion:'<x>'}])assert.throws(()=>storePending(storage,{...r,...patch}));assert.equal(raw,saved);
 r.input.model.heat=true;assert.throws(()=>validatePending(r));storePending(storage,null);assert.equal(readPending(storage),null);
});
test('monitor captures result once and rejects changed server before making requests',async()=>{
 let requests=0,received;const phases=[];const r=record();const m=new OpticalJobMonitor({api:async path=>{requests++;assert.ok(path.endsWith('?workspace_instance='+r.serverInstance));return path.includes('/result?')?{payload:42}:{status:'done'};},onState:s=>phases.push(s.phase),onResult:(value,p)=>received={value,p}});
 await assert.rejects(m.follow(r,'b'.repeat(32)),/restarted/);assert.equal(requests,0);
 await m.follow(r,r.serverInstance);assert.equal(requests,2);assert.deepEqual(received.p,r);assert.equal(received.value.payload,42);assert.deepEqual(phases,['running','loading','done']);assert.equal(m.busy,false);
});
test('stop during a status request suppresses stale result; resume uses the same job',async()=>{
 const d=deferred(),r=record(),values=[],phases=[];let calls=0;
 const m=new OpticalJobMonitor({api:async path=>{calls++;if(calls===1)return d.promise;return path.includes('/result?')?{fresh:true}:{status:'done'};},onResult:v=>values.push(v),onState:s=>phases.push(s.phase)});
 const first=m.follow(r,r.serverInstance);m.stop();assert.equal(m.busy,false);await m.follow(r,r.serverInstance);d.resolve({status:'done'});await first;
 assert.deepEqual(values,[{fresh:true}]);assert.equal(calls,3);assert.equal(phases.filter(p=>p==='done').length,1);
});
test('stop during result download prevents publication; timeouts and failures remain resumable',async()=>{
 const r=record(),d=deferred(),loading=deferred();let received=0;const states=[];
 const m=new OpticalJobMonitor({api:async path=>path.includes('/result?')?d.promise:{status:'done'},onState:s=>{states.push(s);if(s.phase==='loading')loading.resolve();},onResult:()=>received++});
 const work=m.follow(r,r.serverInstance);await loading.promise;m.stop();d.resolve({});await work;assert.equal(received,0);
 const timeout=new OpticalJobMonitor({api:async()=>({status:'running'}),now:()=>0,limitMs:0,onState:s=>states.push(s)});await timeout.follow(r,r.serverInstance);assert.equal(states.at(-1).phase,'detached');assert.equal(timeout.busy,false);
 for(const response of [{status:'unknown'},{status:'error',error:'test failure'}]){const fail=new OpticalJobMonitor({api:async()=>response,onState:s=>states.push(s)});await fail.follow(r,r.serverInstance);assert.equal(states.at(-1).phase,'error');assert.equal(fail.busy,false);}
});
