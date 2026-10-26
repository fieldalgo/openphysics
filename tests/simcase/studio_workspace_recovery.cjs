// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test}=require('node:test');const assert=require('node:assert/strict');
test('recovery validates before replacement, preserves units and reports storage failure',async()=>{
 const {readRecovery,writeRecovery,RECOVERY_KEY}=await import('../../packages/simcase/src/simcase/studio/static/workspace-recovery.mjs');
 const {snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs');
 const data=new Map(),storage={getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)};
 assert.equal(readRecovery(storage),null);
 const input=snapshot({width:500,height:310,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon nitride',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
 writeRecovery(storage,input,new Date('2026-10-26T00:00:00Z'));const saved=data.get(RECOVERY_KEY);
 assert.deepEqual(readRecovery(storage).input,input);
 input.model.height=501;assert.throws(()=>writeRecovery(storage,input));assert.equal(data.get(RECOVERY_KEY),saved);
 assert.throws(()=>writeRecovery({setItem(){throw Error('quota');}},readRecovery(storage).input),/quota/);
 data.set(RECOVERY_KEY,'broken');assert.throws(()=>readRecovery(storage));
 data.set(RECOVERY_KEY,JSON.stringify({version:1,savedAt:'invalid',input}));assert.throws(()=>readRecovery(storage));
});
