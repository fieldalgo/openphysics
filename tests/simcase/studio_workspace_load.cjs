// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let LatestWorkspaceLoad;
before(async()=>({LatestWorkspaceLoad}=await import('../../packages/simcase/src/simcase/studio/static/workspace-load.mjs')));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};

test('the latest selected file wins even when reads finish in reverse order',async()=>{
 const gate=new LatestWorkspaceLoad(()=> 'same workspace'),old=deferred(),next=deferred();
 const first=gate.read(()=>old.promise),second=gate.read(()=>next.promise);
 next.resolve('new session');assert.deepEqual(await second,{value:'new session'});
 old.resolve('old session');assert.equal(await first,null);
});
test('edits, invalid drafts or job transitions during a read require a new review',async()=>{
 for(const after of ['edited','invalid draft','new job']){let context='original';const gate=new LatestWorkspaceLoad(()=>context),pending=deferred();
 const reading=gate.read(()=>pending.promise);context=after;pending.resolve('file');await assert.rejects(reading,/workspace changed/);}
});
test('cancel or a synchronous recovery choice silences an obsolete success and failure',async()=>{
 for(const fails of [false,true]){const gate=new LatestWorkspaceLoad(()=> 'unchanged'),pending=deferred();const reading=gate.read(()=>pending.promise);
 gate.invalidate();if(fails)pending.reject(Error('late broken file'));else pending.resolve('late content');assert.equal(await reading,null);}
});
test('an obsolete read error cannot overwrite the newer result, while the current error is reported',async()=>{
 const gate=new LatestWorkspaceLoad(()=> 'same'),old=deferred();const first=gate.read(()=>old.promise);
 assert.deepEqual(await gate.read(async()=> 'chosen'),{value:'chosen'});old.reject(Error('old'));assert.equal(await first,null);
 await assert.rejects(gate.read(async()=>{throw Error('current malformed file');}),/current malformed/);
});
