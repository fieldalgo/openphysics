// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let NotebookAutosave,readNotebookRecovery,indexedNotebookStore,snapshot,createSession,captureSession,opticalSettings;
before(async()=>{({NotebookAutosave,readNotebookRecovery,indexedNotebookStore}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook-recovery.mjs'));({snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));({createSession,captureSession,opticalSettings}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs'));});
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
 const run={job:'12345678',completedAt:'2026-10-26T00:00:00Z',settings:opticalSettings(),input,effective_index:[2.4,1.7],field:{node_coordinates:[[0,0],[1e-6,0],[0,1e-6]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]},origin:'local'};
 const record={version:1,savedAt:'2026-10-26T00:00:00Z',session:JSON.stringify(createSession(input,[run],run.job,[run.job,run.job]))};const recovered=readNotebookRecovery(record);assert.equal(recovered.session.runs[0].origin,'recovered');const f=recovered.session.runs[0].field;assert.deepEqual({node_coordinates:f.node_coordinates,triangles:f.triangles,real:f.real,imag:f.imag},run.field);
 assert.equal(readNotebookRecovery(null),null);assert.throws(()=>readNotebookRecovery({...record,version:2}));assert.throws(()=>readNotebookRecovery({...record,session:'corrupt'}));
});

test('the default timer path completes a scheduled save without an explicit flush',async()=>{
 let saved;const done=new Promise(resolve=>saved=resolve);const saver=new NotebookAutosave({save:async record=>saved(record)},{delay:1});saver.schedule('timer',()=> 'timer payload');const record=await done;assert.equal(record.session,'timer payload');await Promise.resolve();assert.equal(saver.savedStamp,'timer');
});


test('queued recovery keeps the scheduled notebook when the UI replaces or edits its live session',async()=>{
 const input=snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
 const run={job:'12345678',completedAt:'2026-10-26T00:00:00Z',settings:{...opticalSettings()},input:JSON.parse(JSON.stringify(input)),label:'Reference',pinned:true,effective_index:[2.4,1.7],field:{node_coordinates:[[0,0],[1e-6,0],[0,1e-6]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]},origin:'local'};
 const runs=[run],comparison=[run.job,run.job],view={mode:0,component:'magnitude',window:'Core region',probe:{x:0,y:.15,active:true}};
 let record;const saver=new NotebookAutosave({save:async r=>record=r},timing);
 saver.schedule('original',captureSession(input,runs,run.job,comparison,view));
 input.model.width=800;run.label='Changed';run.pinned=false;run.input.model.width=700;run.effective_index[0]=9;run.settings.domain={xmin:'-2 um'};runs.length=0;comparison.fill(null);view.probe.x=.5;
 await saver.flush();const recovered=readNotebookRecovery(record).session;
 assert.equal(recovered.input.model.width,500);assert.equal(recovered.runs.length,1);assert.equal(recovered.runs[0].label,'Reference');assert.equal(recovered.runs[0].pinned,true);assert.equal(recovered.runs[0].input.model.width,500);assert.deepEqual(recovered.runs[0].effective_index,[2.4,1.7]);assert.deepEqual(recovered.comparison,['12345678','12345678']);assert.equal(recovered.view.probe.x,0);
});

// Minimal asynchronous IDB transaction model: keyed values; requests in one
// transaction are ordered and the transaction completes after the last request's
// handler has run; abort discards its writes. The browser check exercises real
// IndexedDB.
function database(initial){
 const data=new Map([['latest',initial]]);let tail=Promise.resolve();
 return {data,open(){const opening={};queueMicrotask(()=>{
  opening.result={close(){},transaction(){
   let finish,aborted=false,pending=0;const writes=new Map();
   const ready=tail;tail=new Promise(resolve=>finish=resolve);
   const settle=()=>queueMicrotask(()=>{if(pending>0)return;if(!aborted){for(const [key,value] of writes)data.set(key,value);tx.oncomplete?.();}finish();});
   const tx={objectStore:()=>({get(key){const request={};pending++;ready.then(()=>{
    const value=writes.has(key)?writes.get(key):data.get(key);request.result=value===undefined?undefined:structuredClone(value);
    request.onsuccess?.();pending--;settle();
   });return request;},put(record,key){writes.set(key,structuredClone(record));}}),abort(){aborted=true;queueMicrotask(()=>tx.onabort?.());}};
   return tx;
  }};opening.onsuccess();
 });return opening;}};
}
test('the first save after a page adopts a record keeps that record as an earlier session',async()=>{
 const record=session=>({version:1,savedAt:'2026-10-26T00:00:00Z',session});
 const db=database(null);
 // page 1 starts empty and saves twice: nothing earlier to keep
 let page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(record('A1'));await page.save(record('A2'));
 assert.equal((await page.load()).session,'A2');assert.deepEqual(await page.loadEarlier(),[]);
 // page 2 loads A2, does not recover it and saves new work: A2 is kept
 page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(record('B1'));await page.save(record('B2'));
 assert.equal((await page.load()).session,'B2');assert.deepEqual((await page.loadEarlier()).map(r=>r.session),['A2']);
 // pages 3, 4 and 5 do the same; at most three earlier sessions, newest first
 for(const name of ['C','D','E']){page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(record(name));}
 assert.deepEqual((await page.loadEarlier()).map(r=>r.session),['D','C','B2']);
 // adopting the latest record again (a reviewed replacement) still keeps it before the next save
 const latest=await page.load();page.adopt(latest);page.adopt(latest);await page.save(record('F'));
 assert.deepEqual((await page.loadEarlier()).map(r=>r.session),['E','D','C']);
 // a conflicting save changes neither key
 const other=indexedNotebookStore(db);other.adopt(await other.load());await page.save(record('G'));
 await assert.rejects(other.save(record('H')),{code:'recovery-conflict'});
 assert.equal((await other.load()).session,'G');assert.deepEqual((await other.loadEarlier()).map(r=>r.session),['E','D','C']);
});
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

test('explicit recovery replacement can repair a reviewed unreadable record without loading its session',async()=>{
 const invalid={version:99,savedAt:'bad',session:'broken'},store=indexedNotebookStore(database(invalid));
 assert.throws(()=>readNotebookRecovery(invalid));
 const saver=new NotebookAutosave(store,timing);const reviewed=await store.load();
 await saver.replaceReviewed(reviewed,'current',()=> 'valid current snapshot');
 assert.equal((await store.load()).session,'valid current snapshot');assert.equal(saver.savedStamp,'current');
});
test('replacement cannot overwrite a change made after review, even when its stamp was previously saved',async()=>{
 const db=database(null),store=indexedNotebookStore(db),other=indexedNotebookStore(db);store.adopt(null);
 const states=[],saver=new NotebookAutosave(store,{...timing,onState:s=>states.push(s)});
 saver.schedule('same',()=> 'current');await saver.flush();const reviewed=await store.load();
 other.adopt(reviewed);await other.save({version:1,savedAt:'2026-10-26T00:00:00Z',session:'other'});
 await saver.replaceReviewed(reviewed,'same',()=> 'current');assert.equal(states.at(-1).code,'recovery-conflict');assert.equal((await store.load()).session,'other');
 await saver.replaceReviewed(await store.load(),'same',()=> 'current');assert.equal((await store.load()).session,'current');assert.equal(saver.pending,false);
});
test('replacement refuses an active write and supersedes a queued older snapshot',async()=>{
 let complete,stored,adoptions=0;
 const saver=new NotebookAutosave({adopt:()=>adoptions++,save:r=>new Promise(resolve=>{stored=r;complete=resolve;})},timing);
 saver.schedule('old',()=> 'old');const writing=saver.flush();
 await assert.rejects(saver.replaceReviewed(null,'new',()=> 'new'),/busy/);assert.equal(adoptions,0);complete();await writing;
 saver.schedule('queued',()=> 'queued');const replacement=saver.replaceReviewed(null,'new',()=> 'new');assert.equal(stored.session,'new');assert.equal(adoptions,1);complete();await replacement;assert.equal(saver.savedStamp,'new');assert.equal(saver.pending,false);
});
test('continuing the recovered latest session replaces it and keeps no duplicate earlier copy',async()=>{
 const record=session=>({version:1,savedAt:'2026-10-26T00:00:00Z',session});
 const db=database(null);
 let page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(record('A'));
 // a new page does not recover A and saves new work: A is kept as an earlier session
 page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(record('B'));
 assert.equal(page.movedEarlier(),true);assert.deepEqual((await page.loadEarlier()).map(r=>r.session),['A']);
 await page.save(record('B2'));assert.equal(page.movedEarlier(),false);
 // another page recovers the latest session (B2) and continues it: it is replaced, A stays
 for(const next of ['C','D','E']){
  page=indexedNotebookStore(db);const latest=await page.load();page.adopt(latest,{kept:true});
  await page.save(record(next));assert.equal(page.movedEarlier(),false);
 }
 assert.equal((await page.load()).session,'E');assert.deepEqual((await page.loadEarlier()).map(r=>r.session),['A']);
});
