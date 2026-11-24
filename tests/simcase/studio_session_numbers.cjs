// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Stable run numbers and the project name after recovery (optical session version 12), the format.
// Pre-registered: K1 (every earlier fixture is parsed and written again byte for byte), K2 (a
// version 12 round trip of runs 3, 5, 6, 7, 8 and 9, and the reader's refusals), K3 (main fc654fe
// refuses the file by name, alone, in a project and in a recovery record, and does not adopt that
// record: studio_session_fixtures/refusals-v12-fc654fe.json, written by numbered_sessions.mjs from
// that commit's static folder) and K9 (fc654fe reads a version 11 record the same with and without
// `project`). The page's part (K6, K7, K10) is in studio_session_numbers_page.cjs.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIX=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIX,name),'utf8');
let N,P,S,PF,R,G,C;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');S=await import(STATIC+'workspace-multiphysics-session.mjs');
 PF=await import(STATIC+'workspace-project-file.mjs');R=await import(STATIC+'workspace-notebook-recovery.mjs');
 G=await import('./studio_session_fixtures/numbered_sessions.mjs');C=await import('./studio_session_fixtures/closed_sessions.mjs');
});
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const rewrite=text=>{const s=N.parseSession(text);return N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view);};
// a version 12 text edited, with each run's digest computed again unless keepDigest
const edit=(text,f,{keepDigest=false}={})=>{const d=JSON.parse(text);f(d);if(!keepDigest)for(const r of d.runs){delete r.digest;r.digest=S.recordDigest(r);}return S.sessionJson(d);};
const V12='optical-v12-numbers.json';

test('K1: every earlier optical fixture is read and written again byte for byte (version 6 as version 7)',()=>{
 // versions 6 and 7: a file read takes origin "imported" for its runs, so the text written again is
 // compared with main 13f07f4's (below) and with itself written once more; a version 6 file is
 // written as version 7, as the version 7 file of the same state is
 for(const state of ['empty','one','three']){
  const seven=rewrite(fixture(`optical-v7-${state}.json`)),six=rewrite(fixture(`optical-v6-${state}.json`));
  assert.equal(JSON.parse(seven).version,7);assert.equal(six,seven,state);assert.equal(rewrite(seven),seven,state);
 }
 // the texts main 13f07f4 wrote (versions 9, 7 and 10), and the two version 10 files of f8ece10 and 083e151
 const golden=JSON.parse(fixture('sessions-rewritten-13f07f4.json'));
 assert.equal(rewrite(fixture('optical-v6-three.json')),golden['optical-v6-three.json']);
 // the synthetic version 9 session holds runs of this tab (origin "local"): it is written from them again
 assert.equal(C.synthetic(N,P),golden['synthetic version 9']);
 const nine=rewrite(golden['synthetic version 9']);assert.equal(JSON.parse(nine).version,9);assert.equal(rewrite(nine),nine);
 for(const [name,text] of Object.entries(golden))if(name!=='synthetic version 9'){
  assert.equal(rewrite(text),text,name);assert.equal(rewrite(fixture(name)),text,name+' from its file');
 }
 assert.deepEqual(Object.values(golden).map(t=>JSON.parse(t).version),[9,7,7,7,10,10]);
 // version 11: the synthetic runs of closed_sessions.mjs with a closed-window search run
 const v9=N.parseSession(C.synthetic(N,P)),target=N.validateRun({...v9.runs[0],job:'0000000c',settings:N.closedTargetSettings(v9.runs[0].settings,2.46)});
 const eleven=N.sessionText(v9.input,[...v9.runs,target],v9.selected,v9.comparison,v9.view);
 assert.equal(JSON.parse(eleven).version,11);assert.equal(rewrite(eleven),eleven);
 assert.equal(JSON.parse(eleven).runs.some(r=>Object.hasOwn(r,'number')),false);
 // the multiphysics session (version 8, unchanged) and the project file (version 1, unchanged)
 const mp=N.parseSession(fixture('multiphysics-v8.json'));
 assert.equal(S.writeMultiphysicsSession({document:mp.document,runs:mp.runs,baselines:mp.baselines,selected:mp.selected,view:mp.view}).text,fixture('multiphysics-v8.json'));
 const project=fixture('project-v1.json'),read=PF.readProject(project),doc=JSON.parse(project);
 // its multiphysics entry is written again as it is; its optical entry (runs of a tab, origin "local")
 // keeps version 9 and is its own bytes once read; the project is written again from its entries
 const [optical,multi]=read.models.map(m=>m.text),mpEntry=N.parseSession(multi);
 assert.equal(S.writeMultiphysicsSession({document:mpEntry.document,runs:mpEntry.runs,baselines:mpEntry.baselines,selected:mpEntry.selected,view:mpEntry.view}).text,multi);
 const once=rewrite(optical);assert.equal(JSON.parse(once).version,9);assert.equal(rewrite(once),once);
 const again=PF.writeProject({name:doc.name,savedAt:doc.savedAt,studio:doc.studio,active:doc.active,entries:doc.models.map((m,i)=>PF.projectEntry({id:m.id,kind:m.kind,title:m.title,card:m.card,text:read.models[i].text}))});
 assert.equal(again.text,project);
});

test('K2: a version 12 session of runs 3, 5, 6, 7, 8 and 9 is read and written again byte for byte',()=>{
 const text=fixture(V12),doc=JSON.parse(text);
 assert.equal(text,G.numberedSession(N,P,FIX),'the fixture is what this Studio writes');
 assert.equal(doc.version,12);assert.deepEqual(doc.runs.map(r=>r.number),[3,5,6,7,8,9]);
 // number follows job in each run; the top-level keys are those of version 9
 for(const r of doc.runs)assert.deepEqual(Object.keys(r).slice(0,3),['job','number','completedAt']);
 assert.deepEqual(Object.keys(doc),['format','version','application','input','runs','selected','comparison','view']);
 // Run 3 pinned, an open run, a closed-window search run and a run without fields
 assert.deepEqual(doc.runs.map(r=>r.pinned),[true,false,false,false,false,false]);
 assert.deepEqual(doc.runs.map(r=>r.settings.adapter),['optical-shapes-v8','optical-shapes-v9','optical-shapes-v10','optical-shapes-v8','optical-shapes-v8','optical-shapes-v8']);
 assert.deepEqual(doc.runs.map(r=>Object.hasOwn(r,'field')),[true,false,true,true,false,true]);
 const s=N.parseSession(text);
 assert.deepEqual(s.runs.map(r=>r.number),[3,5,6,7,8,9]);
 assert.equal(N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view),text);
 // the number is inside each run's digest
 const d=JSON.parse(text);delete d.runs[1].number;assert.notEqual(S.recordDigest(d.runs[1]),doc.runs[1].digest);
 // in a project, and in a recovery record (recovery lists name the stored numbers)
 const project=PF.writeProject({name:'both-models',savedAt:'2026-11-24T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text})]}).text;
 assert.deepEqual(PF.readProject(project).models[0].session.runs.map(r=>r.number),[3,5,6,7,8,9]);
 const rec=R.readNotebookRecovery({version:1,savedAt:'2026-11-24T10:00:00.000Z',session:text});
 assert.deepEqual(rec.session.runs.map(r=>r.number),[3,5,6,7,8,9]);
});

test('K2: the version 12 reader refuses a changed, missing, invalid, repeated or out-of-order number by name',()=>{
 const text=fixture(V12),refused=(t,message)=>assert.throws(()=>N.parseSession(t),{message});
 // a number edited after the save: the run's digest refuses it
 refused(edit(text,d=>{d.runs[1].number=4;},{keepDigest:true}),'Run 2 changed after it was saved (its check value does not match).');
 // removed (by position), with or without its digest computed again
 refused(edit(text,d=>{delete d.runs[1].number;}),'Run 2: missing number.');
 refused(edit(text,d=>{delete d.runs[1].number;},{keepDigest:true}),'Run 2: missing number.');
 // not a safe integer of at least 1
 for(const n of [0,-1,1.5,'5',null,2**53,true])refused(edit(text,d=>{d.runs[1].number=n;}),'Run 2: invalid run number.');
 // 7 before 5, and the same number twice
 refused(edit(text,d=>{d.runs[1].number=7;d.runs[3].number=5;}),'Run 3 is numbered 6, not after Run 2\'s 7.');
 refused(edit(text,d=>{d.runs[2].number=5;}),'Two runs have the same number 5.');
 refused(edit(text,d=>{d.runs[5].number=3;}),'Two runs have the same number 3.');
 refused(edit(text,d=>{d.runs[4].number=10;}),'Run 6 is numbered 9, not after Run 5\'s 10.');
 // after these checks validateRun names the stored number
 refused(edit(text,d=>{d.runs[2].settings.search_target=1.45;}),'Run 6: invalid search target. Search near n_eff must lie between 1.45 and 3.4777 (3 decimals).');
 refused(edit(text,d=>{d.runs[3].effective_index.reverse();}),'Run 7: its effective indices are not ranked by Re n_eff.');
 // versions 9 to 11 hold no number: their run keys are unchanged
 const eleven=edit(text,d=>{d.version=11;});
 refused(eleven,'Run 1: unknown key "number".');
 // version 13 is the newer one
 refused(edit(text,d=>{d.version=13;}),'This session file is version 13, newer than this Studio reads (versions 6–12). Open it in a newer Studio.');
});

test('K2: version 12 is written exactly when a run is not numbered by its place',()=>{
 const s=N.parseSession(fixture(V12)),renumbered=s.runs.map((r,i)=>Object.assign(N.validateRun(r),{number:i+1}));
 // the same runs numbered 1..6 are version 11 (a closed-window search run), without numbers
 const plain=N.sessionText(s.input,renumbered,s.selected,s.comparison,s.view),doc=JSON.parse(plain);
 assert.equal(doc.version,11);assert.equal(doc.runs.some(r=>Object.hasOwn(r,'number')),false);
 assert.equal(N.sessionVersion(renumbered,VIEW),11);assert.equal(N.sessionVersion(s.runs,VIEW),12);
 // a run without a number is at its place; one run off its place is enough
 assert.equal(N.sessionVersion(s.runs.map(r=>N.validateRun(r)),VIEW),11);
 const two=renumbered.slice(0,2).map((r,i)=>Object.assign(N.validateRun(r),{number:i?3:1}));
 assert.equal(N.sessionVersion(two,VIEW),12);
 // what a version 12 reader refuses is not written
 const back=renumbered.slice(0,2).map((r,i)=>Object.assign(N.validateRun(r),{number:i?1:2}));
 assert.throws(()=>N.sessionText(s.input,back,null,[null,null],VIEW),{message:'Run numbers must be whole numbers of at least 1, increasing in list order.'});
 // an earlier file is numbered from 1 in file order
 assert.deepEqual(N.parseSession(fixture('optical-v7-three.json')).runs.map(r=>r.number),[1,2,3]);
 // the number is not an enumerated key of a parsed run: a copy is a run without a number
 const run=s.runs[0];assert.equal(run.number,3);assert.equal(Object.keys(run).includes('number'),false);assert.equal({...run}.number,undefined);
 assert.deepEqual([...N.OPTICAL_SESSION_VERSIONS],[6,7,9,10,11,12]);assert.deepEqual([...PF.KIND_VERSIONS.workspace],[6,7,9,10,11,12]);
});

test('K3 and K9: main fc654fe refuses version 12 by name and does not adopt its record; it reads a version 11 record alike with and without project',()=>{
 const golden=JSON.parse(fixture('refusals-v12-fc654fe.json'));
 const newer='This session file is version 12, newer than this Studio reads (versions 6–11). Open it in a newer Studio.';
 assert.equal(golden.session,newer);assert.equal(golden.project,'Optical waveguide: '+newer);assert.equal(golden.recovery,newer);
 assert.equal(golden.adopted,false);
 assert.equal(golden['version 11 record'].version,11);assert.equal(golden['version 11 record']['equal with and without project'],true);
 assert.deepEqual(golden['version 11 record'].keys,['savedAt','session','savedFile','openedFile','openedCurrent','page']);
});

test('the recovery record keeps the project name, browser-only; a malformed one is ignored',async()=>{
 const text=fixture(V12),base={version:1,savedAt:'2026-11-24T10:00:00.000Z',session:text};
 assert.equal(R.readNotebookRecovery(base).project,null);
 assert.deepEqual(R.readNotebookRecovery({...base,project:{name:'both-models',from:'file'}}).project,{name:'both-models',from:'file'});
 assert.deepEqual(R.readNotebookRecovery({...base,project:{name:'Ring 한국',from:'user'}}).project,{name:'Ring 한국',from:'user'});
 for(const project of ['both-models',{name:'x'},{name:'x',from:'other'},{name:' x',from:'user'},{name:'',from:'user'},{name:'a\u0001b',from:'user'},{name:'x'.repeat(81),from:'user'},{name:7,from:'user'},[]])
  assert.equal(R.readNotebookRecovery({...base,project}).project,null,JSON.stringify(project));
 // the record keeps the session's version 1; project is written only when it is a valid name
 const written=[],store={save:async record=>{written.push(record);return record;}};
 const autosave=new R.NotebookAutosave(store,{delay:0,setTimer:fn=>{fn();return 1;},clearTimer:()=>{}});
 const make=()=>text;
 autosave.schedule('a',make,{project:{name:'both-models',from:'file'}});await autosave.settle();
 autosave.schedule('b',make,{project:null});await autosave.settle();
 autosave.schedule('c',make,{project:{name:' bad',from:'user'}});await autosave.settle();
 assert.deepEqual(written.map(r=>r.project??null),[{name:'both-models',from:'file'},null,null]);
 assert.deepEqual(written.map(r=>r.version),[1,1,1]);assert.equal(Object.keys(written[0]).at(-1),'project');
});

test('a version 12 session is the same session in browser recovery whatever its runs\' origin (sessionKey leaves out origin and digest)',()=>{
 const text=fixture(V12),recovered=edit(text,d=>{for(const r of d.runs)r.origin='recovered';});
 assert.notEqual(recovered,text);assert.equal(R.sessionKey(recovered),R.sessionKey(text));
 // another run name is another session
 assert.notEqual(R.sessionKey(edit(text,d=>{d.runs[0].label='Other';})),R.sessionKey(text));
});
