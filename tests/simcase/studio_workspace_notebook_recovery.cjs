// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let NotebookAutosave,readNotebookRecovery,indexedNotebookStore,snapshot,createSession,captureSession,OPTICAL_SETTINGS;
before(async()=>{({NotebookAutosave,readNotebookRecovery,indexedNotebookStore}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook-recovery.mjs'));({snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));({createSession,captureSession,OPTICAL_SETTINGS}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs'));});
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


test('queued recovery keeps the scheduled notebook when the UI replaces or edits its live session',async()=>{
 const input=snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
 const run={job:'12345678',completedAt:'2026-10-26T00:00:00Z',settings:{...OPTICAL_SETTINGS},input:JSON.parse(JSON.stringify(input)),label:'Reference',pinned:true,neff:[2.4,1.7],field:{nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]},origin:'local'};
 const runs=[run],comparison=[run.job,run.job],view={mode:0,component:'magnitude',window:'Core region',probe:{x:0,y:.15,active:true}};
 let record;const saver=new NotebookAutosave({save:async r=>record=r},timing);
 saver.schedule('original',captureSession(input,runs,run.job,comparison,view));
 input.model.width=800;run.label='Changed';run.pinned=false;run.input.model.width=700;run.neff[0]=9;run.settings.window_um=[-2,2,-2,2];runs.length=0;comparison.fill(null);view.probe.x=.5;
 await saver.flush();const recovered=readNotebookRecovery(record).session;
 assert.equal(recovered.input.model.width,500);assert.equal(recovered.runs.length,1);assert.equal(recovered.runs[0].label,'Reference');assert.equal(recovered.runs[0].pinned,true);assert.equal(recovered.runs[0].input.model.width,500);assert.deepEqual(recovered.runs[0].neff,[2.4,1.7]);assert.deepEqual(recovered.comparison,['12345678','12345678']);assert.equal(recovered.view.probe.x,0);
});

// Minimal asynchronous IDB transaction model: reads and writes are ordered;
// abort discards the pending write. The browser check exercises real IndexedDB.
function database(initial){
 let value=initial,tail=Promise.resolve();
 return {open(){const opening={};queueMicrotask(()=>{
  opening.result={close(){},transaction(){
   let finish,aborted=false,written=false,next;
   const ready=tail;tail=new Promise(resolve=>finish=resolve);
   const tx={objectStore:()=>({get(){const request={};ready.then(()=>{
    request.result=structuredClone(value);request.onsuccess?.();
    queueMicrotask(()=>{if(!aborted){if(written)value=next;tx.oncomplete?.();}finish();});
   });return request;},put(record){written=true;next=structuredClone(record);}}),abort(){aborted=true;queueMicrotask(()=>tx.onabort?.());}};
   return tx;
  }};opening.onsuccess();
 });return opening;}};
}
test('concurrent notebook writers cannot replace a newer committed recovery',async()=>{
 const db=database(null),a=indexedNotebookStore(db),b=indexedNotebookStore(db);
 a.adopt(await a.load());b.adopt(await b.load());
 const first={version:1,savedAt:'2026-10-26T00:00:00Z',session:'A'};
 const [x,y]=await Promise.allSettled([a.save(first),b.save({...first,session:'B'})]);
 assert.equal(x.status,'fulfilled');assert.equal(y.status,'rejected');assert.equal(y.reason.code,'recovery-conflict');
 assert.equal((await b.load()).session,'A');
 await assert.rejects(b.save({...first,session:'retry B'}),{code:'recovery-conflict'});
 const latest=await b.load();b.adopt(latest);const committed=await b.save({...first,session:'reviewed B'});
 assert.notEqual(committed.revision,latest.revision);assert.equal((await a.load()).session,'reviewed B');
 await assert.rejects(a.save(first),{code:'recovery-conflict'});
});
test('reads do not grant overwrite authority and stale review adoption remains guarded',async()=>{
 const legacy={version:1,savedAt:'2026-10-26T00:00:00Z',session:'legacy'};
 const db=database(legacy),a=indexedNotebookStore(db),b=indexedNotebookStore(db);
 const old=await a.load();await assert.rejects(a.save(legacy),/Read browser recovery/);
 a.adopt(old);b.adopt(old);await b.save({...legacy,session:'new'});
 const preview=await a.load();assert.equal(preview.session,'new');
 await assert.rejects(a.save(legacy),{code:'recovery-conflict'});
 a.adopt(old);await assert.rejects(a.save(legacy),{code:'recovery-conflict'});
 a.adopt(preview);assert.equal((await a.save(legacy)).session,'legacy');
});
test('legacy same-time snapshots have different revisions when payloads differ',async()=>{
 const {recoveryRevision}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook-recovery.mjs');
 assert.notEqual(recoveryRevision({savedAt:'same',session:'A'}),recoveryRevision({savedAt:'same',session:'B'}));
 assert.equal(recoveryRevision(null),null);
});
test('autosave exposes the committed revision and conflict without replacing saved state',async()=>{
 const states=[];let fail=false;
 const saver=new NotebookAutosave({save:async record=>{if(fail)throw Object.assign(Error('conflict'),{code:'recovery-conflict'});return {...record,revision:'committed'};}},{...timing,onState:s=>states.push(s)});
 saver.schedule('a',()=> 'A');await saver.flush();assert.equal(states.at(-1).record.revision,'committed');
 fail=true;saver.schedule('b',()=> 'B');await saver.flush();assert.equal(states.at(-1).code,'recovery-conflict');assert.equal(saver.savedStamp,'a');assert.equal(saver.pending,true);
});
