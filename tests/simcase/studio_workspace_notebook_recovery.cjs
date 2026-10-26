// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let NotebookAutosave,readNotebookRecovery,indexedNotebookStore,snapshot,createSession,OPTICAL_SETTINGS;
before(async()=>{({NotebookAutosave,readNotebookRecovery,indexedNotebookStore}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook-recovery.mjs'));({snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));({createSession,OPTICAL_SETTINGS}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs'));});
const timing={setTimer:()=>1,clearTimer:()=>{}};
test('autosave serializes writes and coalesces pending edits to the newest snapshot',async()=>{
 const calls=[],resolvers=[];const saver=new NotebookAutosave({save:r=>{calls.push(r);return new Promise(resolve=>resolvers.push(resolve));}},timing);
 saver.schedule('a',()=>'{"a":1}');const pending=saver.flush();saver.schedule('b',()=>'{"b":2}');saver.schedule('c',()=>'{"c":3}');assert.equal(calls.length,1);resolvers.shift()();await Promise.resolve();assert.equal(calls.length,2);assert.equal(calls[1].session,'{"c":3}');resolvers.shift()();await pending;assert.equal(saver.savedStamp,'c');assert.equal(saver.pending,false);
});
test('undo during a write re-saves the previous snapshot after the in-flight newer write',async()=>{
 const calls=[],resolvers=[];let immediate=true;const saver=new NotebookAutosave({save:r=>{calls.push(r.session);return immediate?Promise.resolve():new Promise(resolve=>resolvers.push(resolve));}},timing);
 saver.schedule('a',()=> 'A');await saver.flush();immediate=false;saver.schedule('b',()=> 'B');const pending=saver.flush();saver.schedule('a',()=> 'A');resolvers.shift()();await Promise.resolve();assert.deepEqual(calls,['A','B','A']);resolvers.shift()();await pending;assert.equal(saver.savedStamp,'a');
});
test('storage failure does not retry forever, and explicit retry preserves the latest requested snapshot',async()=>{
 let stored='previous',fail=true,calls=0;const phases=[];const saver=new NotebookAutosave({save:async r=>{calls++;if(fail)throw Error('quota');stored=r.session;}},{...timing,onState:s=>phases.push(s.phase)});
 saver.schedule('a',()=> 'A');await saver.flush();assert.equal(stored,'previous');assert.equal(calls,1);assert.equal(saver.pending,true);assert.equal(phases.at(-1),'error');fail=false;await saver.retry();assert.equal(stored,'A');assert.equal(saver.pending,false);
 await assert.rejects(indexedNotebookStore(null).load(),/unavailable/);
});
test('browser recovery validates the full notebook and marks fields as recovered, not newly computed',()=>{
 const input=snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
 const run={job:'12345678',completedAt:'2026-10-26T00:00:00Z',settings:OPTICAL_SETTINGS,input,neff:[2.4,1.7],field:{nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]},origin:'local'};
 const record={version:1,savedAt:'2026-10-26T00:00:00Z',session:JSON.stringify(createSession(input,[run],run.job,[run.job,run.job]))};const recovered=readNotebookRecovery(record);assert.equal(recovered.session.runs[0].origin,'recovered');assert.deepEqual(recovered.session.runs[0].field,run.field);
 assert.equal(readNotebookRecovery(null),null);assert.throws(()=>readNotebookRecovery({...record,version:2}));assert.throws(()=>readNotebookRecovery({...record,session:'corrupt'}));
});

test('the default timer path completes a scheduled save without an explicit flush',async()=>{
 let saved;const done=new Promise(resolve=>saved=resolve);const saver=new NotebookAutosave({save:async record=>saved(record)},{delay:1});saver.schedule('timer',()=> 'timer payload');const record=await done;assert.equal(record.session,'timer payload');await Promise.resolve();assert.equal(saver.savedStamp,'timer');
});
