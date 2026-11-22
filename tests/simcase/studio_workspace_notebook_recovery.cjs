// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let restorePage,recordPage,NotebookAutosave,readNotebookRecovery,indexedNotebookStore,distinctRecords,sessionKey,openedFileName,snapshot,createSession,captureSession,opticalSettings;
before(async()=>{({NotebookAutosave,readNotebookRecovery,indexedNotebookStore,distinctRecords,sessionKey,openedFileName,restorePage,recordPage}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook-recovery.mjs'));({snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));({createSession,captureSession,opticalSettings}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs'));});
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

test('browser recovery keeps the last saved session file beside the session and ignores a malformed one',async()=>{
 let record;const saver=new NotebookAutosave({save:async r=>record=r},timing);
 const input=snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
 const session=JSON.stringify(createSession(input,[],null,[null,null]));
 const savedFile={name:'optical-waveguide-session-2026-11-21-1305.json',savedAt:'2026-11-21T04:05:00Z',current:true};
 saver.schedule('one',()=>session,{savedFile});await saver.flush();
 assert.deepEqual(record.savedFile,savedFile);assert.deepEqual(readNotebookRecovery(record).savedFile,savedFile);
 saver.schedule('two',()=>session);await saver.flush();
 assert.equal('savedFile' in record,false);assert.equal(readNotebookRecovery(record).savedFile,null);
 assert.equal(readNotebookRecovery({...record,savedFile:{name:'x.exe',savedAt:'2026-11-21T04:05:00Z',current:true}}).savedFile,null);
});
test('a session text is stored once: the same model saved again after a move or a second open is not kept twice',async()=>{
 const record=(session,savedAt='2026-11-22T05:26:19Z')=>({version:1,savedAt,session});
 const db=database(null);
 // a page saves the optical session O, then moves to a multiphysics model H and back
 let page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(record('O','2026-11-22T05:25:00Z'));
 page.keepPrevious();await page.save(record('H','2026-11-22T05:25:10Z'));
 assert.deepEqual((await page.loadEarlier()).map(r=>r.session),['O']);
 // the unchanged optical session written again: the earlier copy goes, H is kept
 page.keepPrevious();await page.save(record('O','2026-11-22T05:25:40Z'));
 assert.equal((await page.load()).session,'O');assert.deepEqual((await page.loadEarlier()).map(r=>r.session),['H']);assert.equal(page.movedEarlier(),true);
 // a new page opens the file of H (the same text) and saves: H is in the list once, as the latest
 page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(record('H','2026-11-22T05:26:19Z'));
 assert.equal((await page.load()).session,'H');assert.deepEqual((await page.loadEarlier()).map(r=>r.session),['O']);
 // a new page whose first save repeats the latest text replaces it and keeps no copy
 page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(record('H','2026-11-22T05:27:00Z'));
 assert.deepEqual((await page.loadEarlier()).map(r=>r.session),['O']);assert.equal(page.movedEarlier(),false);
});
test('the recovery lists show each session text once, newest first',()=>{
 const r=(session,savedAt)=>({version:1,savedAt,session});
 const latest=r('H','2026-11-22T05:26:19Z');
 // the earlier copy of the latest text, and two optical records 30 s apart with the same text
 const earlier=[r('H','2026-11-22T05:26:19Z'),r('O','2026-11-22T05:25:10Z'),r('O','2026-11-22T05:24:40Z'),r('P','2026-11-22T05:25:30Z')];
 assert.deepEqual(distinctRecords(latest,earlier).map(e=>[e.record.session,e.index]),[['H',-1],['P',3],['O',1]]);
 assert.deepEqual(distinctRecords(null,earlier).map(e=>e.index),[0,3,1]);
 assert.deepEqual(distinctRecords(null,[]),[]);
});
test('the autosave writes the opened file name beside the session and the reader returns it',async()=>{
 let record;const saver=new NotebookAutosave({save:async r=>record=r},timing);
 const input=snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
 const session=JSON.stringify(createSession(input,[],null,[null,null]));
 saver.schedule('one',()=>session,{openedFile:'optical-waveguide-session-2026-11-22-1425.json'});await saver.flush();
 assert.equal(record.openedFile,'optical-waveguide-session-2026-11-22-1425.json');assert.equal(readNotebookRecovery(record).openedFile,'optical-waveguide-session-2026-11-22-1425.json');
 saver.schedule('two',()=>session,{openedFile:'x.exe'});await saver.flush();
 assert.equal('openedFile' in record,false);assert.equal(readNotebookRecovery({...record,openedFile:'../x.json/'}).openedFile,null);
});
test('two stored sessions that differ only in their view are the same session',async()=>{
 const text=(page,extra={})=>JSON.stringify({format:'openphysics-studio-session',version:8,document:{name:'H'},runs:[1,2],...extra,view:{page,selection:'model'}});
 assert.equal(sessionKey(text('Results')),sessionKey(text('Model')));assert.notEqual(sessionKey(text('Model')),sessionKey(text('Model',{runs:[1]})));
 assert.equal(sessionKey('not json'),'not json');
 const r=(session,savedAt)=>({version:1,savedAt,session});
 assert.deepEqual(distinctRecords(r(text('Model'),'2026-11-22T05:27:00Z'),[r(text('Results'),'2026-11-22T05:26:00Z')]).map(e=>e.index),[-1]);
 // the store: a first save whose session equals the stored one but for the view replaces it
 const db=database(null);let page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(r(text('Results'),'2026-11-22T05:26:00Z'));
 page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(r(text('Model'),'2026-11-22T05:27:00Z'));
 assert.deepEqual(await page.loadEarlier(),[]);
 // a record moved in front drops an older copy of its own session deeper in the list
 page.keepPrevious();await page.save(r('O','2026-11-22T05:28:00Z'));
 page.keepPrevious();await page.save(r(text('Connections'),'2026-11-22T05:29:00Z'));
 page.keepPrevious();await page.save(r('P','2026-11-22T05:30:00Z'));
 assert.deepEqual((await page.loadEarlier()).map(x=>x.session==='O'?'O':'H'),['H','O']);
});
test('an opened file name may be in any script, never a path',()=>{
 assert.equal(openedFileName('가열-도파로 세션.json'),'가열-도파로 세션.json');
 for(const bad of ['../x.json','a/b.json','a\\b.json','x.exe','a\u0001.json',42,null])assert.equal(openedFileName(bad),null,String(bad));
});
// round 9 (J2): the same runs and inputs are one session, whatever their origin, selection or view
const optical=(extra={},run={})=>JSON.stringify({format:'openphysics-studio-session',version:7,input:{w:700},
 runs:[{job:'aaaaaaaa',label:'Design A',pinned:true,origin:'local',...run},{job:'bbbbbbbb',label:'Design B',pinned:true,origin:'local',...run}],
 selected:'bbbbbbbb',comparison:['aaaaaaaa','bbbbbbbb'],view:{mode:0},...extra});
test('round 9: a session key leaves out the runs\' origin, the selected run, the comparison and the view',()=>{
 const key=sessionKey(optical());
 for(const other of [optical({},{origin:'imported'}),optical({},{origin:'recovered'}),optical({selected:'aaaaaaaa'}),optical({comparison:['bbbbbbbb','aaaaaaaa']}),optical({view:{mode:1}})])
  assert.equal(sessionKey(other),key);
 // the runs or the inputs make another session
 for(const other of [optical({input:{w:600}}),optical({},{label:'Design C'}),optical({},{pinned:false}),optical({runs:[]})])
  assert.notEqual(sessionKey(other),key);
});
test('round 9: a page that opens or recovers the runs already stored keeps no second copy of them',async()=>{
 const r=(session,savedAt,extra={})=>({version:1,savedAt,session,...extra});
 const db=database(null);
 // page 1 computes the runs; page 2 opens the session file of the same runs (origin imported)
 let page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(r(optical(),'2026-11-22T15:50:14Z'));
 page=indexedNotebookStore(db);page.adopt(await page.load());
 await page.save(r(optical({selected:'aaaaaaaa'},{origin:'imported'}),'2026-11-22T15:50:50Z',{openedFile:'optical-waveguide-session-2026-11-22-1549.json'}));
 assert.deepEqual(await page.loadEarlier(),[]);assert.equal(page.movedEarlier(),false);
 // page 3 recovers them (origin recovered) from an earlier copy: still one session
 page.keepPrevious();await page.save(r('H','2026-11-22T15:51:00Z'));
 page=indexedNotebookStore(db);page.adopt(await page.load());await page.save(r(optical({},{origin:'recovered'}),'2026-11-22T15:52:00Z'));
 assert.deepEqual((await page.loadEarlier()).map(x=>x.session),['H']);
});
test('round 9: a list entry is the newest record of its session and names the file any merged record names',()=>{
 const r=(session,savedAt,extra={})=>({version:1,savedAt,session,...extra});
 const withFile=r(optical({},{origin:'imported'}),'2026-11-22T15:50:14Z',{openedFile:'optical-waveguide-session-2026-11-22-1549.json'});
 const newer=r(optical({selected:'aaaaaaaa'},{origin:'recovered'}),'2026-11-22T15:50:50Z');
 const entries=distinctRecords(null,[newer,withFile,r('H','2026-11-22T15:49:00Z')]);
 assert.deepEqual(entries.map(e=>[e.index,e.file]),[[0,'optical-waveguide-session-2026-11-22-1549.json'],[2,null]]);
 // the newest record's own file is kept; a saved file is named before an opened one
 const saved=r(optical(),'2026-11-22T15:51:00Z',{savedFile:{name:'optical-waveguide-session-2026-11-22-1551.json',savedAt:'2026-11-22T15:51:00Z',current:true}});
 assert.deepEqual(distinctRecords(saved,[withFile]).map(e=>[e.index,e.file]),[[-1,'optical-waveguide-session-2026-11-22-1551.json']]);
});

test('round 10: a record keeps the page shown and whether the notebook still matched its opened file; a record without them restores as before',async()=>{
 let record;const saver=new NotebookAutosave({save:async r=>record=r},timing);
 const input=snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
 const session=JSON.stringify(createSession(input,[],null,[null,null])),file='optical-waveguide-session-2026-11-22-2010.json';
 saver.schedule('one',()=>session,{openedFile:file,openedCurrent:true,page:'Results'});await saver.flush();
 assert.deepEqual([record.openedFile,record.openedCurrent,record.page],[file,true,'Results']);
 const read=readNotebookRecovery(record);assert.deepEqual([read.openedFile,read.openedCurrent,read.page],[file,true,'Results']);
 // the session text is written as it was given: the extras sit beside it, never in it
 assert.equal(record.session,session);
 saver.schedule('two',()=>session,{openedFile:file,openedCurrent:false,page:'Compare'});await saver.flush();
 assert.deepEqual([readNotebookRecovery(record).openedCurrent,readNotebookRecovery(record).page],[false,'Compare']);
 // invalid values are not written and are ignored when read; openedCurrent needs an opened file
 saver.schedule('three',()=>session,{openedCurrent:true,page:'Applications'});await saver.flush();
 assert.equal('openedCurrent' in record,false);assert.equal('page' in record,false);
 assert.deepEqual([readNotebookRecovery({...record,page:'Settings'}).page,readNotebookRecovery({...record,page:1}).page],[null,null]);
 assert.equal(readNotebookRecovery({...record,openedFile:file,openedCurrent:'yes'}).openedCurrent,null);
 assert.equal(readNotebookRecovery({...record,openedCurrent:true}).openedCurrent,null);
 // a record as the code before this change wrote it (no page, no openedCurrent): the same fields
 // as before, and the page rule of before (Compare for two runs or more, Results for one, else Model)
 const today={version:1,savedAt:'2026-11-22T20:10:00Z',session,openedFile:file,savedFile:{name:file,savedAt:'2026-11-22T20:10:00Z',current:false}};
 const old=readNotebookRecovery(today);
 assert.deepEqual({savedAt:old.savedAt,savedFile:old.savedFile,openedFile:old.openedFile},{savedAt:today.savedAt,savedFile:today.savedFile,openedFile:file});
 assert.deepEqual([old.page,old.openedCurrent],[null,null]);
 assert.deepEqual([0,1,2,6].map(n=>restorePage(old.page,n)),['Model','Results','Compare','Compare']);
 // a named page, when the runs allow it
 assert.deepEqual([restorePage('Results',2),restorePage('Model',2),restorePage('Compare',2)],['Results','Model','Compare']);
 assert.deepEqual([restorePage('Compare',1),restorePage('Results',0)],['Results','Model']);
 assert.equal(recordPage('Results'),'Results');assert.equal(recordPage('Connections'),null);
});
