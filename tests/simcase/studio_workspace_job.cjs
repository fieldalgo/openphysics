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
 // round 16 (S1): no answer for the limit detaches (a job the server says is running never does; see below)
 const timeout=new OpticalJobMonitor({api:async()=>{throw Error('network');},now:()=>0,limitMs:0,onState:s=>states.push(s)});await timeout.follow(r,r.serverInstance);assert.equal(states.at(-1).phase,'detached');assert.equal(timeout.busy,false);
 for(const response of [{status:'unknown'},{status:'error',error:'test failure'}]){const fail=new OpticalJobMonitor({api:async()=>response,onState:s=>states.push(s)});await fail.follow(r,r.serverInstance);assert.equal(states.at(-1).phase,'error');assert.equal(fail.busy,false);}
});

test('missing jobs, restarted servers and failed solvers require detach; transport errors remain resumable',async()=>{
 const r=record();
 for(const failure of [Object.assign(Error('missing'),{status:404}),Object.assign(Error('restarted'),{status:409})]){
  let terminal,results=0;const monitor=new OpticalJobMonitor({api:async()=>{throw failure;},onState:s=>terminal=s,onResult:()=>results++});await monitor.follow(r,r.serverInstance);assert.equal(terminal.canResume,false);assert.match(terminal.message,/Detach this job/);assert.equal(results,0);assert.equal(monitor.busy,false);
 }
 // round 16 (S1): a status request that fails is tried again; after three minutes without an
 // answer the monitor detaches, and Resume can check the job again (fake clock)
 for(const failure of [Error('network'),Object.assign(Error('temporary'),{status:500})]){
  let t=0,terminal,results=0,calls=0;const monitor=new OpticalJobMonitor({api:async()=>{calls++;throw failure;},now:()=>t,wait:async ms=>{t+=ms;},onState:s=>terminal=s,onResult:()=>results++});
  await monitor.follow(r,r.serverInstance);assert.equal(terminal.phase,'detached');assert.equal(terminal.message,'The server has not answered for three minutes. Resume to check this job again.');
  assert.ok(t>=180000&&t<180700+700,'detached once three minutes passed without an answer');assert.ok(calls>200,'retried every 700 ms');assert.equal(results,0);assert.equal(monitor.busy,false);
 }
 let terminal;const monitor=new OpticalJobMonitor({api:async()=>({status:'error',error:'No convergence'}),onState:s=>terminal=s});await monitor.follow(r,r.serverInstance);assert.equal(terminal.canResume,false);assert.match(terminal.message,/Detach this job/);
 await assert.rejects(monitor.follow(r,'b'.repeat(32)),error=>error.status===409&&/Detach/.test(error.message));
});

// round 16 (S1): a long job the server keeps answering for is followed to its result
test('S1: a job running for 12 min is followed while the server answers; the message names m:ss and what it solves',async()=>{
 const r=record(),start=Date.parse(r.startedAt);let t=start;const states=[];let received=0;
 const m=new OpticalJobMonitor({api:async path=>path.includes('/result?')?{ok:1}:{status:t-start<12*60000?'running':'done'},now:()=>t,wait:async ms=>{t+=ms;},onState:s=>states.push(s),onResult:()=>received++});
 await m.follow(r,r.serverInstance);
 assert.equal(received,1);assert.equal(states.at(-1).phase,'done');assert.equal(states.some(s=>s.phase==='detached'),false);
 assert.equal(states[0].message,'Computing job 1234abcd · 0:00 · 2 modes');
 assert.ok(states.some(s=>s.message==='Computing job 1234abcd · 3:07 · 2 modes'));
 assert.match(states.filter(s=>s.phase==='running').at(-1).message,/^Computing job 1234abcd · 12:0\d · 2 modes$/);
});
test('S1: answers between failures restart the three-minute window; Resume after detaching gets the result',async()=>{
 const r=record();let t=0,n=0;const states=[];
 // fails for 2:50, answers once, fails for 2:50 again, answers running, then done
 const plan=ms=>ms<170000?'fail':ms<170700?'running':ms<341000?'fail':ms<350000?'running':'done';
 const m=new OpticalJobMonitor({api:async path=>{n++;if(path.includes('/result?'))return {};const p=plan(t);if(p==='fail')throw Error('network');return {status:p};},now:()=>t,wait:async ms=>{t+=ms;},onState:s=>states.push(s)});
 await m.follow(r,r.serverInstance);assert.equal(states.at(-1).phase,'done');assert.equal(states.some(s=>s.phase==='detached'),false);
 assert.ok(states.some(s=>/ · no answer from the server for 2:4\d; still checking$/.test(s.message)));
 // no answer at all: detached, then Resume (follow again) once the server answers
 let up=false;t=0;const later=[];const m2=new OpticalJobMonitor({api:async path=>{if(!up)throw Error('network');return path.includes('/result?')?{}:{status:'done'};},now:()=>t,wait:async ms=>{t+=ms;},onState:s=>later.push(s)});
 await m2.follow(r,r.serverInstance);assert.equal(later.at(-1).phase,'detached');up=true;await m2.follow(r,r.serverInstance);assert.equal(later.at(-1).phase,'done');
});
test('S1: what a job solves, from its pending record',async()=>{
 const {jobWhat,elapsedText}=await import('../../packages/simcase/src/simcase/studio/static/workspace-job.mjs');
 assert.deepEqual([5000,187000,760000,-3].map(elapsedText),['0:05','3:07','12:40','0:00']);
 assert.equal(jobWhat({}),'2 modes');assert.equal(jobWhat({modeCount:1}),'1 mode');
 const ob={edges:{left:'open'},target:3.4};
 // slice T2: both searches of the run (t and (t + 1.444) / 2 to two decimals); one below 1.466
 assert.equal(jobWhat({openBoundary:ob}),'Open boundary · 2 modes · searches near 3.40 and 2.42');
 assert.equal(jobWhat({openBoundary:ob,pmlCheck:true}),'Open boundary · 2 modes · searches near 3.40 and 2.42 · PML check (up to 2 more solves)');
 assert.equal(jobWhat({openBoundary:ob,pmlCheck:true,modeCount:1}),'Open boundary · 1 mode · searches near 3.40 and 2.42 · PML check (up to 1 more solve)');
 assert.equal(jobWhat({openBoundary:{...ob,target:1.465}}),'Open boundary · 2 modes · search near 1.465');
 assert.equal(jobWhat({openBoundary:{...ob,target:1.466}}),'Open boundary · 2 modes · searches near 1.466 and 1.46');
 assert.equal(jobWhat({openBoundary:ob,checkOf:'1234abcd',checkIndex:0,checkCount:2}),'PML check · mode 1 of 2');
});
test('S1: Stop during a 12-minute running job stops it; the elapsed text at 3:07',async()=>{
 const r={...record(),openBoundary:{edges:{left:'open',right:'open',bottom:'open',top:'open'},target:2.46},pmlCheck:true},start=Date.parse(r.startedAt);
 let t=start,m,stopped=false,received=0;const states=[];
 m=new OpticalJobMonitor({api:async path=>path.includes('/result?')?{}:{status:'running'},now:()=>t,wait:async ms=>{t+=ms;if(t-start>=12*60000&&!stopped){stopped=true;m.stop();}},onState:s=>states.push(s),onResult:()=>received++});
 await m.follow(r,r.serverInstance);
 assert.equal(stopped,true);assert.equal(m.busy,false);assert.equal(received,0);
 assert.equal(states.at(-1).phase,'detached');assert.equal(states.at(-1).message,'Stopped waiting. Server computation may continue; resume to retrieve its result.');
 // no poll is answered after Stop: the last running message is the one before it
 assert.match(states.filter(s=>s.phase==='running').at(-1).message,/ · 11:5\d · /);
 assert.ok(states.some(s=>s.message==='Computing job 1234abcd · 3:07 · Open boundary · 2 modes · searches near 2.46 and 1.95 · PML check (up to 2 more solves)'));
});
